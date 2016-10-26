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
from zengine.lib.json_interface import ZEngineJSONEncoder


BLOCKING_MQ_PARAMS = pika.ConnectionParameters(
    host=settings.MQ_HOST,
    port=settings.MQ_PORT,
    virtual_host=settings.MQ_VHOST,
    heartbeat_interval=0,
    credentials=pika.PlainCredentials(settings.MQ_USER, settings.MQ_PASS)
)
from zengine.log import log

def get_mq_connection():
    connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
    channel = connection.channel()
    if not channel.is_open:
        channel.open()
    return connection, channel


class ClientQueue(object):
    """
    User AMQP queue manager
    """
    def __init__(self, user_id=None, sess_id=None):

        # self.user_id = user_id
        self.connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
        self.channel = self.connection.channel()
        # self.sess_id = sess_id

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

    def send_to_default_exchange(self, sess_id, message=None):
        """
        Send messages through RabbitMQ's default exchange,
        which will be delivered through routing_key (sess_id).

        This method only used for un-authenticated users, i.e. login process.

        Args:
            sess_id string: Session id
            message dict: Message object.
        """
        msg = json.dumps(message, cls=ZEngineJSONEncoder)
        log.debug("Sending following message to %s queue through default exchange:\n%s" % (
            sess_id, msg))
        self.get_channel().publish(exchange='', routing_key=sess_id, body=msg)

    def send_to_prv_exchange(self, user_id, message=None):
        """
        Send messages through logged in users private exchange.

        Args:
            user_id string: User key
            message dict: Message object

        """
        exchange = 'prv_%s' % user_id.lower()
        msg = json.dumps(message, cls=ZEngineJSONEncoder)
        log.debug("Sending following users \"%s\" exchange:\n%s " % (exchange, msg))
        self.get_channel().publish(exchange=exchange, routing_key='', body=msg)

