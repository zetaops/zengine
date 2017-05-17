# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import pytest
import time

from pyoko.conf import settings
from pyoko.db.adapter.db_riak import BlockSave
from pyoko.exceptions import ObjectDoesNotExist
from zengine.lib.exceptions import HTTPError
from zengine.lib.test_utils import BaseTestCase
from zengine.models import User, TaskInvitation, Role
from zengine.messaging.model import Message


class TestCase(BaseTestCase):
    def setup_method(self, test_method):
        BaseTestCase.setup_method(self, test_method)
        # We need to change the models from what are given in the settings (i.e. zengine.models.User)
        # to the models under tests (i.e. tests.models.User). We can't do this in `tests.settings`
        # because running the shell command of the command line management tools otherwise gets stuck
        # on a circular import.
        from zengine.wf_daemon import wf_engine as _wf_engine
        from .models import Role as _RoleModel
        self._role_model = _wf_engine.role_model
        _wf_engine.role_model = _RoleModel

    def teardown_method(self, test_method):
        from zengine.wf_daemon import wf_engine as _wf_engine
        _wf_engine.role_model = self._role_model

    def test_multi_user_success(self):
        # Start the workflow with the first user
        test_user = User.objects.get(username='test_user')
        self.prepare_client('/multiuser/', user=test_user)
        TaskInvitation.objects.filter(wf_name='multiuser').delete()
        time.sleep(1)
        with BlockSave(Message):
            resp = self.client.post()
        assert resp.json['msgbox']['title'] == settings.MESSAGES['lane_change_message_title']

        # This user has the necessary permissions and relations, should be able to join the workflow
        token, user = self.get_user_token('test_user2')
        self.prepare_client('/multiuser/', user=user, token=token)
        task_inv = TaskInvitation.objects.filter(wf_name='multiuser',
                                                 role=self.client.current.role)
        assert task_inv.count() == 1

        task_inv.delete()
        time.sleep(1)

        with BlockSave(Message):
            resp = self.client.post()
        assert resp.json['msgbox']['title'] == settings.MESSAGES['lane_change_message_title']

        token, user = self.get_user_token('test_user')
        self.prepare_client('/multiuser/', user=user, token=token)
        task_inv = TaskInvitation.objects.filter(wf_name='multiuser',
                                                 role=self.client.current.role)
        assert task_inv.count() == 1

        task_inv.delete()
        time.sleep(1)

    def test_multi_user_owner_fail(self):
        # Start the workflow with the first user
        wf_name = '/multiuser/'
        manager_user = User.objects.get(username='test_user')
        self.prepare_client(wf_name, user=manager_user)
        with BlockSave(Message):
            self.client.post()

        # This user has not the necessary permissions and relations,
        # should not have join to workflow.
        token, user = self.get_user_token('test_user3')
        self.prepare_client(wf_name, user=user, token=token)

        with pytest.raises(HTTPError):
            self.client.post()

        # This user has the necessary permissions and relations, should have join to workflow.
        token, user = self.get_user_token('test_user2')
        self.prepare_client(wf_name, user=user, token=token)

        resp = self.client.post()
        assert resp.json['msgbox']['title'] == settings.MESSAGES['lane_change_message_title']

        time.sleep(1)
        TaskInvitation.objects.filter(wf_name='multiuser').delete()
