# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
from thread import start_new_thread
from uuid import uuid4

import pika
import time
from pika.exceptions import AMQPError, ConnectionClosed, ChannelClosed

from zengine.lib.cache import Cache, UserSessionID, KeepAlive
from zengine.tornado_server.queue_manager import MQ_PARAMS


class Notify(Cache):
    """
    Cache based simple notification object.
    """
    PREFIX = 'NTFY'
    EXPIRE_TIME = 120

    TaskInfo = 1
    TaskError = 11
    TaskSuccess = 111
    Message = 2
    Broadcast = 3

    def __init__(self, user_id):
        super(Notify, self).__init__(str(user_id))
        self.user_id = user_id
        self.connection = pika.BlockingConnection(MQ_PARAMS)
        self.channel = self.connection.channel()
        self.sess_id = None

    def get_channel(self):
        if self.channel.is_closed or self.channel.is_closing:
            try:
                self.channel = pika.BlockingConnection(MQ_PARAMS)
            except (ConnectionClosed, AttributeError, KeyError):
                self.connection = pika.BlockingConnection(MQ_PARAMS)
                self.channel = pika.BlockingConnection(MQ_PARAMS)
        return self.channel

    def get_sess_id(self):
        if not self.sess_id:
            self.sess_id = UserSessionID(self.user_id).get()
        return self.sess_id

    def cache_to_queue(self):
        """
        Messages that sent to offline users
        are stored in cache, when user become online,
        stored messages redirected to user's queue.
        """
        offline_messages = list(self.get_all())
        print("OFFF: %s" % offline_messages)
        start_new_thread(self._delayed_send, (offline_messages,))


    def _delayed_send(self, offline_messages):
        time.sleep(3)
        client_message = {'cmd': 'notification',
                          'notifications': offline_messages}
        self.send_to_queue(client_message)
        for n in offline_messages:
            self.remove_item(n)

    def old_to_new_queue(self, old_sess_id):
        """
        Somehow if users old (obsolete) queue has
        undelivered messages, we should redirect them to
        current queue.
        """
        old_input_channel = self.connection.channel()
        while True:
            try:
                method_frame, header_frame, body = old_input_channel.basic_get(old_sess_id)
                if method_frame:
                    self.send_to_queue(json_message=body)
                    old_input_channel.basic_ack(method_frame.delivery_tag)
                else:
                    old_input_channel.queue_delete(old_sess_id)
                    old_input_channel.close()
                    break
            except ChannelClosed as e:
                if e[0] == 404:
                    break
                    # e => (404, "NOT_FOUND - no queue 'sess_id' in vhost '/'")
                else:
                    raise
                    # old_input_channel = self.connection.channel()


    def send_to_queue(self, message=None, json_message=None):
        self.get_channel().basic_publish(exchange='',
                                         routing_key=self.get_sess_id(),
                                         body=json_message or json.dumps(message))


    def set_message(self, title, msg, typ, url=None):
        message = {'title': title, 'body': msg, 'type': typ, 'url': url, 'id': uuid4().hex}

        if KeepAlive(user_id=self.user_id).is_alive():
            client_message = {'cmd': 'notification', 'notifications': [message, ]}
            self.send_to_queue(client_message)
        else:
            self.add(message)

        return message['id']
