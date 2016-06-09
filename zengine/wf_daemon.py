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
from zengine.lib.exceptions import HTTPError
from zengine.log import log
import sys
# receivers should be imported at right time, right place
# they will not registered if not placed in a central location
# but they can cause "cannot import settings" errors if imported too early
from zengine.receivers import *

sys._zops_wf_state_log = ''

wf_engine = ZEngine()


class Worker(object):
    """
    Workflow runner worker object
    """
    INPUT_QUEUE_NAME = 'in_queue'
    INPUT_EXCHANGE = 'tornado_input'

    def __init__(self):
        self.connect()
        signal.signal(signal.SIGTERM, self.exit)
        log.info("Worker starting")
        print("Worker started")

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

        self.input_channel.exchange_declare(exchange=self.INPUT_EXCHANGE, type='topic')
        self.input_channel.queue_declare(queue=self.INPUT_QUEUE_NAME)
        self.input_channel.queue_bind(exchange=self.INPUT_EXCHANGE, queue=self.INPUT_QUEUE_NAME)
        log.info("Bind to queue named '%s' queue with exchange '%s'" % (self.INPUT_QUEUE_NAME, self.INPUT_EXCHANGE))

    def run(self):
        """
        actual consuming of incoming works starts here
        """
        self.input_channel.basic_consume(self.handle_message,
                                         queue=self.INPUT_QUEUE_NAME,
                                         no_ack=True)
        try:
            self.input_channel.start_consuming()
        except (KeyboardInterrupt, SystemExit):
            log.info(" Exiting")
            self.exit()

    def _prepare_error_msg(self, msg):
        try:
            return \
                msg + '\n\n' + \
                "INPUT DATA: %s\n\n" %  pformat(self.current.input) + \
                "OUTPUT DATA: %s\n\n" %  pformat(self.current.output) + \
                   sys._zops_wf_state_log
        except:
            return msg

    def _handle_view(self, session, data, headers):
        login_required_msg = {'error': "Login required", "code": 401}
        self.current = Current(session=session, input=data)
        self.current.headers = headers
        if data['view'] == 'ping':
            still_alive = KeepAlive(sess_id=session.sess_id).update_or_expire_session()
            msg = {'msg': 'pong'}
            if not still_alive:
                msg.update(login_required_msg)
            return msg
        if not (self.current.is_auth or data['view'] in settings.ANONYMOUS_WORKFLOWS):
            return login_required_msg
        view = get_object_from_path(settings.VIEW_URLS[data['view']])
        view(self.current)
        return self.current.output

    def _handle_workflow(self, session, data, headers):
        wf_engine.start_engine(session=session, input=data, workflow_name=data['wf'])
        wf_engine.current.headers = headers
        self.current = wf_engine.current
        wf_engine.run()
        if self.connection.is_closed:
            log.info("Connection is closed, re-opening...")
            self.connect()
        return wf_engine.current.output

    def handle_message(self, ch, method, properties, body):
        """
        this is a pika.basic_consumer callback
        handles client inputs, runs appropriate workflows

        Args:
            ch: amqp channel
            method: amqp method
            properties:
            body: message body
        """
        input = {}
        try:
            sessid = method.routing_key

            input = json_decode(body)
            data = input['data']

            # since this comes as "path" we dont know if it's view or workflow yet
            # just a workaround till we modify ui to
            if 'path' in data:
                if data['path'] in settings.VIEW_URLS:
                    data['view'] = data['path']
                else:
                    data['wf'] = data['path']
                session = Session(sessid[5:])  # clip "HTTP_" prefix from sessid
            else:
                session = Session(sessid)

            headers = {'remote_ip': input['_zops_remote_ip']}

            if 'wf' in data:
                output = self._handle_workflow(session, data, headers)
            else:
                output = self._handle_view(session, data, headers)
        except HTTPError as e:
            import sys
            if hasattr(sys, '_called_from_test'):
                raise
            output = {'cmd': 'error', 'error': self._prepare_error_msg(e.message), "code": e.code}
            log.exception("Http error occurred")
        except:
            import sys
            if hasattr(sys, '_called_from_test'):
                raise
            err = traceback.format_exc()
            output = {'error': self._prepare_error_msg(err), "code": 500}
            log.exception("Worker error occurred")
        if 'callbackID' in input:
            output['callbackID'] = input['callbackID']
        log.info("OUTPUT for %s: %s" % (sessid, output))
        output['reply_timestamp'] = time()
        self.send_output(output, sessid)

    def send_output(self, output, sessid):
        self.client_queue.sess_id = sessid
        self.client_queue.send_to_queue(output)
        # self.output_channel.basic_publish(exchange='',
        #                                   routing_key=sessid,
        #                                   body=json.dumps(output))
        # except ConnectionClosed:


def run_workers(no_subprocess):
    """
    subprocess handler
    """
    import atexit, os, subprocess, signal

    # global child_pids
    child_pids = []

    log.info("starting %s workers" % no_subprocess)
    for i in range(int(no_subprocess)):
        proc = subprocess.Popen([sys.executable, __file__],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        child_pids.append(proc.pid)
        log.info("Started worker with pid %s" % proc.pid)

    def kill_child(foo=None, bar=None):
        """
        kill subprocess on exit of manager (this) process
        """
        for pid in child_pids:
            if pid is not None:
                os.kill(pid, signal.SIGTERM)

    atexit.register(kill_child)
    signal.signal(signal.SIGTERM, kill_child)
    while 1:
        try:
            sleep(1)
        except KeyboardInterrupt:
            log.info("Keyboard interrupt, exiting")
            sys.exit(0)


if __name__ == '__main__':
    if 'manage' in str(sys.argv):
        no_subprocess = [arg.split('manage=')[-1] for arg in sys.argv if 'manage' in arg][0]
        run_workers(no_subprocess)
    else:
        worker = Worker()
        worker.run()
