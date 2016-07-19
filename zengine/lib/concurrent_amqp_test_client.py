# -*-  coding: utf-8 -*-
"""
When a user is not online, AMQP messages that sent to this
user are discarded at users private exchange.
When user come back, offline sent messages will be loaded
from DB and send to users private exchange.

Because of this, we need to fully simulate 2 online users to test real time chat behaviour.

"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import uuid

import pika
from tornado.escape import json_encode, json_decode

from pyoko.conf import settings
from pyoko.lib.utils import get_object_from_path
from zengine.current import Current
from zengine.lib.cache import Session
from zengine.log import log
from zengine.tornado_server.ws_to_queue import QueueManager, NON_BLOCKING_MQ_PARAMS
import sys

from zengine.views.auth import Login

sys.sessid_to_userid = {}
UserModel = get_object_from_path(settings.USER_MODEL)


class TestQueueManager(QueueManager):
    def on_input_queue_declare(self, queue):
        """
        AMQP connection callback.
        Creates input channel.

        Args:
            connection: AMQP connection
        """
        log.info("input queue declared")
        super(TestQueueManager, self).on_input_queue_declare(queue)
        self.run_after_connection()

    def __init__(self, *args, **kwargs):
        super(TestQueueManager, self).__init__(*args, **kwargs)
        log.info("queue manager init")
        self.test_class = lambda qm: 1

    def conn_err(self, *args, **kwargs):
        log("conne err: %s %s" % (args, kwargs))

    def run_after_connection(self):
        log.info("run after connect")
        self.test_class(self)

    def set_test_class(self, kls):
        log.info("test class setted %s" % kls)
        self.test_class = kls


class TestWSClient(object):
    def __init__(self, queue_manager, username, sess_id=None):
        self.message_callbacks = {}
        self.message_stack = {}
        self.user = UserModel.objects.get(username=username)

        self.request = type('MockWSRequestObject', (object,), {'remote_ip': '127.0.0.1'})
        self.queue_manager = queue_manager
        # order is important!
        self.sess_id = sess_id or uuid.uuid4().hex
        sys.sessid_to_userid[self.sess_id] = self.user.key.lower()
        self.queue_manager.register_websocket(self.sess_id, self)
        self.login_user()
        # mimic tornado ws object
        # zengine.tornado_server.ws_to_queue.QueueManager will call write_message() method
        self.write_message = self.backend_to_client

    def login_user(self):
        session = Session(self.sess_id)
        current = Current(session=session, input={})
        current.auth.set_user(self.user)
        Login(current)._do_upgrade()

    def backend_to_client(self, body):
        """
        from backend to client
        """
        body = json_decode(body)
        try:
            self.message_callbacks[body['callbackID']](body)
        except KeyError:
            self.message_stack[body['callbackID']] = body
        log.info("WRITE MESSAGE TO CLIENT:\n%s" % (body,))

    def client_to_backend(self, message, callback):
        """
        from client to backend
        """
        cbid = uuid.uuid4().hex
        self.message_callbacks[cbid] = callback
        message = json_encode({"callbackID": cbid, "data": message})
        log.info("GOT MESSAGE FOR BACKEND %s: %s" % (self.sess_id, message))
        self.queue_manager.redirect_incoming_message(self.sess_id, message, self.request)


class ConcurrentTestCase(object):
    """
    Extend this class, define your test methods with "test_" prefix.



    """

    def __init__(self, queue_manager):
        from tornado import ioloop
        log.info("ConcurrentTestCase class init with %s" % queue_manager)
        ioloop = ioloop.IOLoop.instance()
        self.ws1 = self.get_client('ulakbus')
        self.ws2 = self.get_client('ogrenci_isleri_1')
        self.queue_manager = TestQueueManager(io_loop=ioloop)
        # initiate amqp manager
        self.queue_manager.set_test_class(self.run_tests)
        self.queue_manager.connect()
        ioloop.start()

    def get_client(self, username):
        """
        Args:
            username: username for this client instance

        Returns:
            Logged in TestWSClient instance for given username
        """
        return TestWSClient(self.queue_manager, username)

    def run_tests(self):
        for name in sorted(self.__class__.__dict__):
            if name.startswith("test_"):
                try:
                    getattr(self, name)()
                    print("%s succesfully passed" % name)
                except:
                    print("%s FAIL" % name)

    def success_test_callback(self, response, request=None):
        # print(response)
        assert response['code'] in (200, 201), "Process response not successful: \n %s \n %s" % (
            response, request
        )

    def test_channel_list(self):
        self.ws1.client_to_backend({"view": "_zops_list_channels"},
                                   self.success_test_callback)

    def test_search_user(self):
        self.ws1.client_to_backend({"view": "_zops_search_user",
                                    "query": "x"},
                                   self.success_test_callback)
