# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from time import sleep
import falcon
import pytest
from zengine.lib.test_utils import BaseTestCase, user_pass
from zengine.models import User


class TestCase(BaseTestCase):
    def test_multi_user_mono(self):
        self.prepare_client('multi_user')
        resp = self.client.post()
        resp.raw()
        resp = self.client.post()
        resp.raw()
        resp = self.client.post()
        resp.raw()

    @classmethod
    def create_wrong_user(cls):
        user, new = User.objects.get_or_create({"password": user_pass,
                                                           "superuser": True},
                                                          username='wrong_user')
        if new:
            sleep(2)
        return user

    def test_multi_user_with_fail(self):
        wf_name = 'multi_user'
        self.prepare_client(wf_name)
        resp = self.client.post()
        wf_token = self.client.token
        new_user = self.create_wrong_user()
        self.prepare_client(wf_name, user=new_user, token=wf_token)
        with pytest.raises(falcon.errors.HTTPForbidden):
            self.client.post()

