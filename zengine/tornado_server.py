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
from zengine.receivers import *


from tornado import websocket, web, ioloop
import json

from zengine.views.auth import Login

cl = []

class IndexHandler(web.RequestHandler):
    def get(self):
        self.render("index.html")

class SocketHandler(websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        if self not in cl:
            cl.append(self)

    def on_close(self):
        if self in cl:
            cl.remove(self)

class LoginHandler(web.RequestHandler):


    @web.asynchronous
    def get(self, *args):
        self.finish()
        id = self.get_argument("id")
        value = self.get_argument("value")

        current = Current()
        Login(current)

    @web.asynchronous
    def post(self):
        pass

app = web.Application([
    # (r'/', IndexHandler),
    (r'/ws', SocketHandler),
    (r'/login/([^/]+)', LoginHandler),
])

if __name__ == '__main__':
    app.listen(9001)
    ioloop.IOLoop.instance().start()


