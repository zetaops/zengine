# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.lib.concurrent_amqp_test_client import ConcurrentTestCase, TestQueueManager


class TestCase(ConcurrentTestCase):
    def test_channel_list(self):
        self.post('ulakbus', {"view": "_zops_list_channels"})

    def test_search_user(self):
        self.post('ulakbus', {"view": "_zops_search_user",
                                    "query": "x"})

    def test_show_channel(self):
        self.post('ulakbus',
                  {"view": "_zops_show_channel",
             'channel_key': 'iG4mvjQrfkvTDvM6Jk56X5ILoJ_CoqwpemOHnknn3hYu1BlAghb3dm'})

    def test_create_message(self):
        self.post('ulakbus',
                  {"view": "_zops_create_message",
             "message": dict(
                 body='test_body', title='testtitle',
                 channel='iG4mvjQrfkvTDvM6Jk56X5ILoJ_CoqwpemOHnknn3hYu1BlAghb3dm',
                 receiver='',
                 type=2
             )})


def main():
    from tornado import ioloop
    # initiate amqp manager
    ioloop = ioloop.IOLoop.instance()
    qm = TestQueueManager(io_loop=ioloop)

    # initiate test case
    qm.set_test_class(TestCase)

    qm.connect()
    ioloop.start()


if __name__ == '__main__':
    main()
