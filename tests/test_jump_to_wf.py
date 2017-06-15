# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import pytest
from pyoko.conf import settings
from pyoko.db.adapter.db_riak import BlockSave
from zengine.lib.exceptions import HTTPError
from zengine.lib.test_utils import BaseTestCase
from zengine.models import User
from zengine.messaging.model import Message
from zengine.signals import lane_user_change


class TestCase(BaseTestCase):
    def test_jump_to_wf(self):
        self.prepare_client('/jump_to_wf/', username='super_user')
        resp = self.client.post()
        assert resp.json['from_jumped'] is None
        assert resp.json['from_main']
        assert resp.json['msgbox']['title'] == 'jumped_task_msg'
        resp = self.client.post()
        assert resp.json['from_jumped']
        self.client.post()
        assert self.client.current.task_data['from_jumped']
