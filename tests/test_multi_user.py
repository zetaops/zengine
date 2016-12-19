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

        with BlockSave(Message):
            resp = self.client.post()
        assert resp.json['msgbox']['title'] == settings.MESSAGES['lane_change_message_title']

        token, user = self.get_user_token('test_user')
        self.prepare_client('/multiuser/', user=user, token=token)
        task_inv = TaskInvitation.objects.filter(wf_name='multiuser',
                                                 role=self.client.current.role)
        assert task_inv.count() == 1

        task_inv.delete()

    def test_multi_user_owner_fail(self):
        Message.objects.delete()
        # Start the workflow with the first user
        wf_name = '/multiuser/'
        mananger_user = User.objects.get(username='test_user')
        self.prepare_client(wf_name, user=mananger_user)
        with BlockSave(Message):
            self.client.post()
        # The owners extension of the workflow limits the possible users, this user has the correct
        # permissions but is not included in owners, so shouldn't even receive the join message
        with pytest.raises(ObjectDoesNotExist) as exc_info:
            token, user = self.get_user_token('test_user3')
        assert exc_info.value.args[0].startswith('zengine_models_message')  # message doesn't exist
        # This user has the necessary permissions and relations, should have recieved the invitation
        token, user = self.get_user_token('test_user2')
        assert token
        TaskInvitation.objects.filter(wf_name='multiuser').delete()
