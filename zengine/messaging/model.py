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
import six

from pyoko import Model, field, ListNode
from pyoko.conf import settings
from pyoko.db.adapter.db_riak import BlockSave
from pyoko.exceptions import IntegrityError
from pyoko.fields import DATE_TIME_FORMAT
from pyoko.lib.utils import get_object_from_path
from zengine.client_queue import BLOCKING_MQ_PARAMS, get_mq_connection
from zengine.lib.utils import to_safe_str

UserModel = get_object_from_path(settings.USER_MODEL)

CHANNEL_TYPES = (
    # users private message hub
    (5, "Private"),
    #  a One-To-One communication between 2 user
    (10, "Direct"),
    # public chat rooms
    (15, "Public"),
)


class Channel(Model):
    """
    Represents MQ exchanges.

    is_private: Represents users exchange hub
    Each user have a durable private exchange,
     which their code_name composed from user key prefixed with "prv_"

    is_direct: Represents a user-to-user direct message exchange
    """

    class Meta:
        verbose_name = "Kanal"
        verbose_name_plural = "Kanallar"
        search_fields = ['name']
        list_filters = ['typ']

    mq_channel = None
    mq_connection = None

    typ = field.Integer("Tip", choices=CHANNEL_TYPES)
    name = field.String("Ad")
    code_name = field.String("İç ad")
    description = field.String("Tanım")
    owner = UserModel(reverse_name='created_channels', null=True)

    def __unicode__(self):
        return "%s (%s's %s channel)" % (self.name or '',
                                         self.owner.full_name,
                                         self.get_typ_display())

    #
    # class Managers(ListNode):
    #     user = UserModel()
    @property
    def is_private(self):
        return self.typ == 5

    @classmethod
    def get_or_create_direct_channel(cls, initiator_key, receiver_key):
        """
        Creates a  direct messaging channel between two user

        Args:
            initiator: User, who want's to make first contact
            receiver: User, other party

        Returns:
            (Channel, receiver_name)
        """
        existing = cls.objects.OR().filter(
            code_name='%s_%s' % (initiator_key, receiver_key)).filter(
            code_name='%s_%s' % (receiver_key, initiator_key))
        receiver_name = UserModel.objects.get(receiver_key).full_name
        if existing:
            channel = existing[0]
        else:
            channel_name = '%s_%s' % (initiator_key, receiver_key)
            channel = cls(is_direct=True, code_name=channel_name, typ=10).blocking_save()
        with BlockSave(Subscriber):
            Subscriber.objects.get_or_create(channel=channel,
                                             user_id=initiator_key,
                                             name=receiver_name)
            Subscriber.objects.get_or_create(channel=channel,
                                             user_id=receiver_key,
                                             name=UserModel.objects.get(initiator_key).full_name)
        return channel, receiver_name

    def get_avatar(self, user):
        if self.typ == 10:
            return self.subscriber_set.objects.exclude(user=user)[0].user.get_avatar_url()
        else:
            return None

    @classmethod
    def add_message(cls, channel_key, body, title=None, sender=None, url=None, typ=2,
                    receiver=None):
        mq_channel = cls._connect_mq()
        msg_object = Message(sender=sender, body=body, msg_title=title, url=url,
                             typ=typ, channel_id=channel_key, receiver=receiver, key=uuid4().hex)
        msg_object.setattr('unsaved', True)
        mq_channel.basic_publish(exchange=channel_key,
                                 routing_key='',
                                 body=json.dumps(msg_object.serialize()))
        return msg_object.save()

    def get_subscription_for_user(self, user_id):
        return self.subscriber_set.objects.get(user_id=user_id)

    def get_last_messages(self):
        # TODO: Try to refactor this with https://github.com/rabbitmq/rabbitmq-recent-history-exchange
        return self.message_set.objects.order_by('-updated_at').all()[:20]

    @classmethod
    def _connect_mq(cls):
        if cls.mq_connection is None or cls.mq_connection.is_closed:
            cls.mq_connection, cls.mq_channel = get_mq_connection()
        return cls.mq_channel

    def create_exchange(self):
        """
        Creates MQ exchange for this channel
        Needs to be defined only once.
        """
        mq_channel = self._connect_mq()
        mq_channel.exchange_declare(exchange=self.code_name,
                                    exchange_type='fanout',
                                    durable=True)

    def delete_exchange(self):
        """
        Deletes MQ exchange for this channel
        Needs to be defined only once.
        """
        mq_channel = self._connect_mq()
        mq_channel.exchange_delete(exchange=self.code_name)

    def pre_creation(self):
        if not self.code_name:
            if self.name:
                self.code_name = to_safe_str(self.name)
                self.key = self.code_name
                return
            if self.owner and self.is_private:
                self.code_name = self.owner.prv_exchange
                self.key = self.code_name
                return
            raise IntegrityError('Non-private and non-direct channels should have a "name".')
        else:
            self.key = self.code_name

    def post_delete(self):
        self.delete_exchange()

    def post_save(self):
        self.create_exchange()
        # self.subscribe_owner()

class Subscriber(Model):
    """
    Permission model
    """

    class Meta:
        verbose_name = "Abonelik"
        verbose_name_plural = "Abonelikler"
        # list_fields = ["name", ]
        # list_filters = ["name",]
        search_fields = ["name", ]

    mq_channel = None
    mq_connection = None

    channel = Channel()
    typ = field.Integer("Tip", choices=CHANNEL_TYPES)
    name = field.String("Abonelik adı")
    user = UserModel(reverse_name='subscriptions')
    is_muted = field.Boolean("Kanalı sustur", default=False)
    pinned = field.Boolean("Yukarı sabitle", default=False)
    inform_me = field.Boolean("Adım geçtiğinde haber ver", default=True)
    read_only = field.Boolean("Salt-okunur (duyuru) kanalı",
                              default=False)
    is_visible = field.Boolean("Görünür", default=True)
    can_manage = field.Boolean("Bu kanalı yönetebilir", default=False)
    can_leave = field.Boolean("Kanaldan ayrılabilir", default=True)
    last_seen_msg_time = field.TimeStamp("Son okunan mesajın zamanpulu")

    # status = field.Integer("Status", choices=SUBSCRIPTION_STATUS)

    def __unicode__(self):
        return "%s subscription of %s" % (self.name, self.user)

    @classmethod
    def _connect_mq(cls):
        if cls.mq_connection is None or cls.mq_connection.is_closed:
            cls.mq_connection, cls.mq_channel = get_mq_connection()
        return cls.mq_channel

    def get_channel_listing(self):
        """
        serialized form for channel listing

        """
        return {'name': self.name,
                'key': self.channel.key,
                'type': self.channel.typ,
                'read_only': self.read_only,
                'is_online': self.is_online(),
                'actions': self.get_actions(),
                'unread': self.unread_count()}

    def get_actions(self):
        actions = [
            ('Yukarı Sabitle', '_zops_pin_channel'),
            # ('Mute', '_zops_mute_channel'),
        ]
        if self.channel.owner == self.user or self.can_manage:
            actions.extend([
                ('Sil', '_zops_delete_channel'),
                ('Düzenle', '_zops_edit_channel'),
                ('Kullanıcı Ekle', '_zops_add_members'),
                ('Birim Ekle', '_zops_add_unit_to_channel')
            ])
        return actions

    def is_online(self):
        # TODO: Cache this method
        if self.channel.typ == 10:
            try:
                return self.channel.subscriber_set.objects.exclude(
                    user=self.user).get().user.is_online()
            except:
                return False

    def unread_count(self):
        if self.last_seen_msg_time:
            return self.channel.message_set.objects.filter(
                updated_at__gt=self.last_seen_msg_time).count()
        else:
            return self.channel.message_set.objects.count()

    def get_unread_messages(self, amount):
        if self.last_seen_msg_time:
            return self.channel.message_set.objects.all(
                updated_at__gt=self.last_seen_msg_time)[:amount]
        else:
            return self.channel.message_set.objects.all()[:amount]

    def create_exchange(self):
        """
        Creates user's private exchange

        Actually user's private channel needed to be defined only once,
        and this should be happened when user first created.
        But since this has a little performance cost,
        to be safe we always call it before binding to the channel we currently subscribe
        """
        channel = self._connect_mq()
        channel.exchange_declare(exchange=self.user.prv_exchange,
                                 exchange_type='fanout',
                                 durable=True)

    @classmethod
    def mark_seen(cls, key, datetime_str):
        cls.objects.filter(key=key).update(last_seen=datetime_str)

    def bind_to_channel(self):
        """
        Binds (subscribes) users private exchange to channel exchange
        Automatically called at creation of subscription record.
        """
        if self.channel.code_name != self.user.prv_exchange:
            channel = self._connect_mq()
            channel.exchange_bind(source=self.channel.code_name, destination=self.user.prv_exchange)

    def inform_subscriber(self):
        if self.channel.typ != 5:
            self.user.send_client_cmd(self.get_channel_listing(), 'channel_subscription')

    def post_creation(self):
        self.create_exchange()
        self.bind_to_channel()
        self.inform_subscriber()

    def pre_creation(self):
        if (self.channel.key == self.user.prv_exchange and
                Subscriber.objects.filter(channel_id=self.user.prv_exchange).count()):
            raise Exception("Duplicate private channel subscription for %s" % self.user)
        if not self.name:
            self.name = self.channel.name


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
    Message model

    Notes:
        Never use directly for creating new messages! Use these methods:
            - Channel objects's **add_message()** method.
            - User object's **set_message()** method. (which also uses channel.add_message)
    """

    class Meta:
        verbose_name = "Mesaj"
        verbose_name_plural = "Mesajlar"

    channel = Channel()
    sender = UserModel(reverse_name='sent_messages')
    receiver = UserModel(reverse_name='received_messages')
    typ = field.Integer("Tip", choices=MSG_TYPES, default=1)
    status = field.Integer("Durum", choices=MESSAGE_STATUS, default=1)
    msg_title = field.String("Başlık")
    body = field.String("Metin")
    url = field.String("URL")

    def get_actions_for(self, user):
        actions = []
        if Favorite.objects.filter(user=user,
                                   channel=self.channel,
                                   message=self).count():
            actions.append(('Favorilerden çıkar', '_zops_remove_from_favorites'))
        else:
            actions.append(('Favorilere ekle', '_zops_favorite_message'))

        if user:
            if FlaggedMessage.objects.filter(user=user, message=self).count():
                actions.append(('İşareti Kaldır', '_zops_unflag_message'))
            else:
                actions.append(('İşaretle', '_zops_flag_message'))
            if self.sender == user:
                actions.extend([
                    ('Sil', '_zops_delete_message'),
                    ('Düzenle', '_zops_edit_message')
                ])
        return actions

    def serialize(self, user=None):
        """
        Serializes message for given user.

        Note:
            Should be called before first save(). Otherwise "is_update" will get wrong value.

        Args:
            user: User object

        Returns:
            Dict. JSON serialization ready dictionary object
        """
        return {
            'content': self.body,
            'type': self.typ,
            'updated_at': self.updated_at,
            'timestamp': self.updated_at,
            'is_update': not hasattr(self, 'unsaved'),
            'attachments': [attachment.serialize() for attachment in self.attachment_set],
            'title': self.msg_title,
            'url': self.url,
            'sender_name': self.sender.full_name,
            'sender_key': self.sender.key,
            'channel_key': self.channel.key,
            'cmd': 'message',
            'avatar_url': self.sender.avatar,
            'key': self.key,
        }

    def __unicode__(self):
        content = six.text_type(self.msg_title or self.body)
        return "%s%s" % (content[:30], '...' if len(content) > 30 else '')

    def _republish(self):
        """
        Re-publishes updated message
        """
        mq_channel = self.channel._connect_mq()
        mq_channel.basic_publish(exchange=self.channel.key, routing_key='',
                                 body=json.dumps(self.serialize()))

    def pre_save(self):
        if not hasattr(self, 'unsaved'):
            self._republish()


ATTACHMENT_TYPES = (
    (1, "Belge"),
    (11, "Hesap Tablosu"),
    (22, "Görsel"),
    (33, "PDF"),

)


class Attachment(Model):
    """
    A model to store message attachments
    """
    file = field.File("Dosya", random_name=True, required=False)
    typ = field.Integer("Tip", choices=ATTACHMENT_TYPES)
    name = field.String("Dosya Adı")
    description = field.String("Tanım")
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

    class Meta:
        verbose_name = "Favori"
        verbose_name_plural = "Favoriler"

    channel = Channel()
    user = UserModel()
    message = Message()
    summary = field.String("Mesaj Özeti")
    channel_name = field.String("Kanal Adı")

    def pre_creation(self):
        if not self.channel:
            self.channel = self.message.channel
        self.summary = self.message.body[:60]
        self.channel_name = self.channel.name


class FlaggedMessage(Model):
    """
    A model to store users bookmarked messages
    """

    class Meta:
        verbose_name = "İşaretlenmiş Mesaj"
        verbose_name_plural = "İşaretlenmiş Mesajlar"

    channel = Channel()
    user = UserModel()
    message = Message()

    def pre_creation(self):
        self.channel = self.message.channel
