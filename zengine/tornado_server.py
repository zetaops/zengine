# -*-  coding: utf-8 -*-
"""
tornado websocket proxy for WF worker daemons
"""
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.pika_client import PikaClient
from uuid import uuid4

from tornado import websocket, web, ioloop
import logging

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)
COOKIE_NAME = 'zopsess'
CLIENT_SOCKETS = {}

class IndexHandler(web.RequestHandler):
    def get(self):
        self.render("index.html")

class SocketHandler(websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def _get_sess_id(self):
        return self.sess_id;
        sess_id = self.get_cookie(COOKIE_NAME)
        # print("Got session cookie: %s" % sess_id)
        return sess_id

    def open(self):
        # sess_id = self._get_sess_id()
        sess_id = self.sess_id = uuid4().hex
        if sess_id:
            self.application.pc.register_websocket(self._get_sess_id(), self)
        else:
            print("no session, no joy!")

    def on_message(self, message):
        # print("Got WS Message: %s" % message)
        self.application.pc.redirect_incoming_message(self._get_sess_id(), message)

    def on_close(self):
        """
        remove connection from pool on connection close.
        """
        print("Websocket closed")
        self.application.pc.unregister_websocket(self._get_sess_id())

class LoginHandler(web.RequestHandler):




    @web.asynchronous
    def post(self):
        self.set_header('Access-Control-Allow-Origin', '*')
        sess_id = self._create_hash()
        self.set_cookie(COOKIE_NAME, sess_id)  # , domain='127.0.0.1'
        print("Set session cookie: %s" % sess_id)
        self.finish()

    def _create_hash(self):
        return uuid4().hex


app = web.Application([
    # (r'/', IndexHandler),
    (r'/ws', SocketHandler),
    (r'/login', LoginHandler),
])

def runserver():
    zioloop = ioloop.IOLoop.instance()

    # setup pika client
    pc = PikaClient(zioloop)
    app.pc = pc
    pc.connect()
    app.listen(9001)
    zioloop.start()

if __name__ == '__main__':
    runserver()

