# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json

import pika
from passlib.handlers.pbkdf2 import pbkdf2_sha512

from pyoko.conf import settings
from zengine.client_queue import BLOCKING_MQ_PARAMS
from zengine.lib.cache import Cache
from zengine.log import log


class ConnectionStatus(Cache):
    """
    Cache object for workflow instances.

    Args:
        wf_token: Token of the workflow instance.
    """
    PREFIX = 'ONOFF'

    def __init__(self, user_id):
        super(ConnectionStatus, self).__init__(user_id)


class BaseUser(object):
    mq_connection = None
    mq_channel = None

    @classmethod
    def _connect_mq(cls):
        if cls.mq_connection is None or cls.mq_connection.is_closed:
            cls.mq_connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
            cls.mq_channel = cls.mq_connection.channel()
        return cls.mq_channel

    def get_avatar_url(self):
        """
        Bu metot kullanıcıya ait avatar url'ini üretir.

        Returns:
            str: kullanıcı avatar url
        """
        return "%s%s" % (settings.S3_PUBLIC_URL, self.avatar)

    def __unicode__(self):
        return "User %s" % self.username

    def set_password(self, raw_password):
        """
        Kullanıcı şifresini encrypt ederek set eder.

        Args:
            raw_password (str)
        """
        self.password = pbkdf2_sha512.encrypt(raw_password, rounds=10000,
                                              salt_size=10)

    def is_online(self, status=None):
        if status is None:
            return ConnectionStatus(self.key).get() or False
        ConnectionStatus(self.key).set(status)


    def encrypt_password(self):
        """ encrypt password if not already encrypted """
        if self.password and not self.password.startswith('$pbkdf2'):
            self.set_password(self.password)

    def prepare_user_channel(self):
        """should be called from User.post_creation hook"""
        from zengine.messaging.model import Channel, Subscriber
        # create private channel of user
        ch, new = Channel.objects.get_or_create(owner=self, typ=5)
        # create subscription entry for notification messages
        sb, new = Subscriber.objects.get_or_create(channel=ch, user=self, is_visible=True,
                                                   can_leave=False, inform_me=False)

    def check_password(self, raw_password):
        """
        Verilen encrypt edilmemiş şifreyle kullanıcıya ait encrypt
        edilmiş şifreyi karşılaştırır.

        Args:
            raw_password (str)

        Returns:
             bool: Değerler aynı olması halinde True, değilse False
                döner.
        """
        return pbkdf2_sha512.verify(raw_password, self.password)

    def get_role(self, role_id):
        """
        Retrieves user's roles.

        Args:
            role_id (int)

        Returns:
            dict: Role nesnesi

        """
        return self.role_set.node_dict[role_id]

    @property
    def full_name(self):
        return self.username

    @property
    def prv_exchange(self):
        return 'prv_%s' % str(self.key).lower()

    def bind_channels_to_session_queue(self, sess_id):
        mq_channel = pika.BlockingConnection(BLOCKING_MQ_PARAMS).channel()
        mq_channel.queue_declare(queue=sess_id, arguments={'x-expires': 40000})
        log.debug("Binding private exchange to client queue: Q:%s --> E:%s" % (sess_id,
                                                                               self.prv_exchange))
        for sbs in self.subscriptions.objects.filter():
            mq_channel.queue_bind(exchange=sbs.channel.code_name, queue=sess_id)

    def send_notification(self, title, message, typ=1, url=None):
        """
        sends message to users private mq exchange
        Args:
            title:
            message:
            sender:
            url:
            typ:


        """
        self.channel_set.channel.__class__.add_message(
            channel_key=self.prv_exchange,
            body=message,
            title=title,
            typ=typ,
            url=url
        )
