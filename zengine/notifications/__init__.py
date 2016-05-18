# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.client_queue import ClientQueue

try:
    from thread import start_new_thread
except ImportError:
    from _thread import start_new_thread
from uuid import uuid4
import time
import six
from zengine.lib.cache import Cache, KeepAlive
from .model import NotificationMessage

class Notify(Cache, ClientQueue):
    """
    Cache based simple notification object.
    """
    PREFIX = 'NTFY'

    TaskInfo = 1
    TaskError = 11
    TaskSuccess = 111
    Message = 2
    Broadcast = 3

    def __init__(self, user_id, sess_id=None):
        Cache.__init__(self, user_id=user_id)
        ClientQueue.__init__(self, user_id, sess_id)


    def cache_to_queue(self):
        """
        Messages that sent to offline users
        are stored in cache, when user become online,
        stored messages redirected to user's queue.
        """
        # FIXME: This will be converted to a after-login view
        offline_messages = list(self.get_all())
        start_new_thread(self._delayed_send, (offline_messages,))

    def _delayed_send(self, offline_messages):
        time.sleep(3)
        client_message = {'cmd': 'notification',
                          'notifications': offline_messages}
        self.send_to_queue(client_message)
        for n in offline_messages:
            self.remove_item(n)

    def set_message(self, title, msg, typ, url=None, sender=None):
        message = {'title': title, 'body': msg, 'type': typ, 'url': url, 'id': uuid4().hex}
        if sender and isinstance(sender, six.string_types):
            sender = NotificationMessage.sender.objects.get(sender)
        receiver = NotificationMessage.receiver.objects.get(self.user_id)
        NotificationMessage(typ=typ, msg_title=title, body=msg, url=url,
                            sender=sender, receiver=receiver).save()
        if KeepAlive(user_id=self.user_id).is_alive():
            client_message = {'cmd': 'notification', 'notifications': [message, ]}
            self.send_to_queue(client_message)
        else:
            self.add(message)

        return message['id']
