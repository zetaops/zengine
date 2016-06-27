# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pyoko.conf import settings
from pyoko.lib.utils import get_object_from_path
from zengine.messaging.model import Channel, Attachment
from zengine.views.base import BaseView

UserModel = get_object_from_path(settings.USER_MODEL)



def create_message(current):
    """
    Creates a message for the given channel.

    API:

    .. code-block:: python

            {'view':'_zops_create_message',
            'message': {
                'channel': "code_name of the channel",
                'receiver': "Key of receiver. Can be blank for non-direct messages",
                'title': "Title of the message. Can be blank.",
                'body': "Message body.",
                'type': zengine.messaging.model.MSG_TYPES,
                'attachments': [{
                    'description': "Can be blank.",
                    'name': "File name with extension.",
                    'content': "base64 encoded file content"
                    }]}

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

def _dedect_file_type(current, name, content):
    # TODO: Attachment type detection
    return 1  # Document

def show_channel(current):
    """
    Initial display of channel content

    API:


    """


def list_channels(current):
    pass

def create_public_channel(current):
    pass

def create_direct_channel(current):
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
