# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pyoko.conf import settings
from pyoko.lib.utils import get_object_from_path
from zengine.views.base import BaseView
UserModel = get_object_from_path(settings.USER_MODEL)

class MessageView(BaseView):

    def create_message(self):
        """
        Creates a message for the given channel.

        Args:
            self.current.input['data']['message'] = {
                'channel': code_name of the channel
                'title': Title of the message, optional
                'body': Title of the message
                'attachment':{
                    'name': title/name of file
                    'key': storage key
                    }
                }

        """
        # TODO: Attachment support!!!
        msg = self.current.input['message']

        # UserModel.objects.get(msg['receiver']).send_message(msg.get('title'), msg['body'], typ=2,
        #                                                     sender=self.current.user)



    def new_broadcast_message(self):
        pass

    def show_channel(self):
        pass


    def list_channels(self):
        pass
