# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.lib.test_utils import BaseTestCase


class TestCase(BaseTestCase):
    def test_login_fail(self):
        self.prepare_client('/login/', login=False)
        self.client.post()
        resp = self.client.post(username='wrong_user', password="WRONG_PASS", cmd="do")
        resp.raw()
        assert resp.json['status_code'] == 403

