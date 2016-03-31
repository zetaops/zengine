# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
from uuid import uuid4

import pika
import time
from pika.exceptions import AMQPError

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
        client_message = {'cmd': 'notification',
                          'notifications': list(self.get_all())}
        self.send_to_queue(client_message)


    def old_to_new_queue(self, old_sess_id):
        """
        Somehow if users old (obsolete) queue has
        undelivered messages, we should redirect them to
        current queue.
        """
        old_input_channel = self.connection.channel()
        while True:
            method_frame, header_frame, body = old_input_channel.basic_get(old_sess_id)
            if method_frame:
                self.send_to_queue(json_message=body)
                old_input_channel.basic_ack(method_frame.delivery_tag)
            else:
                break
        old_input_channel.queue_delete(old_sess_id)





    def send_to_queue(self, message=None, json_message=None):
        self.channel.basic_publish(exchange='',
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
