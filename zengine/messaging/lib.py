# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import pika


class BaseUser(object):
    connection = None
    channel = None


    def _connect_mq(self):
        if not self.connection is None or self.connection.is_closed:
            self.connection = pika.BlockingConnection(BLOCKING_MQ_PARAMS)
            self.channel = selfconnection.channel()
        return self.channel


    def send_message(self, title, message, sender=None, url=None, typ=1):
        channel = self._connect_mq()
        mq_msg = json.dumps(dict(sender=sender, body=message, msg_title=title, url=url, typ=typ))
        channel.basic_publish(exchange=self.key, body=mq_msg)
