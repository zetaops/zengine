# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
from uuid import uuid4

import os, sys
sys.sessid_to_userid = {}
import pika
import time
from pika.adapters import TornadoConnection, BaseConnection
from pika.exceptions import ChannelClosed, ConnectionClosed
from tornado.escape import json_decode, json_encode

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

NON_BLOCKING_MQ_PARAMS = pika.ConnectionParameters(
    host=settings.MQ_HOST,
    port=settings.MQ_PORT,
    virtual_host=settings.MQ_VHOST,
    credentials=pika.PlainCredentials(settings.MQ_USER, settings.MQ_PASS)
)


class QueueManager(object):
    """
    Async RabbitMQ & Tornado websocket connector
    """
    INPUT_QUEUE_NAME = 'in_queue'

    def __init__(self, io_loop=None):
        log.info('PikaClient: __init__')
        self.io_loop = io_loop
        self.connected = False
        self.connecting = False
        self.connection = None
        self.in_channel = None
        self.out_channels = {}
        self.out_channel = None
        self.websockets = {}
        # self.connect()

    def connect(self):
        """
        Creates connection to RabbitMQ server
        """
        if self.connecting:
            log.info('PikaClient: Already connecting to RabbitMQ')
            return

        log.info('PikaClient: Connecting to RabbitMQ')
        self.connecting = True

        self.connection = TornadoConnection(NON_BLOCKING_MQ_PARAMS,
                                            stop_ioloop_on_close=False,
                                            custom_ioloop=self.io_loop,
                                            on_open_callback=self.on_connected)

    def on_connected(self, connection):
        """
        AMQP connection callback.
        Creates input channel.

        Args:
            connection: AMQP connection
        """
        log.info('PikaClient: connected to RabbitMQ')
        self.connected = True
        self.in_channel = self.connection.channel(self.on_channel_open)

    def on_channel_open(self, channel):
        """
        Input channel creation callback
        Queue declaration done here

        Args:
            channel: input channel
        """
        self.in_channel.exchange_declare(exchange='input_exc', type='topic', durable=True)
        channel.queue_declare(callback=self.on_input_queue_declare, queue=self.INPUT_QUEUE_NAME)

    def on_input_queue_declare(self, queue):
        """
        Input queue declaration callback.
        Input Queue/Exchange binding done here

        Args:
            queue: input queue
        """
        self.in_channel.queue_bind(callback=None,
                                   exchange='input_exc',
                                   queue=self.INPUT_QUEUE_NAME,
                                   routing_key="#")



    def register_websocket(self, sess_id, ws):
        """

        Args:
            sess_id:
            ws:
        """
        self.websockets[sess_id] = ws
        self.create_out_channel(sess_id)

    def inform_disconnection(self, sess_id):
        self.in_channel.basic_publish(exchange='input_exc',
                                      routing_key=sess_id,
                                      body=json_encode(dict(data={
                                          'view': '_zops_mark_offline_user',
                                          'sess_id': sess_id,},
                                          _zops_source= 'Internal',
                                          _zops_remote_ip='')))

        self.websockets[sess_id].write_message(json.dumps({"cmd": "status", "status": "closing"}))

    def unregister_websocket(self, sess_id):
        # user_id = sys.sessid_to_userid.get(sess_id, None)
        try:
            self.inform_disconnection(sess_id)
            del self.websockets[sess_id]
        except KeyError:
            log.exception("Non-existent websocket for %s" % sess_id)
        if sess_id in self.out_channels:
            try:
                self.out_channels[sess_id].close()
            except ChannelClosed:
                log.exception("Pika client (out) channel already closed")

    def create_out_channel(self, sess_id):
        def _on_output_channel_creation(channel):
            def _on_output_queue_decleration(queue):
                # differentiate and identify incoming message with registered consumer
                channel.basic_consume(self.on_message,
                                      queue=sess_id,
                                      consumer_tag=sess_id,
                                      # no_ack=True
                                      )
                log.debug("BINDED QUEUE TO WS Q.%s" % sess_id)
            self.out_channels[sess_id] = channel

            channel.queue_declare(callback=_on_output_queue_decleration,
                                  queue=sess_id,
                                  arguments={'x-expires': 40000},
                                  # auto_delete=True,
                                  # exclusive=True
                                  )

        self.connection.channel(_on_output_channel_creation)


    def redirect_incoming_message(self, sess_id, message, request):
        message = json_decode(message)
        message['_zops_sess_id'] = sess_id
        message['_zops_remote_ip'] = request.remote_ip
        message['_zops_source'] = 'Remote'
        self.in_channel.basic_publish(exchange='input_exc',
                                      routing_key=sess_id,
                                      body=json_encode(message))

    def on_message(self, channel, method, header, body):
        sess_id = method.consumer_tag
        log.debug("WS RPLY for %s" % sess_id)
        log.debug("WS BODY for %s" % body)
        try:
            if sess_id in self.websockets:
                log.info("write msg to client")
                self.websockets[sess_id].write_message(body)
                log.debug("WS OBJ %s" % self.websockets[sess_id])
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except RuntimeError:
            log.exception("CANT WRITE TO HTTP OR WS: %s\n \n%s" % (sess_id, body))
        except KeyError:
            self.unregister_websocket(sess_id)
            log.exception("CANT FIND WS OR HTTP: %s" % sess_id)
