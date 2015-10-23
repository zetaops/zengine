# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import falcon
import pytest
from zengine.lib.test_utils import BaseTestCase, RWrapper


class TestCase(BaseTestCase):
    def test_login_fail(self):
        self.prepare_client('/login/', reset=True, login=False)
        resp = self.client.post()
        # resp.raw()

        # wrong username
        with pytest.raises(falcon.errors.HTTPForbidden):
            self.client.post(username="test_loser", password="123", cmd="do")
        # resp.raw()

        self.client.set_path('/logout/')

        # not logged in so cannot logout, should got an error
        with pytest.raises(falcon.errors.HTTPUnauthorized):
            self.client.post()

