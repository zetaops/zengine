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
    def test_check_user_task_rerun(self):

        for i in range(3):
            self.prepare_client('/check_user_task_rerun', username='super_user')
            resp = self.client.post(cmd = i)
            token = resp.token
            assert resp.json['task_name'] == 'user_task_a'
            self.prepare_client('/check_user_task_rerun', username='super_user',token =token)
            resp = self.client.post()
            assert resp.json['task_name'] == 'user_task_a'

        self.prepare_client('/check_user_task_rerun', username='super_user')
        resp = self.client.post(cmd=4)
        assert resp.json['task_name'] == 'user_task_b'
        resp = self.client.post()
        assert resp.json['task_name'] == 'user_task_a'