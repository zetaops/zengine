# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pyoko.conf import settings
from pyoko.exceptions import ObjectDoesNotExist
from pyoko.lib.utils import get_object_from_path
from zengine.lib.exceptions import HTTPError
from zengine.messaging.model import Channel, Attachment, Subscriber, Message, Favorite

UserModel = get_object_from_path(settings.USER_MODEL)
UnitModel = get_object_from_path(settings.UNIT_MODEL)

"""

.. code-block:: python

    MSG_DICT = {'content': string,
                 'title': string,
                 'time': datetime,
                 'channel_key': key,
                 'sender_name': string,
                 'sender_key': key,
                 'type': int,
                 'key': key,
                 'actions':[('name_string', 'cmd_string'),]
                 'attachments': [{
                                    'description': string,
                                    'file_name': string,
                                    'url': string,
                                },]
                }
"""

def _dedect_file_type(name, content):
    # FIXME: Implement attachment type detection
    return 1  # Return as Document for now


def _paginate(self, current_page, query_set, per_page=10):
    """
    Handles pagination of object listings.

    Args:
        current_page int:
            Current page number
        query_set (:class:`QuerySet<pyoko:pyoko.db.queryset.QuerySet>`):
            Object listing queryset.
        per_page int:
            Objects per page.

    Returns:
        QuerySet object, pagination data dict as a tuple
    """
    total_objects = query_set.count()
    total_pages = int(total_objects / per_page or 1)
    # add orphans to last page
    current_per_page = per_page + (
        total_objects % per_page if current_page == total_pages else 0)
    pagination_data = dict(page=current_page,
                           total_pages=total_pages,
                           total_objects=total_objects,
                           per_page=current_per_page)
    query_set = query_set.set_params(rows=current_per_page, start=(current_page - 1) * per_page)
    return query_set, pagination_data


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
    ch = Channel(current).objects.get(msg['channel'])
    msg_obj = ch.add_message(body=msg['body'], typ=msg['typ'], sender=current.user,
                             title=msg['title'], receiver=msg['receiver'] or None)
    if 'attachment' in msg:
        for atch in msg['attachments']:
            # TODO: Attachment type detection
            typ = current._dedect_file_type(atch['name'], atch['content'])
            Attachment(channel=ch, msg=msg_obj, name=atch['name'], file=atch['content'],
                       description=atch['description'], typ=typ).save()



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
            'last_messages': [MSG_DICT]
            }
    """
    ch = Channel(current).objects.get(current.input['channel_key'])
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


def channel_history(current):
    """
        Get old messages for a channel. 20 messages per request

        .. code-block:: python

            #  request:
                {
                'view':'_zops_channel_history,
                'channel_key': key,
                'timestamp': datetime, # timestamp data of oldest shown message
                }

            #  response:
                {
                'messages': [MSG_DICT, ],
                'status': 'OK',
                'code': 200
                }
    """
    current.output = {
        'status': 'OK',
        'code': 201,
        'messages': [
            msg.serialize_for(current.user)
            for msg in Message.objects.filter(channel_id=current.input['channel_key'],
                                              timestamp__lt=current.input['timestamp'])[:20]]
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
    Subscriber(current).objects.filter(channel_id=current.input['channel_key'],
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
        {'name': sbs.channel.name or ('Notifications' if sbs.channel.is_private() else ''),
         'key': sbs.channel.key,
         'type': sbs.channel.typ,
         'actions': sbs.channel.get_actions_for(current.user),
         'unread': sbs.unread_count()} for sbs in
        current.user.subscriptions if sbs.is_visible]


def create_channel(current):
    """
        Create a public channel. Can be a broadcast channel or normal chat room.

        .. code-block:: python

            #  request:
                {
                'view':'_zops_create_public_channel',
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


def add_members(current):
    """
        Subscribe member(s) to a channel

        .. code-block:: python

            #  request:
                {
                'view':'_zops_add_members',
                'channel_key': key,
                'members': [key, key],
                }

            #  response:
                {
                'existing': [key,], # existing members
                'newly_added': [key,], # newly added members
                'status': 'Created',
                'code': 201
                }
    """
    newly_added, existing = [], []
    for member_key in current.input['members']:
        sb, new = Subscriber(current).objects.get_or_create(user_id=member_key,
                                                            channel_id=current.input['channel_key'])
        if new:
            newly_added.append(member_key)
        else:
            existing.append(member_key)

    current.output = {
        'existing': existing,
        'newly_added': newly_added,
        'status': 'OK',
        'code': 201
    }


def add_unit_to_channel(current):
    """
        Subscribe users of a given unit to given channel

        JSON API:
            .. code-block:: python

                #  request:
                    {
                    'view':'_zops_add_unit_to_channel',
                    'unit_key': key,
                    'channel_key': key,
                    }

                #  response:
                    {
                    'existing': [key,], # existing members
                    'newly_added': [key,], # newly added members
                    'status': 'Created',
                    'code': 201
                    }
    """
    newly_added, existing = [], []
    for member_key in UnitModel.get_user_keys(current, current.input['unit_key']):
        sb, new = Subscriber(current).objects.get_or_create(user_id=member_key,
                                                            channel_id=current.input['channel_key'])
        if new:
            newly_added.append(member_key)
        else:
            existing.append(member_key)

    current.output = {
        'existing': existing,
        'newly_added': newly_added,
        'status': 'OK',
        'code': 201
    }


def search_user(current):
    """
        Search users for adding to a public room
        or creating one to one direct messaging

        .. code-block:: python

            #  request:
                {
                'view':'_zops_search_user',
                'query': string,
                }

            #  response:
                {
                'results': [('full_name', 'key', 'avatar_url'), ],
                'status': 'OK',
                'code': 200
                }
    """
    current.output = {
        'results': [],
        'status': 'OK',
        'code': 201
    }
    for user in UserModel(current).objects.search_on(settings.MESSAGING_USER_SEARCH_FIELDS,
                                                     contains=current.input['query']):
        current.output['results'].append((user.full_name, user.key, user.avatar))


def search_unit(current):
    """
        Search on units for subscribing it's users to a channel

        .. code-block:: python

            #  request:
                {
                'view':'_zops_search_unit',
                'query': string,
                }

            #  response:
                {
                'results': [('name', 'key'), ],
                'status': 'OK',
                'code': 200
                }
    """
    current.output = {
        'results': [],
        'status': 'OK',
        'code': 201
    }
    for user in UnitModel(current).objects.search_on(settings.MESSAGING_UNIT_SEARCH_FIELDS,
                                                     contains=current.input['query']):
        current.output['results'].append((user.name, user.key))


def create_direct_channel(current):
    """
    Create a One-To-One channel between current and selected user.


    .. code-block:: python

        #  request:
            {
            'view':'_zops_create_direct_channel',
            'user_key': key,
            }

        #  response:
            {
            'status': 'Created',
            'code': 201,
            'channel_key': key, # of just created channel
            }
    """
    channel = Channel.get_or_create_direct_channel(current.user_id, current.input['user_key'])
    current.output = {
        'channel_key': channel.key,
        'status': 'OK',
        'code': 201
    }



def find_message(current):
    """
        Search in messages. If "channel_key" given, search will be limited to that channel,
        otherwise search will be performed on all of user's subscribed channels.

        .. code-block:: python

            #  request:
                {
                'view':'_zops_search_unit,
                'channel_key': key,
                'query': string,
                'page': int,
                }

            #  response:
                {
                'results': [MSG_DICT, ],
                'pagination': {
                    'page': int, # current page
                    'total_pages': int,
                    'total_objects': int,
                    'per_page': int, # object per page
                    },
                'status': 'OK',
                'code': 200
                }
    """
    current.output = {
        'results': [],
        'status': 'OK',
        'code': 201
    }
    query_set = Message(current).objects.search_on(['msg_title', 'body', 'url'],
                                                   contains=current.input['query'])
    if current.input['channel_key']:
        query_set = query_set.filter(channel_id=current.input['channel_key'])
    else:
        subscribed_channels = Subscriber.objects.filter(user_id=current.user_id).values_list(
            "channel_id", flatten=True)
        query_set = query_set.filter(channel_id__in=subscribed_channels)

    query_set, pagination_data = _paginate(current_page=current.input['page'], query_set=query_set)
    current.output['pagination'] = pagination_data
    for msg in query_set:
        current.output['results'].append(msg.serialize_for(current.user))


def delete_message(current):
    """
        Delete a message

        .. code-block:: python

            #  request:
                {
                'view':'_zops_delete_message,
                'message_key': key,
                }

            #  response:
                {
                'status': 'OK',
                'code': 200
                }
    """
    try:
        Message(current).objects.get(sender_id=current.user_id,
                                     key=current.input['message_key']).delete()
        current.output = {'status': 'Deleted', 'code': 200}
    except ObjectDoesNotExist:
        raise HTTPError(404, "")


def edit_message(current):
    """
    Edit a message a user own.

    .. code-block:: python

        # request:
        {
            'view':'_zops_edit_message',
            'message': {
                'body': string,     # message text
                'key': key
                }
        }
        # response:
            {
            'status': string,   # 'OK' for success
            'code': int,        # 200 for success
            }

    """
    current.output = {'status': 'OK', 'code': 200}
    msg = current.input['message']
    if not Message(current).objects.filter(sender_id=current.user_id,
                                           key=msg['key']).update(body=msg['body']):
        raise HTTPError(404, "")


def get_message_actions(current):
    """
    Returns applicable actions for current user for given message key

    .. code-block:: python

        # request:
        {
            'view':'_zops_get_message_actions',
            'message_key': key,
        }
        # response:
            {
            'actions':[('name_string', 'cmd_string'),]
            'status': string,   # 'OK' for success
            'code': int,        # 200 for success
            }

    """
    current.output = {'status': 'OK',
                      'code': 200,
                      'actions': Message.objects.get(
                          current.input['message_key']).get_actions_for(current.user)}


def add_to_favorites(current):
    """
    Favorite a message

    .. code-block:: python

        #  request:
            {
            'view':'_zops_add_to_favorites,
            'message_key': key,
            }

        #  response:
            {
            'status': 'Created',
            'code': 201
            'favorite_key': key
            }

    """
    msg = Message.objects.get(current.input['message_key'])
    current.output = {'status': 'Created', 'code': 201}
    fav, new = Favorite.objects.get_or_create(user_id=current.user_id, message=msg['key'])
    current.output['favorite_key'] = fav.key


def remove_from_favorites(current):
    """
    Remove a message from favorites

    .. code-block:: python

        #  request:
            {
            'view':'_zops_remove_from_favorites,
            'message_key': key,
            }

        #  response:
            {
            'status': 'Deleted',
            'code': 200
            }

    """
    try:
        current.output = {'status': 'Deleted', 'code': 200}
        Favorite(current).objects.get(user_id=current.user_id,
                                      key=current.input['message_key']).delete()
    except ObjectDoesNotExist:
        raise HTTPError(404, "")


def list_favorites(current):
    """
    List user's favorites. If "channel_key" given, will return favorites belong to that channel.

    .. code-block:: python

        #  request:
            {
            'view':'_zops_list_favorites,
            'channel_key': key,
            }

        #  response:
            {
            'status': 'OK',
            'code': 200
            'favorites':[{'key': key,
                        'channel_key': key,
                        'message_key': key,
                        'message_summary': string, # max 60 char
                        'channel_name': string,
                        },]
            }

    """
    current.output = {'status': 'OK', 'code': 200, 'favorites': []}
    query_set = Favorite(current).objects.filter(user_id=current.user_id)
    if current.input['channel_key']:
        query_set = query_set.filter(channel_id=current.input['channel_key'])
    current.output['favorites'] = [{
                                       'key': fav.key,
                                       'channel_key': fav.channel.key,
                                       'message_key': fav.message.key,
                                       'message_summary': fav.summary,
                                       'channel_name': fav.channel_name
                                   } for fav in query_set]
