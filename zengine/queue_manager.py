# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
import pika
import time
from pika.adapters import TornadoConnection, BaseConnection
from pika.exceptions import ChannelClosed, ConnectionClosed
from tornado.escape import json_decode
try:
    from zengine.log import log
except ImportError:
    import logging as log
    log.basicConfig(level=log.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename='tornado.log',
                    filemode='a')


class BlockingConnectionForHTTP(object):
    REPLY_TIMEOUT = 5

    def __init__(self):
        self.connection = pika.BlockingConnection()

    def create_channel(self):
        try:
            return self.connection.channel()
        except ConnectionClosed:
            self.connection = pika.BlockingConnection()
            return self.connection.channel()

    def wait_for_message(self, sess_id, request_id):

        channel = self.create_channel()
        channel.queue_declare(queue=sess_id,
                              auto_delete=True)
        for i in range(self.REPLY_TIMEOUT):
            method_frame, header_frame, body = channel.basic_get(sess_id)
            if method_frame:
                reply = json_decode(body)
                if 'callbackID' in reply and reply['callbackID'] == request_id:
                    channel.basic_ack(method_frame.delivery_tag)
                    log.info('Returned view message for %s: %s' % (sess_id, body))
                    return body
                log.info("XXXXXXXXX: %s" % reply)
            time.sleep(1)
        log.info('No message returned for %s' % sess_id)
        return json.dumps({'code': 503, 'error': 'Retry'})



class QueueManager(object):
    """
    Async RabbitMQ & Tornado websocket connector
    """
    INPUT_QUEUE_NAME = 'in_queue'
    def __init__(self, io_loop):
        log.info('PikaClient: __init__')
        self.io_loop = io_loop
        self.connected = False
        self.connecting = False
        self.connection = None
        self.in_channel = None
        self.out_channels = {}
        self.out_channel = None
        self.websockets = {}
        self.connect()

    def connect(self):
        """
        Creates connection to RabbitMQ server
        """
        if self.connecting:
            log.info('PikaClient: Already connecting to RabbitMQ')
            return

        log.info('PikaClient: Connecting to RabbitMQ')
        self.connecting = True

        cred = pika.PlainCredentials('guest', 'guest')
        param = pika.ConnectionParameters(
            host='localhost',
            port=5672,
            virtual_host='/',
            credentials=cred
        )

        self.connection = TornadoConnection(param,
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
        self.connection = connection
        self.in_channel = self.connection.channel(self.on_conn_open)

    def on_conn_open(self, channel):
        """
        Input channel creation callback
        Queue declaration done here

        Args:
            channel: input channel
        """
        self.in_channel.exchange_declare(exchange='tornado_input', type='topic')
        channel.queue_declare(callback=self.on_input_queue_declare, queue=self.INPUT_QUEUE_NAME)

    def on_input_queue_declare(self, queue):
        """
        Input queue declaration callback.
        Input Queue/Exchange binding done here

        Args:
            queue: input queue
        """
        self.in_channel.queue_bind(callback=None,
                           exchange='tornado_input',
                           queue=self.INPUT_QUEUE_NAME,
                           routing_key="#")

    def register_websocket(self, sess_id, ws):
        """

        Args:
            sess_id:
            ws:
        """
        self.websockets[sess_id] = ws
        channel = self.create_out_channel(sess_id)


    def unregister_websocket(self, sess_id):
        del self.websockets[sess_id]
        if sess_id in self.out_channels:
            try:
                self.out_channels[sess_id].close()
            except ChannelClosed:
                log.exception("Pika client (out) channel already closed")


    def create_out_channel(self, sess_id):
        def _on_output_channel_creation(channel):
            def _on_output_queue_decleration(queue):
                channel.basic_consume(self.on_message, queue=sess_id)
            self.out_channels[sess_id] = channel
            channel.queue_declare(callback=_on_output_queue_decleration,
                                  queue=sess_id,
                                  auto_delete=True,
                                  # exclusive=True
                                  )

        self.connection.channel(_on_output_channel_creation)


    def redirect_incoming_message(self, sess_id, message):
        self.in_channel.basic_publish(exchange='tornado_input',
                              routing_key=sess_id,
                              body=message)

    def on_message(self, channel, method, header, body):
        sess_id = method.routing_key
        if sess_id in self.websockets:
            self.websockets[sess_id].write_message(body)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        # else:
        #     channel.basic_reject(delivery_tag=method.delivery_tag)


