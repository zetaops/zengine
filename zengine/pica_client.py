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
logger = logging.getLogger(__name__)


class PikaClient(object):
    def __init__(self, io_loop):
        pika.log.info('PikaClient: __init__')
        self.io_loop = io_loop

        self.connected = False
        self.connecting = False
        self.connection = None
        # self.channel = None

        # self.event_listeners = set([])
        self.in_channels = {}
        self.out_channels = {}
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
        self.connection.channel(self.on_channel_open)

    def on_channel_open(self, channel):
        pika.log.info('PikaClient: Channel open, Declaring exchange')
        self.channel = channel
        # declare exchanges, which in turn, declare
        # queues, and bind exchange to queues

    # def on_closed(self, connection):
    #     pika.log.info('PikaClient: rabbit connection closed')
    #     self.io_loop.stop()

    def register_websocket(self, sess_id, ws):
        self.websockets[sess_id] = ws
        self.create_channel(sess_id)

    def unregister_websocket(self, sess_id):
        del self.websockets[sess_id]
        self.in_channels["in_%s" % sess_id].close()


    def create_channel(self, sessid):
        channel = self.connection.channel()
        self.in_channels[sessid] = channel
        return channel

    def send_message(self, sessid, message):
        channel = self.in_channels[sessid]
        channel.basic_publish(exchange='',
                              routing_key='in.%s' % sessid,
                              body=message)

    def on_message(self, channel, method, header, body):
        pika.log.info('PikaClient: message received: %s' % body)
        self.notify_listeners(body)

        # def notify_listeners(self, event_obj):
        #     # here we assume the message the sourcing app
        #     # post to the message queue is in JSON format
        #     event_json = json.dumps(event_obj)
        #
        #     for listener in self.event_listeners:
        #         listener.write_message(event_json)
        #         pika.log.info('PikaClient: notified %s' % repr(listener))
        #
        # def add_event_listener(self, listener):
        #     self.event_listeners.add(listener)
        #     pika.log.info('PikaClient: listener %s added' % repr(listener))
        #
        # def remove_event_listener(self, listener):
        #     try:
        #         self.event_listeners.remove(listener)
        #         pika.log.info('PikaClient: listener %s removed' % repr(listener))
        #     except KeyError:
        #         pass
