# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
import threading
from uuid import uuid4

import os, sys

sys.sessid_to_userid = {}
import pika
import time
from pika.exceptions import ConnectionClosed

try:
    from .get_logger import get_logger
except:
    from get_logger import get_logger

settings = type('settings', (object,), {
    'LOG_HANDLER': os.environ.get('LOG_HANDLER', 'file'),
    'LOG_FILE': os.environ.get('TORNADO_LOG_FILE', 'tornado.log'),
    'LOG_LEVEL': os.environ.get('LOG_LEVEL', 'DEBUG'),
    'MQ_HOST': os.environ.get('MQ_HOST', 'localhost'),
    'MQ_PORT': int(os.environ.get('MQ_PORT', '5672')),
    'MQ_USER': os.environ.get('MQ_USER', 'guest'),
    'MQ_PASS': os.environ.get('MQ_PASS', 'guest'),
    'DEBUG': bool(int(os.environ.get('DEBUG', 0))),
    'MQ_VHOST': os.environ.get('MQ_VHOST', '/'),
    'ALLOWED_ORIGINS': os.environ.get('ALLOWED_ORIGINS', 'http://127.0.0.1'),
})
log = get_logger(settings)

BLOCKING_MQ_PARAMS = pika.ConnectionParameters(
    host=settings.MQ_HOST,
    port=settings.MQ_PORT,
    virtual_host=settings.MQ_VHOST,
    heartbeat_interval=0,
    credentials=pika.PlainCredentials(settings.MQ_USER, settings.MQ_PASS)
)

WORKER_TIMEOUT = 60

class RpcClient(object):
    internal_lock = threading.Lock()

    def __init__(self):


        self.exchange = 'output_exc'
        self.exchange_declared = False
        self.connection = None
        self.channel = None

        log.info("connection for rpc... __init__")

        self.open_connection()
        thread = threading.Thread(target=self._process_data_events)
        thread.setDaemon(True)
        thread.start()
        log.info("a new thread started for rpc data events... __init__")

    def _process_data_events(self):
        """
        In order to come over the "ERROR:pika.adapters.base_connection:Socket Error on fd 34: 104"
        adapted from:
            https://github.com/pika/pika/issues/439
            https://github.com/pika/pika/issues/439#issuecomment-36452519
            https://github.com/eandersson/python-rabbitmq-examples/blob/master/Flask-examples/pika_async_rpc_example.py
        """
        log.info("start to consume {}".format(self.callback_queue))
        self.channel.basic_consume(self.on_response, no_ack=True,
                                   queue=self.callback_queue)

        while True:
            with self.internal_lock:
                # log.info("process data events.... .... ... ")
                self.connection.process_data_events()
            time.sleep(0.05)

    def open_connection(self):
        """
        Connect to RabbitMQ.
        """

        if not self.connection or self.connection.is_closed:
            log.info("create a new connection for rpc... __open_connection__")
            self.connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)

        if not self.channel or self.channel.is_closed:
            log.info("open a new channel for rpc... __open_connection__")
            self.channel = self.connection.channel()

        if not self.exchange_declared:
            log.info("exchange declared for rpc... __open_connection__ {}".format(self.exchange))
            self.channel.exchange_declare(exchange=self.exchange, exchange_type='topic', durable=True,
                                          auto_delete=False)
            self.exchange_declared = True

        result = self.channel.queue_declare(exclusive=True)
        self.callback_queue = result.method.queue
        log.info("queue declared for rpc... __open_connection__ {}".format(self.callback_queue))

    def close_connection(self):
        """
        Close active connection.
        """

        if self.channel:
            self.channel.close()

        if self.connection:
            self.connection.close()

        self.connection, self.channel = None, None

    def on_response(self, ch, method, props, body):
        log.info('Got a new response, Corr ID: {} / Self Corr: {}'.format(props.correlation_id, self.corr_id))
        if self.corr_id == props.correlation_id:
            self.response = json.loads(body)

    def rpc_call(self, message, blocking=True, time_limit=WORKER_TIMEOUT):
        self.response = None
        self.corr_id = str(uuid4())

        try:
            if not self.connection or self.connection.is_closed or not self.channel or self.channel.is_closed:
                with self.internal_lock:
                    self.open_connection()

            with self.internal_lock:
                self.channel.basic_publish(
                    exchange='input_exc',
                    routing_key='rpc_call',
                    properties=pika.BasicProperties(
                        # delivery_mode=1,
                        reply_to=self.callback_queue,
                        correlation_id=self.corr_id,
                    ),
                    body=json.dumps(message, ensure_ascii=False),
                    # mandatory=1,
                )
                log.info('Publish rpc call. Self Corr ID: {}'.format(self.corr_id))

        except ConnectionClosed:
            with self.internal_lock:
                self.close_connection()
                self.open_connection()
            return self.rpc_call(message=message, blocking=blocking, time_limit=time_limit)

        except Exception as e:
            self.response = {"error": {"code": -32603, "message": "Can not connect AMQP or another error occured!"}, }
            self.close_connection()

        deadline = time.time() + time_limit

        while self.response is None:
            time_limit = deadline - time.time()
            if time_limit <= 0:
                self.response = {"error": {"code": -32003, "message": "Worker timeout"}, }

        return self.response

