# -*-  coding: utf-8 -*-
"""
We created a Falcon based WSGI server.
Integrated session support with beaker.
Then route all requests to ZEngine.run() that runs SpiffWorkflow engine
and invokes associated activity methods.

Request and response objects for json data processing done at the middleware layer,
thus, activity methods (which will be invoked from workflow engine)
can simply read json data from current.input and write back to current.output

"""
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
import traceback
from falcon.http_error import HTTPError
import falcon
from beaker.middleware import SessionMiddleware
from pyoko.lib.utils import get_object_from_path
from zengine.log import log

from zengine.config import settings
from zengine.engine import ZEngine, Current

# receivers should be imported at right time, right place
# they will not registered if not placed in a central location
# but they can cause "cannot import settings" errors if imported too early
from zengine.pica_client import PikaClient
from zengine.receivers import *
from uuid import uuid4

from tornado import websocket, web, ioloop
import json

# import pika
import time

# connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
# channel = connection.channel()
# channel2 = connection.channel()

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
        return self.get_cookie(COOKIE_NAME)

    def open(self):
        sess_id = self.get_cookie(COOKIE_NAME)
        self.application.pc.register_websocket(self._get_sess_id(), self)

    def on_message(self, message):
        self.application.pc.send_message(self._get_sess_id(), message)

    def on_close(self):
        """
        remove connection from pool on connection close.
        """
        self.application.pc.unregister_websocket(self._get_sess_id())

class LoginHandler(web.RequestHandler):

    @web.asynchronous
    def get(self, *args):
        self.finish()

    @web.asynchronous
    def post(self):
        self.set_cookie(COOKIE_NAME, self._create_hash())

    def _create_hash(self):
        return uuid4().hex

    def _get_send_socket(self, client_hash):
        return CLIENT_SOCKETS[client_hash]


app = web.Application([
    # (r'/', IndexHandler),
    (r'/ws', SocketHandler),
    (r'/login/([^/]+)', LoginHandler),
])

if __name__ == '__main__':

    zioloop = ioloop.IOLoop.instance()

    # setup pika client
    pc = PikaClient(zioloop)
    app.pc = pc
    pc.connect()
    app.listen(9001)
    zioloop.start()


