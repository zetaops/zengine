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
from pika.exceptions import AMQPError

from zengine.lib.cache import Cache, UserSessionID
from zengine.tornado_server.queue_manager import MQ_PARAMS


class Notify(Cache):
    """
    Cache based simple notification object.
    """
    PREFIX = 'NTFY'

    TaskInfo = 1
    TaskError = 11
    TaskSuccess = 111
    Message = 2
    Broadcast = 3

    def __init__(self, user_id):
        super(Notify, self).__init__(str(user_id))
        self.connection = pika.BlockingConnection(MQ_PARAMS)
        self.channel = self.connection.channel()
        self.sess_id = UserSessionID(user_id).get()

    def set_message(self, title, msg, typ, url=None):
        message_id = uuid4().hex
        message = {'title': title, 'body': msg, 'type': typ,
                   'url': url, 'id': message_id}

        try:
            client_message = {'cmd': 'notification',
                              'notifications': [message, ]}
            self.channel.basic_publish(exchange='',
                                       routing_key=self.sess_id,
                                       body=json.dumps(client_message))
        except AMQPError:
            self.add(message)

        return message_id
