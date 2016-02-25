# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
import logging

import pika
import time
from pika.adapters import TornadoConnection

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
pika.log = logging.getLogger(__name__)


class PikaClient(object):
    INPUT_QUEUE_NAME = 'in_queue'
    def __init__(self, io_loop):
        pika.log.info('PikaClient: __init__')
        self.io_loop = io_loop
        self.received_message_counter = 0
        self.sent_message_counter = 0
        self.start_time = -1
        self.connected = False
        self.connecting = False
        self.connection = None
        self.in_channel = None
        self.out_channels = {}
        self.out_channel = None
        self.websockets = {}
        self.connect()

    def connect(self):
        if self.connecting:
            pika.log.info('PikaClient: Already connecting to RabbitMQ')
            return

        pika.log.info('PikaClient: Connecting to RabbitMQ')
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
        # self.connection.add_on_close_callback(self.on_closed)

    def on_connected(self, connection):
        pika.log.info('PikaClient: connected to RabbitMQ')
        self.connected = True
        self.connection = connection
        self.in_channel = self.connection.channel(self.on_open)

    def on_open(self, channel):
        self.in_channel.exchange_declare(exchange='tornado_input', type='topic')
        channel.queue_declare(callback=self.on_queue_declare, queue=self.INPUT_QUEUE_NAME)

    def on_queue_declare(self, queue):
        self.in_channel.queue_bind(callback=None,
                           exchange='tornado_input',
                           queue=self.INPUT_QUEUE_NAME,
                           routing_key="#")

    def register_websocket(self, sess_id, ws):
        self.websockets[sess_id] = ws
        channel = self.create_out_channel(sess_id)


    def unregister_websocket(self, sess_id):
        del self.websockets[sess_id]
        if sess_id in self.out_channels:
            self.out_channels[sess_id].close()
        print("Time: %s, Total In: %s Out: %s" % (int(time.time() - self.start_time),
                                                  self.received_message_counter,
                                                  self.sent_message_counter) )


    def create_out_channel(self, sess_id):
        def on_output_channel_creation(channel):
            def on_output_queue_decleration(queue):
                channel.basic_consume(self.on_message, queue=sess_id)
            self.out_channels[sess_id] = channel
            channel.queue_declare(callback=on_output_queue_decleration,
                                  queue=sess_id,
                                  auto_delete=True,
                                  exclusive=True)

        self.connection.channel(on_output_channel_creation)


    def send_message(self, sess_id, message):
        if not self.sent_message_counter:
            self.start_time = time.time()
        self.received_message_counter += 1
        self.in_channel.basic_publish(exchange='tornado_input',
                              routing_key='in.%s' % sess_id,
                              body=message)

    def on_message(self, channel, method, header, body):
        self.sent_message_counter += 1
        sess_id = method.routing_key
        if sess_id in self.websockets:
            self.websockets[sess_id].write_message(body)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        else:
            channel.basic_reject(delivery_tag=method.delivery_tag)


