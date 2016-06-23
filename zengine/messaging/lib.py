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



class BaseUser(object):
    connection = None
    channel = None

    def _connect_mq(self):
        if not self.connection is None or self.connection.is_closed:
            self.connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
            self.channel = self.connection.channel()
        return self.channel

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

    def pre_save(self):
        """ encrypt password if not already encrypted """
        if self.password and not self.password.startswith('$pbkdf2'):
            self.set_password(self.password)

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
        Kullanıcıya ait Role nesnesini getirir.

        Args:
            role_id (int)

        Returns:
            dict: Role nesnesi

        """
        return self.role_set.node_dict[role_id]

    @property
    def full_name(self):
        return self.username

    def send_message(self, title, message, sender=None, url=None, typ=1):
        """
        sends message to users private mq exchange
        Args:
            title:
            message:
            sender:
            url:
            typ:


        """
        mq_channel = self._connect_mq()
        mq_msg = dict(body=message, msg_title=title, url=url, typ=typ)
        if sender:
            mq_msg['sender_name'] = sender.full_name
            mq_msg['sender_key'] = sender.key

        mq_channel.basic_publish(exchange=self.key, body=json.dumps(mq_msg))
        self._write_message_to_db(sender, message, title, url, typ)

    def _write_message_to_db(self, sender, body, title, url, typ):
        from zengine.messaging.model import Channel, Message
        channel = Channel.objects.get(owner=self, is_private=True)
        Message(channel=channel, sender=sender, msg_title=title,
                body=body, receiver=self, url=url, typ=typ).save()
