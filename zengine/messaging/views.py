# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pyoko.conf import settings
from pyoko.lib.utils import get_object_from_path
from zengine.messaging.model import Channel, Attachment, Subscriber
from zengine.views.base import BaseView

UserModel = get_object_from_path(settings.USER_MODEL)


def create_message(current):
    """
    Creates a message for the given channel.

    .. code-block:: python

        # request:
        {
            'view':'_zops_create_message',
            'message': {
                'channel': key,     # of channel
                'receiver': key,    # of receiver. Should be set only for direct messages,
                'body': string,     # message text.,
                'type': int,        # zengine.messaging.model.MSG_TYPES,
                'attachments': [{
                    'description': string,  # can be blank,
                    'name': string,         # file name with extension,
                    'content': string,      # base64 encoded file content
                    }]}
        # response:
            {
            'status': string,   # 'OK' for success
            'code': int,        # 201 for success
            'msg_key': key,     # key of the message object,
            }

    """
    msg = current.input['message']
    ch = Channel.objects.get(msg['channel'])
    msg_obj = ch.add_message(body=msg['body'], typ=msg['typ'], sender=current.user,
                             title=msg['title'], receiver=msg['receiver'] or None)
    if 'attachment' in msg:
        for atch in msg['attachments']:
            # TODO: Attachment type detection
            typ = current._dedect_file_type(atch['name'], atch['content'])
            Attachment(channel=ch, msg=msg_obj, name=atch['name'], file=atch['content'],
                       description=atch['description'], typ=typ).save()


def _dedect_file_type(name, content):
    # FIXME: Implement attachment type detection
    return 1  # Return as Document for now


def show_channel(current):
    """
    Initial display of channel content.
    Returns channel description, members, no of members, last 20 messages etc.


    .. code-block:: python

        #  request:
            {
                'view':'_zops_show_channel',
                'channel_key': key,
            }

        #  response:
            {
            'channel_key': key,
            'description': string,
            'no_of_members': int,
            'member_list': [
                {'name': string,
                 'is_online': bool,
                 'avatar_url': string,
                }],
            'last_messages': [
                {'content': string,
                 'title': string,
                 'time': datetime,
                 'channel_key': key,
                 'sender_name': string,
                 'sender_key': key,
                 'type': int,
                 'key': key,
                 'actions':[('name_string', 'cmd_string'),]
                }]
            }
    """
    ch = Channel.objects.get(current.input['channel_key'])
    current.output = {'channel_key': current.input['channel_key'],
                      'description': ch.description,
                      'no_of_members': len(ch.subscriber_set),
                      'member_list': [{'name': sb.user.full_name,
                                       'is_online': sb.user.is_online(),
                                       'avatar_url': sb.user.get_avatar_url()
                                       } for sb in ch.subscriber_set],
                      'last_messages': [msg.serialize_for(current.user)
                                        for msg in ch.get_last_messages()]
                      }


def last_seen_msg(current):
    """
    Push timestamp of last seen message for a channel


    .. code-block:: python

        #  request:
            {
            'view':'_zops_last_seen_msg',
            'channel_key': key,
            'msg_key': key,
            'timestamp': datetime,
            }

        #  response:
            {
            'status': 'OK',
            'code': 200,
            }
    """
    Subscriber.objects.filter(channel_id=current.input['channel_key'],
                              user_id=current.user_id
                              ).update(last_seen_msg_time=current.input['timestamp'])


def list_channels(current):
    """
        List channel memberships of current user


        .. code-block:: python

            #  request:
                {
                'view':'_zops_list_channels',
                }

            #  response:
                {
                'channels': [
                    {'name': string,
                     'key': key,
                     'unread': int,
                     'type': int,
                     'key': key,
                     'actions':[('name_string', 'cmd_string'),]
                    },]
                }
        """
    current.output['channels'] = [
        {'name': sbs.channel.name,
         'key': sbs.channel.key,
         'type': sbs.channel.typ,
         'actions': sbs.channel.get_actions_for(current.user),
         'unread': sbs.unread_count()} for sbs in
        current.user.subscriptions if sbs.is_visible]


def create_public_channel(current):
    """
        Create a public chat room

        .. code-block:: python

            #  request:
                {
                'view':'_zops_create_public_channel,
                'name': string,
                'description': string,
                }

            #  response:
                {
                'status': 'Created',
                'code': 201,
                'channel_key': key, # of just created channel
                }
    """
    channel = Channel(name=current.input['name'],
                      description=current.input['description'],
                      owner=current.user,
                      typ=15).save()
    current.output = {
        'channel_key': channel.key,
        'status': 'OK',
        'code': 201
    }


def create_direct_channel(current):
    """
    Create a One-To-One channel for current user and selected user.

    """
    pass


def create_broadcast_channel(current):
    """
    Create a One-To-One channel for current user and selected user.

    """
    pass


def find_message(current):
    pass


def delete_message(current):
    pass


def edit_message(current):
    pass
