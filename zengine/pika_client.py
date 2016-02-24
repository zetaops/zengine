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
from pika.adapters import TornadoConnection

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
pika.log = logging.getLogger(__name__)


class PikaClient(object):
    def __init__(self, io_loop):
        pika.log.info('PikaClient: __init__')
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
        self.in_channel.exchange_declare(exchange='tornado_input', type='direct')
        # self.out_channel = self.connection.channel()

    def register_websocket(self, sess_id, ws):
        self.websockets[sess_id] = ws
        channel = self.create_out_channel(sess_id)
        channel.queue_declare(queue=sess_id, auto_delete=True)
        channel.basic_consume(self.on_message,
                              queue=sess_id,
                              # no_ack=True
                              )

    def unregister_websocket(self, sess_id):
        del self.websockets[sess_id]
        # self.in_channels["in_%s" % sess_id].close()


    def create_out_channel(self, sess_id):
        channel = self.connection.channel()
        self.out_channels[sess_id] = channel
        return channel

    def send_message(self, sess_id, message):
        # channel = self.in_channels[sess_id]
        self.in_channel.basic_publish(exchange='tornado_input',
                              routing_key='in.%s' % sess_id,
                              body=message)

    def on_message(self, channel, method, header, body):
        sess_id = method.routing_key
        if sess_id in self.websockets:
            self.websockets[sess_id].write(body)
            channel.basic.ack(delivery_tag=header['delivery_tag'])
        else:
            channel.basic_reject(delivery_tag=header['delivery_tag'])


