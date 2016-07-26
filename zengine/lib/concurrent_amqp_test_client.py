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
from __future__ import print_function

import inspect
import uuid
from pprint import pprint, pformat

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
        try:
            body = json_decode(body)
            if 'callbackID' in body:
                self.message_stack[body['callbackID']] = body
                self.message_callbacks[body['callbackID']](body)
            elif 'cmd' in body:
                self.message_callbacks[body['cmd']](body)
        except:
            import traceback
            print("\nException BODY: %s \n" % pformat(body))
            traceback.print_exc()

        log.info("WRITE MESSAGE TO CLIENT:\n%s" % (pformat(body),))

    def client_to_backend(self, message, callback, caller_fn_name):
        """
        from client to backend
        """
        cbid = uuid.uuid4().hex
        message = json_encode({"callbackID": cbid, "data": message})
        def cb(res):
            print("API Request: %s :: " % caller_fn_name, end='')
            result = callback(res, message)
            if ConcurrentTestCase.stc == callback and not result:
                FAIL = 'FAIL'
            else:
                FAIL = '--> %s' % callback.__name__
            print('PASS' if result else FAIL)
        # self.message_callbacks[cbid] = lambda res: callable(res, message)
        self.message_callbacks[cbid] = cb
        log.info("GOT MESSAGE FOR BACKEND %s: %s" % (self.sess_id, message))
        self.queue_manager.redirect_incoming_message(self.sess_id, message, self.request)


class ConcurrentTestCase(object):
    """
    Extend this class, define your test methods with "test_" prefix.



    """

    def __init__(self, queue_manager):
        log.info("ConcurrentTestCase class init with %s" % queue_manager)
        self.cmds = {}
        self.register_cmds()
        self.queue_manager = queue_manager
        self.clients = {}
        self.make_client('ulakbus')
        self.run_tests()

    def make_client(self, username):
        """
        Args:
            username: username for this client instance

        Returns:
            Logged in TestWSClient instance for given username
        """
        self.clients[username] = TestWSClient(self.queue_manager, username)



    def post(self, username, data, callback=None):
        if username not in self.clients:
            self.make_client(username)
        self.clients[username].message_callbacks.update(self.cmds)
        callback = callback or self.stc
        view_name = data['view'] if 'view' in data else sys._getframe(1).f_code.co_name
        self.clients[username].client_to_backend(data, callback, view_name)

    def register_cmds(self):
        for name in sorted(self.__class__.__dict__):
            if name.startswith("cmd_"):
                self.cmds[name[4:]] = getattr(self, name)

    def run_tests(self):
        for name in sorted(self.__class__.__dict__):
            if name.startswith("test_"):
                try:
                    getattr(self, name)()
                except:
                    import traceback
                    traceback.print_exc()

    def process_error_reponse(self, resp):
        if 'error' in resp:
            print(resp['error'].replace('\\n','\n').replace('u\\', ''))
            return True

    def stc(self, response, request=None):
        """
        STC means Success Test Callback. Looks for 200 or 201 codes in response code.

        Args:
            response:
            request:
        """
        try:
            if not response['code'] in (200, 201):
                print("FAILED: Response not successful: \n")
                if not self.process_error_reponse(response):
                    print("\nRESP:\n%s")
                print("\nREQ:\n %s" % (response, request))
            else:
                return True
        except Exception as e:
            log.exception("\n===========>\nFAILED API REQUEST\n<===========\n%s\n" % e)
            log.info("Response: \n%s\n\n" % response)

    def pstc(self, response, request=None):
        """
        Same as self.stc() (success request callback) but printing response/request
        for debugging purposes

        Args:
            response:
            request:

        """
        self.stc(response, request)
        print("\n\n=================\n\nRESPONSE: %s \n\nREQUEST: %s\n" % (response, request))



def main():
    from tornado import ioloop
    # initiate amqp manager
    ioloop = ioloop.IOLoop.instance()
    qm = TestQueueManager(io_loop=ioloop)

    # initiate test case
    qm.set_test_class(ConcurrentTestCase)

    qm.connect()
    ioloop.start()


if __name__ == '__main__':
    main()
