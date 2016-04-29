# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json

from pyoko.conf import settings
import pika
import time
from pika.exceptions import ConnectionClosed, ChannelClosed

from zengine.lib.cache import UserSessionID

BLOCKING_MQ_PARAMS = pika.ConnectionParameters(
    host=settings.MQ_HOST,
    port=settings.MQ_PORT,
    virtual_host=settings.MQ_VHOST,
    heartbeat_interval=0,
    credentials=pika.PlainCredentials(settings.MQ_USER, settings.MQ_PASS)
)


class ClientQueue(object):
    """
    User AMQP queue manager
    """
    def __init__(self, user_id=None, sess_id=None):

        self.user_id = user_id
        self.connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
        self.channel = self.connection.channel()
        self.sess_id = sess_id

    def close(self):
        self.channel.close()
        self.connection.close()

    def get_channel(self):
        if self.channel.is_closed or self.channel.is_closing:
            try:
                self.channel = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
            except (ConnectionClosed, AttributeError, KeyError):
                self.connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
                self.channel = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
        return self.channel

    def get_sess_id(self):
        if not self.sess_id:
            self.sess_id = UserSessionID(self.user_id).get()
        return self.sess_id

    def send_to_queue(self, message=None, json_message=None):
        self.get_channel().basic_publish(exchange='',
                                         routing_key=self.get_sess_id(),
                                         body=json_message or json.dumps(message))

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
