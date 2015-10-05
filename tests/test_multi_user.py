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
    def test_multi_user(self):
        self.prepare_client('multi_user')
        resp = self.client.post()
        resp.raw()
        resp = self.client.post()
        resp.raw()
        resp = self.client.post()
        resp.raw()
