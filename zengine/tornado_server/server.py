# -*-  coding: utf-8 -*-
"""
tornado websocket proxy for WF worker daemons
"""
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
import os, sys
import traceback
from uuid import uuid4
from tornado import websocket, web, ioloop
from tornado.escape import json_decode, json_encode
from tornado.httpclient import HTTPError
import pika
import time
import copy

sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))
from ws_to_queue import QueueManager, log, settings
from blocking_rpc import RpcClient

COOKIE_NAME = 'zopsess'
DEBUG = os.getenv("DEBUG", False)


class SocketHandler(websocket.WebSocketHandler):
    """
    websocket handler
    """

    def check_origin(self, origin):
        """
        Prevents CORS attacks.

        Args:
            origin: HTTP "Origin" header. URL of initiator of the request.

        Returns:
            True if origin is legit, otherwise False
        """
        # FIXME: implement CORS checking
        return True

    def _get_sess_id(self):
        # return self.sess_id;
        sess_id = self.get_cookie(COOKIE_NAME)
        return sess_id

    def open(self):
        """
        Called on new websocket connection.
        """
        sess_id = self._get_sess_id()
        if sess_id:
            self.application.pc.websockets[self._get_sess_id()] = self
            self.write_message(json.dumps({"cmd": "status", "status": "open"}))
        else:
            self.write_message(json.dumps({"cmd": "error", "error": "Please login", "code": 401}))

    def on_message(self, message):
        """
        called on new websocket message,
        """
        log.debug("WS MSG for %s: %s" % (self._get_sess_id(), message))
        self.application.pc.redirect_incoming_message(self._get_sess_id(), message, self.request)

    def on_close(self):
        """
        remove connection from pool on connection close.
        """
        self.application.pc.unregister_websocket(self._get_sess_id())


# noinspection PyAbstractClass
class HttpHandler(web.RequestHandler):
    """
    login handler class
    """



    def _handle_headers(self):
        """
        Do response processing
        """
        origin = self.request.headers.get('Origin')
        if not settings.DEBUG:
            if origin in settings.ALLOWED_ORIGINS or not origin:
                self.set_header('Access-Control-Allow-Origin', origin)
            else:
                log.debug("CORS ERROR: %s not allowed, allowed hosts: %s" % (origin,
                                                                             settings.ALLOWED_ORIGINS))
                raise HTTPError(403, "Origin not in ALLOWED_ORIGINS: %s" % origin)
        else:
            self.set_header('Access-Control-Allow-Origin', origin or '*')
        self.set_header('Access-Control-Allow-Credentials', "true")
        self.set_header('Access-Control-Allow-Headers', 'Content-Type')
        self.set_header('Access-Control-Allow-Methods', 'OPTIONS')
        self.set_header('Content-Type', 'application/json')

    def post(self):
        """
        login handler
        """
        sess_id = None
        input_data = {}
        # try:
        self._handle_headers()

        corr_id = uuid4().hex
        log.info("new colleration id: {}".format(corr_id))

        # handle input
        input_data = json_decode(self.request.body) if self.request.body else {}
        # input_data['path'] = view_name

        # set or get session cookie
        if not self.get_cookie(COOKIE_NAME) or 'username' in input_data:
            self.sess_id = uuid4().hex
            self.set_cookie(COOKIE_NAME, self.sess_id)  # , domain='127.0.0.1'

        else:
            self.sess_id = self.get_cookie(COOKIE_NAME)

        rpc_data = {'data': input_data,
                           '_zops_remote_ip': self.request.remote_ip,
                           '_zops_sess_id': self.sess_id,
                           '_zops_source': 'Remote',
                           }

        body = self.application.rpc_client.rpc_call(message=rpc_data)


        if body:
                self.write(body)
                log.info("wrintg body: %s" % body)
                self.finish()
        else:
            log.error(
                "asfasfasadas")
            self.finish()


URL_CONFS = [
    (r'/ws', SocketHandler),
    (r'/', HttpHandler),
]

app = web.Application(URL_CONFS, debug=DEBUG, autoreload=False)


def runserver(host=None, port=None):
    """
    Run Tornado server
    """
    host = host or os.getenv('HTTP_HOST', '0.0.0.0')
    port = port or os.getenv('HTTP_PORT', '9001')
    zioloop = ioloop.IOLoop.instance()

    # setup pika client:
    pc = QueueManager(io_loop=zioloop)
    app.pc = pc
    pc.connect()
    rpc = RpcClient()
    app.rpc_client = rpc
    app.listen(port, host)
    zioloop.start()


if __name__ == '__main__':
    runserver()
