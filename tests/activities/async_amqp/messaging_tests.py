# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.lib.concurrent_amqp_test_client import ConcurrentTestCase


class TestCase(ConcurrentTestCase):
    def test_channel_list(self):
        self.ws1.client_to_backend({"view": "_zops_list_channels"},
                                   self.success_test_callback)

    def test_search_user(self):
        self.ws1.client_to_backend({"view": "_zops_search_user",
                                    "query":"x"},
                                   self.success_test_callback)







if __name__ == '__main__':
    TestCase()
