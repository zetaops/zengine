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
from zengine.models import User
from zengine.messaging.model import Message
from zengine.signals import lane_user_change


class TestCase(BaseTestCase):
    def test_multi_user_success(self):
        # Start the workflow with the first user
        test_user = User.objects.get(username='test_user')
        self.prepare_client('/multi_user2/', user=test_user)
        with BlockSave(Message):
            resp = self.client.post()
        assert resp.json['msgbox']['title'] == settings.MESSAGES['lane_change_message_title']
        # This user has the necessary permissions and relations, should be able to join the workflow
        token, user = self.get_user_token('test_user2')
        self.prepare_client('/multi_user2/', user=user, token=token)
        with BlockSave(Message):
            resp = self.client.post()
            resp.raw()
            resp = self.client.post()
            resp.raw()
        assert resp.json['msgbox']['title'] == settings.MESSAGES['lane_change_message_title']

    def test_multi_user_permission_fail(self):
        Message.objects.delete()
        # Start the workflow with the first user
        wf_name = '/multi_user/'
        self.prepare_client(wf_name, username='test_user')
        with BlockSave(Message):
            self.client.post()
        # This user is specified in owners so should recieve the workflow change message, but
        # doesn't have the permissions to join
        token, user = self.get_user_token('test_user2')
        self.prepare_client(wf_name, user=user, token=token)
        with pytest.raises(HTTPError) as exc_info:
            self.client.post()
        assert  exc_info.value[0] == 403
        assert 'You don\'t have required permission' in exc_info.value[1]

    def test_multi_user_owner_fail(self):
        Message.objects.delete()
        # Start the workflow with the first user
        wf_name = '/multi_user/'
        self.prepare_client(wf_name, username='test_user')
        with BlockSave(Message):
            self.client.post()
        # The owners extension of the workflow limits the possible users, this user has the correct
        # permissions but is not included in owners, so shouldn't even receive the join message
        with pytest.raises(ObjectDoesNotExist) as exc_info:
            token, user = self.get_user_token('test_user3')
        assert exc_info.value.message.startswith('zengine_models_message')  # message doesn't exist

    def test_multi_user_relation_fail(self):
        Message.objects.delete()
        # Start the workflow from the first user
        test_user = User.objects.get(username='test_user')
        self.prepare_client('/multi_user2/', user=test_user)
        with BlockSave(Message):
            resp = self.client.post()
        assert resp.json['msgbox']['title'] == settings.MESSAGES['lane_change_message_title']
        # This user doesn't have the necessary relation, thus shouldn't be able to join the workflow
        token, user = self.get_user_token('test_user3')
        self.prepare_client('/multi_user2/', user=user, token=token)
        with pytest.raises(HTTPError) as exc_info:
            self.client.post()
        assert exc_info.value[0] == 403
        assert 'You aren\'t qualified for this lane:' in exc_info.value[1]
