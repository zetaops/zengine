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
from zengine.client_queue import BLOCKING_MQ_PARAMS, get_mq_connection
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
            cls.mq_connection, cls.mq_channel = get_mq_connection()
        return cls.mq_channel

    def get_avatar_url(self):
        """
        Bu metot kullanıcıya ait avatar url'ini üretir.

        Returns:
            str: kullanıcı avatar url
        """
        if self.avatar:
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
        # if not self.key:
            # FIXME: This should not happen!
            # return
        if status is None:
            return ConnectionStatus(self.key).get() or False
        else:
            mq_channel = self._connect_mq()
            for sbs in self.subscriptions.objects.all():
                if sbs.channel.typ == 10:
                    other_party = self.get_prv_exchange(
                        sbs.channel.code_name.replace(self.key, '').replace('_', ''))
                    mq_channel.basic_publish(exchange=other_party,
                                             routing_key='',
                                             body=json.dumps({
                                                 'cmd': 'user_status',
                                                 'channel_key': sbs.channel.key,
                                                 'channel_name': sbs.name,
                                                 'avatar_url': self.get_avatar_url(),
                                                 'is_online': status,
                                             }))
            ConnectionStatus(self.key).set(status)

    def encrypt_password(self):
        """ encrypt password if not already encrypted """
        if self.password and not self.password.startswith('$pbkdf2'):
            self.set_password(self.password)

    def prepare_channels(self):
        from zengine.messaging.model import Channel, Subscriber
        # create private channel of user
        ch, new_ch = Channel.objects.get_or_create(owner=self, typ=5)
        # create subscription entry for notification messages
        sb, new_sb = Subscriber.objects.get_or_create(
            channel=ch,
            user=self,
            read_only=True,
            name='Notifications',
            defaults=dict(can_manage=True, can_leave=False, inform_me=False)
        )

        return ch, new_ch, sb, new_sb

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
        return self.get_prv_exchange(self.key)

    @staticmethod
    def get_prv_exchange(key):
        return 'prv_%s' % str(key).lower()

    def bind_private_channel(self, sess_id):
        mq_channel = self._connect_mq()
        mq_channel.queue_declare(queue=sess_id, arguments={'x-expires': 40000})
        log.debug("Binding private exchange to client queue: Q:%s --> E:%s" % (sess_id,
                                                                               self.prv_exchange))
        mq_channel.queue_bind(exchange=self.prv_exchange, queue=sess_id)

    def unbind_private_channel(self, sess_id):
        mq_channel = self._connect_mq()
        log.debug("Unbinding existing queue from private exchange: Q:%s --> E:%s" % (sess_id,
                                                                               self.prv_exchange))
        mq_channel.queue_unbind(queue=sess_id, exchange=self.prv_exchange)

    def send_notification(self, title, message, typ=1, url=None, sender=None):
        """
        sends message to users private mq exchange
        Args:
            title:
            message:
            sender:
            url:
            typ:
        """
        self.created_channels.channel.add_message(
            channel_key=self.prv_exchange,
            body=message,
            title=title,
            typ=typ,
            url=url,
            sender=sender,
            receiver=self
        )

    def send_client_cmd(self, data, cmd=None, via_queue=None):
        """
        Send arbitrary cmd and data to client

        if queue name passed by "via_queue" parameter,
        that queue will be used instead of users private exchange.
        Args:
            data: dict
            cmd: string
            via_queue: queue name,
        """
        mq_channel = self._connect_mq()
        if cmd:
            data['cmd'] = cmd
        if via_queue:
            mq_channel.basic_publish(exchange='',
                                     routing_key=via_queue,
                                     body=json.dumps(data))
        else:
            mq_channel.basic_publish(exchange=self.prv_exchange,
                                     routing_key='',
                                     body=json.dumps(data))
