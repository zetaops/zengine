# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import falcon
from zengine.lib.test_utils import BaseTestCase


class TestCase(BaseTestCase):
    def test_login_fail(self):
        self.prepare_client('login', reset=True, login=False)
        resp = self.client.post()
        # resp.raw()

        # wrong username
        resp = self.client.post(username="test_loser", password="123", cmd="do")
        # resp.raw()


        self.client.set_workflow('logout')
        resp = self.client.post()

        # resp.raw()
        # not logged in so cannot logout, should got an error
        assert resp.code == falcon.HTTP_401
