# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from uuid import uuid4

from zengine.lib.cache import Cache


class Notify(Cache):
    PREFIX = 'NTFY'

    TaskInfo = 1
    TaskError = 11
    TaskSuccess = 111
    Message = 2
    Broadcast = 3

    def __init__(self, user_id):
        super(Notify, self).__init__(str(user_id))

    def set_message(self, title, msg, typ, url=None):
        self.add({'title': title, 'body': msg, 'type': typ, 'url': url, 'id': uuid4().hex})
