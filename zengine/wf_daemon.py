#!/usr/bin/env python
"""
workflow worker daemon
"""
import json
import traceback
from pprint import pformat

import signal
from time import sleep, time

import pika
from tornado.escape import json_decode

from pyoko.conf import settings
from pyoko.lib.utils import get_object_from_path
from zengine.client_queue import ClientQueue, BLOCKING_MQ_PARAMS
from zengine.engine import ZEngine
from zengine.current import Current
from zengine.lib.cache import Session, KeepAlive
from zengine.lib.exceptions import HTTPError, SecurityInfringementAttempt
from zengine.lib.decorators import VIEW_METHODS, JOB_METHODS, runtime_importer

from zengine.log import log
import sys

runtime_importer()

sys._zops_wf_state_log = ''

wf_engine = ZEngine()

LOGIN_REQUIRED_MESSAGE = {"cmd": "error", "error": "Login required", "code": 401}


class Worker(object):
    """
    Workflow runner worker object
    """
    INPUT_QUEUE_NAME = 'in_queue'
    INPUT_EXCHANGE = 'input_exc'

    def __init__(self):
        self.connect()
        signal.signal(signal.SIGTERM, self.exit)
        log.info("Worker starting")

    def exit(self, signal=None, frame=None):
        """
        Properly close the AMQP connections
        """
        self.input_channel.close()
        self.client_queue.close()
        self.connection.close()
        log.info("Worker exiting")
        sys.exit(0)

    def connect(self):
        """
        make amqp connection and create channels and queue binding
        """
        self.connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
        self.client_queue = ClientQueue()
        self.input_channel = self.connection.channel()

        self.input_channel.exchange_declare(exchange=self.INPUT_EXCHANGE,
                                            type='topic',
                                            durable=True)
        self.input_channel.queue_declare(queue=self.INPUT_QUEUE_NAME)
        self.input_channel.queue_bind(exchange=self.INPUT_EXCHANGE, queue=self.INPUT_QUEUE_NAME)
        log.info("Bind to queue named '%s' queue with exchange '%s'" % (self.INPUT_QUEUE_NAME,
                                                                        self.INPUT_EXCHANGE))



    def clear_queue(self):
        """
        clear outs all messages from INPUT_QUEUE_NAME
        """
        def remove_message(ch, method, properties, body):
            print("Removed message: %s" % body)
        self.input_channel.basic_consume(remove_message, queue=self.INPUT_QUEUE_NAME, no_ack=True)
        try:
            self.input_channel.start_consuming()
        except (KeyboardInterrupt, SystemExit):
            log.info(" Exiting")
            self.exit()

    def run(self):
        """
        actual consuming of incoming works starts here
        """
        self.input_channel.basic_consume(self.handle_message,
                                         queue=self.INPUT_QUEUE_NAME,
                                         no_ack=True
                                         )
        try:
            self.input_channel.start_consuming()
        except (KeyboardInterrupt, SystemExit):
            log.info(" Exiting")
            self.exit()

    def _prepare_error_msg(self, msg):
        try:
            return \
                msg + '\n\n' + \
                "INPUT DATA: %s\n\n" % pformat(self.current.input) + \
                "OUTPUT DATA: %s\n\n" % pformat(self.current.output) + \
                sys._zops_wf_state_log
        except:
            return msg

    def _handle_ping_pong(self, data, session):

        still_alive = KeepAlive(sess_id=session.sess_id).update_or_expire_session()
        msg = {'msg': 'pong'}
        if not still_alive:
            msg.update(LOGIN_REQUIRED_MESSAGE)
        return msg

    def _handle_job(self, session, data, headers):
        # security check for preventing external job execution attempts
        if headers['source'] != 'Internal':
            raise SecurityInfringementAttempt(
                "Someone ({user}) from {ip} tried to inject a job {job}".format(user=session['user_id'], ip=headers['remote_ip'], job=data['job']))
        self.current = Current(session=session, input=data)
        self.current.headers = headers
        # import method
        # method = get_object_from_path(settings.BG_JOBS[data['job']])
        # call view with current object
        JOB_METHODS[data['job']](self.current)

    def _handle_view(self, session, data, headers):
        # create Current object
        self.current = Current(session=session, input=data)
        self.current.headers = headers

        # handle ping/pong/session expiration
        if data['view'] == 'ping':
            return self._handle_ping_pong(data, session)

        # handle authentication
        if not (self.current.is_auth or data['view'] in settings.ANONYMOUS_WORKFLOWS):
            return LOGIN_REQUIRED_MESSAGE

        # import view
        # view = get_object_from_path(settings.VIEW_URLS[data['view']])

        # call view with current object
        VIEW_METHODS[data['view']](self.current)

        # return output
        return self.current.output

    def _handle_workflow(self, session, data, headers):
        wf_engine.start_engine(session=session, input=data, workflow_name=data['wf'])
        wf_engine.current.headers = headers
        self.current = wf_engine.current
        wf_engine.run()
        # if self.connection.is_closed:
        #     log.info("Connection is closed, re-opening...")
        #     self.connect()
        return wf_engine.current.output

    def handle_message(self, ch, method, properties, body):
        """
        this is a pika.basic_consumer callback
        handles client inputs, runs appropriate workflows and views

        Args:
            ch: amqp channel
            method: amqp method
            properties:
            body: message body
        """
        input = {}
        headers = {}
        try:
            self.sessid = method.routing_key

            input = json_decode(body)
            data = input['data']

            # since this comes as "path" we dont know if it's view or workflow yet
            # TODO: just a workaround till we modify ui to
            if 'path' in data:
                if data['path'] in VIEW_METHODS:
                    data['view'] = data['path']
                else:
                    data['wf'] = data['path']
            session = Session(self.sessid)

            headers = {'remote_ip': input['_zops_remote_ip'],
                       'source': input['_zops_source']}

            if 'wf' in data:
                output = self._handle_workflow(session, data, headers)
            elif 'job' in data:

                self._handle_job(session, data, headers)
                return
            else:
                output = self._handle_view(session, data, headers)

        except HTTPError as e:
            import sys
            if hasattr(sys, '_called_from_test'):
                raise
            output = {"cmd": "error", "error": self._prepare_error_msg(e.message), "code": e.code}
            log.exception("Http error occurred")
        except:
            self.current = Current(session=session, input=data)
            self.current.headers = headers
            import sys
            if hasattr(sys, '_called_from_test'):
                raise
            err = traceback.format_exc()
            output = {"cmd": "error", "error": self._prepare_error_msg(err), "code": 500}
            log.exception("Worker error occurred with messsage body:\n%s" % body)
        if 'callbackID' in input:
            output['callbackID'] = input['callbackID']
        log.info("OUTPUT for %s: %s" % (self.sessid, output))
        output['reply_timestamp'] = time()
        self.send_output(output)

    def send_output(self, output):
        # TODO: This is ugly, we should separate login process
        # log.debug("SEND_OUTPUT: %s" % output)
        if self.current.user_id is None or 'login_process' in output:
            self.client_queue.send_to_default_exchange(self.sessid, output)
        else:
            self.client_queue.send_to_prv_exchange(self.current.user_id, output)


def run_workers(no_subprocess, watch_paths=None, is_background=False):
    """
    subprocess handler
    """
    import atexit, os, subprocess, signal
    if watch_paths:
        from watchdog.observers import Observer
        # from watchdog.observers.fsevents import FSEventsObserver as Observer
        # from watchdog.observers.polling import PollingObserver as Observer
        from watchdog.events import FileSystemEventHandler

    def on_modified(event):
        if not is_background:
            print("Restarting worker due to change in %s" % event.src_path)
        log.info("modified %s" % event.src_path)
        try:
            kill_children()
            run_children()
        except:
            log.exception("Error while restarting worker")

    handler = FileSystemEventHandler()
    handler.on_modified = on_modified

    # global child_pids
    child_pids = []
    log.info("starting %s workers" % no_subprocess)

    def run_children():
        global child_pids
        child_pids = []
        for i in range(int(no_subprocess)):
            proc = subprocess.Popen([sys.executable, __file__],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            child_pids.append(proc.pid)
            log.info("Started worker with pid %s" % proc.pid)

    def kill_children():
        """
        kill subprocess on exit of manager (this) process
        """
        log.info("Stopping worker(s)")
        for pid in child_pids:
            if pid is not None:
                os.kill(pid, signal.SIGTERM)

    run_children()
    atexit.register(kill_children)
    signal.signal(signal.SIGTERM, kill_children)
    if watch_paths:
        observer = Observer()
        for path in watch_paths:
            if not is_background:
                print("Watching for changes under %s" % path)
            observer.schedule(handler, path=path, recursive=True)
        observer.start()
    while 1:
        try:
            sleep(1)
        except KeyboardInterrupt:
            log.info("Keyboard interrupt, exiting")
            if watch_paths:
                observer.stop()
                observer.join()
            sys.exit(0)


if __name__ == '__main__':
    if 'manage' in str(sys.argv):
        no_subprocess = [arg.split('manage=')[-1] for arg in sys.argv if 'manage' in arg][0]
        run_workers(no_subprocess)
    else:
        worker = Worker()
        worker.run()
