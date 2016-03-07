#!/usr/bin/env python
"""
workflow worker daemon
"""
import json
import traceback

import signal
from time import sleep

import pika
from pika.exceptions import ConnectionClosed
from tornado.escape import json_decode

from zengine.engine import ZEngine
from zengine.lib.cache import Session
from zengine.models import Permission

import sys

wf_engine = ZEngine()

class Worker(object):
    """
    Workflow runner worker object
    """
    INPUT_QUEUE_NAME = 'in_queue'
    def __init__(self):
        self.connect()
        signal.signal(signal.SIGTERM, self.exit)

    def exit(self, signal=None, frame=None):
        """
        Properly close the AMQP connections
        """
        self.input_channel.close()
        self.output_channel.close()
        self.connection.close()
        sys.exit(0)



    def connect(self):
        """
        make amqp connection and create channels and queue binding
        """
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.output_channel = self.connection.channel()
        self.input_channel = self.connection.channel()

        self.input_channel.exchange_declare(exchange='tornado_input', type='topic')
        self.input_channel.queue_declare(queue=self.INPUT_QUEUE_NAME)
        self.input_channel.queue_bind(exchange='tornado_input', queue=self.INPUT_QUEUE_NAME)

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
            print(" Exiting")
            self.exit()



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
        sessid = method.routing_key
        session = Session(sessid)
        input = json_decode(body)
        try:
            wf_engine.start_engine(session=session, input=input, workflow_name=input['wf'])
            wf_engine.run()
            if self.connection.is_closed:
                print("Connection is closed, re-opening...")
                self.connect()
            output = wf_engine.current.output
        except:
            err = traceback.format_exc()
            output = {'error': err, "code": 500}
            print(traceback.format_exc())
        if 'callbackID' in input:
            output['callbackID'] = input['callbackID']
        self.output_channel.basic_publish(exchange='',
                                         routing_key=sessid,
                                         body=json.dumps(output))
        # except ConnectionClosed:


def run_workers(no_subprocess):
    """
    subprocess handler
    """
    import atexit, os, subprocess, signal

    # global child_pids
    child_pids = []

    print("starting %s workers" % no_subprocess)
    for i in range(int(no_subprocess)):
        proc = subprocess.Popen([sys.executable, __file__],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        child_pids.append(proc.pid)
        print("Started worker with pid %s" % proc.pid)

    def kill_child():
        """
        kill subprocess on exit of manager (this) process
        """
        for pid in child_pids:
            if pid is not None:
                os.kill(pid, signal.SIGTERM)



    atexit.register(kill_child)
    while 1:
        try:
            sleep(1)
        except KeyboardInterrupt:
            print("Keyboard interrupt, exiting")
            sys.exit(0)




if __name__ == '__main__':
    if 'manage' in str(sys.argv):
        no_subprocess = [arg.split('manage=')[-1] for arg in sys.argv if 'manage' in arg][0]
        run_workers(no_subprocess)
    else:
        worker = Worker()
        worker.run()

