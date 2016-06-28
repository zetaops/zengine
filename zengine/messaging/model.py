# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json

import pika

from pyoko import Model, field, ListNode
from pyoko.conf import settings
from pyoko.exceptions import IntegrityError
from pyoko.lib.utils import get_object_from_path
from zengine.client_queue import BLOCKING_MQ_PARAMS
from zengine.lib.utils import to_safe_str

UserModel = get_object_from_path(settings.USER_MODEL)


def get_mq_connection():
    connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
    channel = connection.channel()
    return connection, channel


# CHANNEL_TYPES = (
#     (1, "Notification"),
# (10, "System Broadcast"),
# (20, "Chat"),
# (25, "Direct"),
# )


class Channel(Model):
    """
    Represents MQ exchanges.

    is_private: Represents users exchange hub
    Each user have a durable private exchange,
     which their code_name composed from user key prefixed with "prv_"

    is_direct: Represents a user-to-user direct message exchange
    """
    channel = None
    connection = None

    name = field.String("Name")
    code_name = field.String("Internal name")
    description = field.String("Description")
    owner = UserModel(reverse_name='created_channels')
    # is this users private exchange
    is_private = field.Boolean()
    # is this a One-To-One channel
    is_direct = field.Boolean()

    # typ = field.Integer("Type", choices=CHANNEL_TYPES)

    class Meta:
        unique_together = (('is_private', 'owner'),)

    class Managers(ListNode):
        user = UserModel(reverse_name='managed_channels')

    @classmethod
    def get_or_create_direct_channel(cls, initiator, receiver):
        """
        Creates a  direct messaging channel between two user

        Args:
            initiator: User, who sent the first message
            receiver: User, other party

        Returns:
            Channel
        """
        existing = cls.objects.OR().filter(
            code_name='%s_%s' % (initiator.key, receiver.key)).filter(
            code_name='%s_%s' % (receiver.key, initiator.key))
        if existing:
            return existing[0]
        else:
            channel_name = '%s_%s' % (initiator.key, receiver.key)
            channel = cls(is_direct=True, code_name=channel_name).save()
            Subscriber(channel=channel, user=initiator).save()
            Subscriber(channel=channel, user=receiver).save()
            return channel

    def add_message(self, body, title=None, sender=None, url=None, typ=2, receiver=None):
        mq_channel = self._connect_mq()
        mq_msg = json.dumps(dict(sender=sender, body=body, msg_title=title, url=url, typ=typ))
        mq_channel.basic_publish(exchange=self.code_name, body=mq_msg)
        return Message(sender=sender, body=body, msg_title=title, url=url,
                       typ=typ, channel=self, receiver=receiver).save()

    def get_last_messages(self):
        # TODO: Refactor this with RabbitMQ Last Cached Messages exchange
        return self.message_set.objects.filter()[:20]

    @classmethod
    def _connect_mq(cls):
        if cls.connection is None or cls.connection.is_closed:
            cls.connection, cls.channel = get_mq_connection()
        return cls.channel

    def create_exchange(self):
        """
        Creates MQ exchange for this channel
        Needs to be defined only once.
        """
        channel = self._connect_mq()
        channel.exchange_declare(exchange=self.code_name, exchange_type='fanout', durable=True)

    def pre_creation(self):
        if not self.code_name:
            if self.name:
                self.code_name = to_safe_str(self.name)
                return
            if self.owner and self.is_private:
                self.code_name = "prv_%s" % to_safe_str(self.owner.key)
                return
            raise IntegrityError('Non-private and non-direct channels should have a "name".')

    def post_creation(self):
        self.create_exchange()


class Subscriber(Model):
    """
    Permission model
    """

    channel = Channel()
    user = UserModel(reverse_name='subscriptions')
    is_muted = field.Boolean("Mute the channel")
    inform_me = field.Boolean("Inform when I'm mentioned", default=True)
    visible = field.Boolean("Show under user's channel list", default=True)
    can_leave = field.Boolean("Membership is not obligatory", default=True)

    # status = field.Integer("Status", choices=SUBSCRIPTION_STATUS)

    @classmethod
    def _connect_mq(cls):
        if cls.connection is None or cls.connection.is_closed:
            cls.connection, cls.channel = get_mq_connection()
        return cls.channel

    def unread_count(self):
        # FIXME: track and return actual unread message count
        return 0

    def create_exchange(self):
        """
        Creates user's private exchange
        Actually needed to be defined only once.
        but since we don't know if it's exists or not
        we always call it before binding it to related channel
        """
        channel = self._connect_mq()
        channel.exchange_declare(exchange=self.user.key, exchange_type='fanout', durable=True)

    def bind_to_channel(self):
        """
        Binds (subscribes) users private exchange to channel exchange
        Automatically called at creation of subscription record.
        """
        channel = self._connect_mq()
        channel.exchange_bind(source=self.channel.code_name, destination=self.user.key)

    def post_creation(self):
        self.create_exchange()
        self.bind_to_channel()

    def __unicode__(self):
        return "%s in %s" % (self.user, self.channel.name)


MSG_TYPES = (
    (1, "Info Notification"),
    (11, "Error Notification"),
    (111, "Success Notification"),
    (2, "Direct Message"),
    (3, "Broadcast Message"),
    (4, "Channel Message")
)
MESSAGE_STATUS = (
    (1, "Created"),
    (11, "Transmitted"),
    (22, "Seen"),
    (33, "Read"),
    (44, "Archived"),

)


class Message(Model):
    """
    Permission model
    """
    channel = Channel()
    sender = UserModel(reverse_name='sent_messages')
    receiver = UserModel(reverse_name='received_messages')
    typ = field.Integer("Type", choices=MSG_TYPES)
    status = field.Integer("Status", choices=MESSAGE_STATUS)
    msg_title = field.String("Title")
    body = field.String("Body")
    url = field.String("URL")

    def get_actions_for(self, user):
        actions = [
            ('Favorite', 'favorite_message')
        ]
        if self.sender == user:
            actions.extend([
                ('Delete', 'delete_message'),
                ('Edit', 'delete_message')
            ])
        else:
            actions.extend([
                ('Flag', 'flag_message')
            ])

    def serialize_for(self, user):
        return {
            'content': self.body,
            'type': self.typ,
            'attachments': [attachment.serialize() for attachment in self.attachment_set],
            'title': self.msg_title,
            'sender_name': self.sender.full_name,
            'sender_key': self.sender.key,
            'key': self.key,
            'actions': self.get_actions_for(user),
        }

    def __unicode__(self):
        content = self.msg_title or self.body
        return "%s%s" % (content[:30], '...' if len(content) > 30 else '')


ATTACHMENT_TYPES = (
    (1, "Document"),
    (11, "Spreadsheet"),
    (22, "Image"),
    (33, "PDF"),

)


class Attachment(Model):
    """
    A model to store message attachments
    """
    file = field.File("File", random_name=True, required=False)
    typ = field.Integer("Type", choices=ATTACHMENT_TYPES)
    name = field.String("File Name")
    description = field.String("Description")
    channel = Channel()
    message = Message()

    def serialize(self):
        return {
            'description': self.description,
            'file_name': self.name,
            'url': "%s%s" % (settings.S3_PUBLIC_URL, self.file)
        }

    def __unicode__(self):
        return self.name


class Favorite(Model):
    """
    A model to store users bookmarked messages
    """
    channel = Channel()
    user = UserModel()
    message = Message()
