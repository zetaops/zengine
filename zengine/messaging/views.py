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


class MessageView(BaseView):
    def create_message(self):
        """
        Creates a message for the given channel.

        API:
            self.current.input['data']['message'] = {
                'channel': code_name of the channel.
                'receiver': Key of receiver. Can be blank for non-direct messages.
                'title': Title of the message. Can be blank.
                'body': Message body.
                'type': zengine.messaging.model.MSG_TYPES
                'attachments': [{
                    'description': Can be blank.
                    'name': File name with extension.
                    'content': base64 encoded file content
                    }]
                }

        """
        msg = self.current.input['message']
        ch = Channel.objects.get(msg['channel'])
        msg_obj = ch.add_message(body=msg['body'], typ=msg['typ'], sender=self.current.user,
                                 title=msg['title'], receiver=msg['receiver'] or None)
        if 'attachment' in msg:
            for atch in msg['attachments']:
                # TODO: Attachment type detection
                typ = self._dedect_file_type(atch['name'], atch['content'])
                Attachment(channel=ch, msg=msg_obj, name=atch['name'], file=atch['content'],
                           description=atch['description'], typ=typ).save()

    def _dedect_file_type(self, name, content):
        # TODO: Attachment type detection
        return 1  # Document

    def show_channel(self):
        pass

    def list_channels(self):
        pass

    def create_public_channel(self):
        pass

    def create_direct_channel(self):
        """
        Create a One-To-One channel for current user and selected user.

        """
        pass

    def find_message(self):
        pass

    def delete_message(self):
        pass

    def edit_message(self):
        pass
