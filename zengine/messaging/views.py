# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pyoko.conf import settings
from pyoko.db.adapter.db_riak import BlockSave
from pyoko.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from pyoko.lib.utils import get_object_from_path
from zengine.lib.decorators import view
from zengine.log import log
from zengine.lib.exceptions import HTTPError
from zengine.messaging.model import Channel, Attachment, Subscriber, Message, Favorite, \
    FlaggedMessage

UserModel = get_object_from_path(settings.USER_MODEL)
UnitModel = get_object_from_path(settings.UNIT_MODEL)

"""

.. code-block:: python

    MSG_DICT = {
        'content': string,
        'title': string,
        'timestamp': datetime,
        'updated_at': datetime,
        'is_update': boolean, # false for new messages
                              # true if this is an updated message
        'channel_key': key,
        'sender_name': string,
        'sender_key': key,
        'type': int,
        'url': string,
        'avatar_url': string,
        'key': key,
        'cmd': 'message',
        'attachments': [{
                        'description': string,
                        'file_name': string,
                        'url': string,
                    },]
}


    USER_STATUS_UPDATE = {
        'cmd': 'user_status',
        'channel_key': key,
        'channel_name': string,
        'avatar_url': string,
        'is_online': boolean,
    }

    CHANNEL_SUBSCRIPTION = {
        'cmd': 'channel_subscription',
        'channel_key': key,
        'channel_name': string,
        'avatar_url': string,
        'is_online': boolean,
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

@view()
def create_message(current):
    """
    Creates a message for the given channel.

    .. code-block:: python

        # request:
        {
            'view':'_zops_create_message',
            'message': {
                'channel': key,     # of channel
                'body': string,     # message text.,
                'type': int,        # zengine.messaging.model.MSG_TYPES,
                'attachments': [{
                    'description': string,  # can be blank,
                    'name': string,         # file name with extension,
                    'content': string,      # base64 encoded file content
                    }]}
        # response:
            {
            'status': 'Created',
            'code': 201,
            'msg_key': key,     # key of the message object,
            }

    """
    msg = current.input['message']
    msg_obj = Channel.add_message(msg['channel'], body=msg['body'], typ=msg['type'],
                                  sender=current.user,
                                  title=msg['title'], receiver=msg['receiver'] or None)
    current.output = {
        'msg_key': msg_obj.key,
        'status': 'Created',
        'code': 201
    }
    if 'attachment' in msg:
        for atch in msg['attachments']:
            typ = current._dedect_file_type(atch['name'], atch['content'])
            Attachment(channel_id=msg['channel'], msg=msg_obj, name=atch['name'],
                       file=atch['content'], description=atch['description'], typ=typ).save()

@view()
def show_channel(current, waited=False):
    """
    Initial display of channel content.
    Returns channel description, members, no of members, last 20 messages etc.


    .. code-block:: python

        #  request:
            {
                'view':'_zops_show_channel',
                'key': key,
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
            'name': string,
            'last_messages': [MSG_DICT]
            'status': 'OK',
            'code': 200
            }
    """
    ch = Channel(current).objects.get(current.input['key'])
    sbs = ch.get_subscription_for_user(current.user_id)
    current.output = {'key': current.input['key'],
                      'description': ch.description,
                      'name': sbs.name,
                      'actions': sbs.get_actions(),
                      'avatar_url': ch.get_avatar(current.user),
                      'no_of_members': len(ch.subscriber_set),
                      'member_list': [{'name': sb.user.full_name,
                                       'is_online': sb.user.is_online(),
                                       'avatar_url': sb.user.get_avatar_url()
                                       } for sb in ch.subscriber_set.objects.all()],
                      'last_messages': [],
                      'status': 'OK',
                      'code': 200
                      }
    for msg in ch.get_last_messages():
        current.output['last_messages'].insert(0, msg.serialize(current.user))

@view()
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
        'messages': []
    }

    for msg in list(Message.objects.filter(channel_id=current.input['channel_key'],
                                      updated_at__lte=current.input['timestamp'])[:20]):
        current.output['messages'].insert(0, msg.serialize(current.user))
    # FIXME: looks like  pyoko's __lt is broken
    # TODO: convert lte to lt and remove this block, when __lt filter fixed
    if current.output['messages']:
        current.output['messages'].pop(-1)

@view()
def report_last_seen_message(current):
    """
    Push timestamp of latest message of an ACTIVE channel.

    This view should be called with timestamp of latest message;
    - When user opens (clicks on) a channel.
    - Periodically (eg: setInterval for 15secs) while user staying in a channel.


    .. code-block:: python

        #  request:
            {
            'view':'_zops_last_seen_msg',
            'channel_key': key,
            'key': key,
            'timestamp': datetime,
            }

        #  response:
            {
            'status': 'OK',
            'code': 200,
            }
    """
    sbs = Subscriber(current).objects.filter(channel_id=current.input['channel_key'],
                                             user_id=current.user_id)[0]
    sbs.last_seen_msg_time = current.input['timestamp']
    sbs.save()
    current.output = {
        'status': 'OK',
        'code': 200}

@view()
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
                    {'name': string, # name of channel
                     'key': key,     # key of channel
                     'unread': int,  # unread message count
                     'type': int,    # channel type,
                                     # 15: public channels (chat room/broadcast channel distinction
                                                         comes from "read_only" flag)
                                     # 10: direct channels
                                     # 5: one and only private channel which is "Notifications"
                     'read_only': boolean,
                                     # true if this is a read-only subscription to a broadcast channel
                                     # false if it's a public chat room

                     'actions':[('action name', 'view name'),]
                    },]
                }
        """
    current.output = {
        'status': 'OK',
        'code': 200,
        'channels': []}
    for sbs in current.user.subscriptions.objects.filter(is_visible=True):
        try:
            current.output['channels'].append(sbs.get_channel_listing())
        except ObjectDoesNotExist:
            # FIXME: This should not happen,
            log.exception("UNPAIRED DIRECT EXCHANGES!!!!")
            sbs.delete()

@view()
def unread_count(current):
    """
        Number of unread messages for current user


        .. code-block:: python

            #  request:
                {
                'view':'_zops_unread_count',
                }

            #  response:
                {
                'status': 'OK',
                'code': 200,
                'notifications': int,
                'messages': int,
                }
        """
    unread_ntf = 0
    unread_msg = 0
    for sbs in current.user.subscriptions.objects.filter(is_visible=True):
        try:
            if sbs.channel.key == current.user.prv_exchange:
                unread_ntf += sbs.unread_count()
            else:
                unread_msg += sbs.unread_count()
        except ObjectDoesNotExist:
            # FIXME: This should not happen,
            log.exception("MULTIPLE PRV EXCHANGES!!!!")
            sbs.delete()
    current.output = {
        'status': 'OK',
        'code': 200,
        'notifications': unread_ntf,
        'messages': unread_msg
    }

@view()
def get_notifications(current):
    """
        Returns last N notifications for current user


        .. code-block:: python

            #  request:
                {
                'view':'_zops_unread_messages',
                'amount': int, # Optional, defaults to 8
                }

            #  response:
                {
                'status': 'OK',
                'code': 200,
                'notifications': [{'title':string,
                                   'body': string,
                                   'channel_key': key,
                                   'type': int,
                                   'url': string, # could be a in app JS URL prefixed with "#" or
                                                  # full blown URL prefixed with "http"
                                   'message_key': key,
                                   'timestamp': datetime},],
                }
        """
    current.output = {
        'status': 'OK',
        'code': 200,
        'notifications': [],
    }
    amount = current.input.get('amount', 8)
    try:
        notif_sbs = current.user.subscriptions.objects.get(channel_id=current.user.prv_exchange)
    except MultipleObjectsReturned:
        # FIXME: This should not happen,
        log.exception("MULTIPLE PRV EXCHANGES!!!!")
        sbs = current.user.subscriptions.objects.filter(channel_id=current.user.prv_exchange)
        sbs[0].delete()
        notif_sbs = sbs[1]
    for msg in notif_sbs.channel.message_set.objects.all()[:amount]:
        current.output['notifications'].insert(0, {
            'title': msg.msg_title,
            'body': msg.body,
            'type': msg.typ,
            'url': msg.url,
            'channel_key': msg.channel.key,
            'message_key': msg.key,
            'timestamp': msg.updated_at})

@view()
def create_channel(current):
    """
        Create a public channel. Can be a broadcast channel or normal chat room.

        Chat room and broadcast distinction will be made at user subscription phase.

        .. code-block:: python

            #  request:
                {
                'view':'_zops_create_channel',
                'name': string,
                'description': string,
                }

            #  response:
                {
                'description': string,
                'name': string,
                'no_of_members': int,
                'member_list': [
                    {'name': string,
                     'is_online': bool,
                     'avatar_url': string,
                    }],
                'last_messages': [MSG_DICT]
                'status': 'Created',
                'code': 201,
                'key': key, # of just created channel
                }
    """
    channel = Channel(name=current.input['name'],
                      description=current.input['description'],
                      owner=current.user,
                      typ=15).save()
    with BlockSave(Subscriber):
        Subscriber.objects.get_or_create(user=channel.owner,
                                         channel=channel,
                                         can_manage=True,
                                         can_leave=False)
    current.input['key'] = channel.key
    show_channel(current)
    current.output.update({
        'status': 'Created',
        'code': 201
    })

@view()
def add_members(current):
    """
        Subscribe member(s) to a channel

        .. code-block:: python

            #  request:
                {
                'view':'_zops_add_members',
                'channel_key': key,
                'read_only': boolean, # true if this is a Broadcast channel,
                                      # false if it's a normal chat room
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
    read_only = current.input['read_only']
    for member_key in current.input['members']:
        sb, new = Subscriber(current).objects.get_or_create(user_id=member_key,
                                                            read_only=read_only,
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

@view()
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
                    'read_only': boolean, # true if this is a Broadcast channel,
                                          # false if it's a normal chat room

                    }

                #  response:
                    {
                    'existing': [key,], # existing members
                    'newly_added': [key,], # newly added members
                    'status': 'Created',
                    'code': 201
                    }
    """
    read_only = current.input['read_only']
    newly_added, existing = [], []
    for member_key in UnitModel.get_user_keys(current, current.input['unit_key']):
        sb, new = Subscriber(current).objects.get_or_create(user_id=member_key,
                                                            read_only=read_only,
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

@view()
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
    qs = UserModel(current).objects.exclude(key=current.user_id).search_on(
        *settings.MESSAGING_USER_SEARCH_FIELDS,
        contains=current.input['query'])
    # FIXME: somehow exclude(key=current.user_id) not working with search_on()

    for user in qs:
        if user.key != current.user_id:
            current.output['results'].append((user.full_name, user.key, user.get_avatar_url()))

@view()
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
    for user in UnitModel(current).objects.search_on(*settings.MESSAGING_UNIT_SEARCH_FIELDS,
                                                     contains=current.input['query']):
        current.output['results'].append((user.name, user.key))

@view()
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
            'description': string,
            'no_of_members': int,
            'member_list': [
                {'name': string,
                 'is_online': bool,
                 'avatar_url': string,
                }],
            'last_messages': [MSG_DICT]
            'status': 'Created',
            'code': 201,
            'channel_key': key, # of just created channel
            'name': string, # name of subscribed channel
            }
    """
    channel, sub_name = Channel.get_or_create_direct_channel(current.user_id,
                                                             current.input['user_key'])
    current.input['key'] = channel.key
    show_channel(current)
    current.output.update({
        'status': 'Created',
        'code': 201
    })

@view()
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
        current.output['results'].append(msg.serialize(current.user))

@view()
def delete_channel(current):
    """
        Delete a channel

        .. code-block:: python

            #  request:
                {
                'view':'_zops_delete_channel,
                'channel_key': key,
                }

            #  response:
                {
                'status': 'OK',
                'code': 200
                }
    """
    ch_key = current.input['channel_key']

    ch = Channel(current).objects.get(owner_id=current.user_id, key=ch_key)
    ch.delete()
    Subscriber.objects.filter(channel_id=ch_key).delete()
    Message.objects.filter(channel_id=ch_key).delete()
    current.output = {'status': 'Deleted', 'code': 200}

@view()
def edit_channel(current):
    """
        Update channel name or description

        .. code-block:: python

            #  request:
                {
                'view':'_zops_edit_channel,
                'channel_key': key,
                'name': string,
                'description': string,
                }

            #  response:
                {
                'status': 'OK',
                'code': 200
                }
    """
    ch = Channel(current).objects.get(owner_id=current.user_id,
                                      key=current.input['channel_key'])
    ch.name = current.input['name']
    ch.description = current.input['description']
    ch.save()
    for sbs in ch.subscriber_set.objects.all():
        sbs.name = ch.name
        sbs.save()
    current.output = {'status': 'OK', 'code': 200}

@view()
def pin_channel(current):
    """
        Pin a channel to top of channel list

        .. code-block:: python

            #  request:
                {
                'view':'_zops_pin_channel,
                'channel_key': key,
                }

            #  response:
                {
                'status': 'OK',
                'code': 200
                }
    """
    try:
        Subscriber(current).objects.filter(user_id=current.user_id,
                                           channel_id=current.input['channel_key']).update(
            pinned=True)
        current.output = {'status': 'OK', 'code': 200}
    except ObjectDoesNotExist:
        raise HTTPError(404, "")

@view()
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
                'key': key,
                'status': 'OK',
                'code': 200
                }
    """
    try:
        Message(current).objects.get(sender_id=current.user_id,
                                     key=current.input['key']).delete()
        current.output = {'status': 'Deleted', 'code': 200, 'key': current.input['key']}
    except ObjectDoesNotExist:
        raise HTTPError(404, "")

@view()
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
    in_msg = current.input['message']
    try:
        msg = Message(current).objects.get(sender_id=current.user_id, key=in_msg['key'])
        msg.body = in_msg['body']
        msg.save()
    except ObjectDoesNotExist:
        raise HTTPError(404, "")

@view()
def flag_message(current):
    """
    Flag inappropriate messages

    .. code-block:: python

        # request:
        {
            'view':'_zops_flag_message',
            'message_key': key,
        }
        # response:
            {
            '
            'status': 'Created',
            'code': 201,
            }

    """
    current.output = {'status': 'Created', 'code': 201}
    FlaggedMessage.objects.get_or_create(user_id=current.user_id,
                                         message_id=current.input['key'])

@view()
def unflag_message(current):
    """
    remove flag of a message

    .. code-block:: python

        # request:
        {
            'view':'_zops_flag_message',
            'key': key,
        }
        # response:
            {
            '
            'status': 'OK',
            'code': 200,
            }

    """
    current.output = {'status': 'OK', 'code': 200}

    FlaggedMessage(current).objects.filter(user_id=current.user_id,
                                           message_id=current.input['key']).delete()

@view()
def get_message_actions(current):
    """
    Returns applicable actions for current user for given message key

    .. code-block:: python

        # request:
        {
            'view':'_zops_get_message_actions',
            'key': key,
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
                          current.input['key']).get_actions_for(current.user)}

@view()
def add_to_favorites(current):
    """
    Favorite a message

    .. code-block:: python

        #  request:
            {
            'view':'_zops_add_to_favorites,
            'key': key,
            }

        #  response:
            {
            'status': 'Created',
            'code': 201
            'favorite_key': key
            }

    """
    msg = Message.objects.get(current.input['key'])
    current.output = {'status': 'Created', 'code': 201}
    fav, new = Favorite.objects.get_or_create(user_id=current.user_id, message=msg)
    current.output['favorite_key'] = fav.key

@view()
def remove_from_favorites(current):
    """
    Remove a message from favorites

    .. code-block:: python

        #  request:
            {
            'view':'_zops_remove_from_favorites,
            'key': key,
            }

        #  response:
            {
            'status': 'OK',
            'code': 200
            }

    """
    try:
        current.output = {'status': 'OK', 'code': 200}
        Favorite(current).objects.get(user_id=current.user_id,
                                      key=current.input['key']).delete()
    except ObjectDoesNotExist:
        raise HTTPError(404, "")

@view()
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
