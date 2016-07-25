# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.lib.concurrent_amqp_test_client import ConcurrentTestCase, TestQueueManager


class TestCase(ConcurrentTestCase):
    def __init__(self, *args, **kwargs):
        super(TestCase, self).__init__(*args, **kwargs)

    def test_channel_list(self):
        self.post('ulakbus', dict(view="_zops_list_channels"), self.show_channel)

    def test_search_user(self):
        self.post('ulakbus',
                  dict(view="_zops_search_user", query="x"))

    def show_channel(self, res, req):
        ch_key = res['channels'][0]['key']
        self.post('ulakbus',
                  dict(view="_zops_show_channel", channel_key=ch_key),
                  self.create_message)

    def create_message(self, res, req):
        self.post('ulakbus',
                  {"view": "_zops_create_message",
                   "message": dict(
                       body='test_body', title='testtitle',
                       channel=res['key'],
                       receiver='',
                       type=2
                   )})

    def cmd_user_status(self, res, req):
        print("CMD: user_status:")
        print(res)

    def cmd_message(self, res, req=None):
        print("MESSAGE RECEIVED")
        print(res)


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
