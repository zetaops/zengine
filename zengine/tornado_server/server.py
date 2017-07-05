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

sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))
from ws_to_queue import QueueManager, log, settings

COOKIE_NAME = 'zopsess'
DEBUG = os.getenv("DEBUG", False)
# blocking_connection = BlockingConnectionForHTTP()


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

    @web.asynchronous
    def get(self, view_name):
        """
        only used to display login form

        Args:
            view_name: should be "login"

        """
        self.post(view_name)

    @web.asynchronous
    def post(self, view_name):
        """
        login handler
        """
        sess_id = None
        input_data = {}
        # try:
        self._handle_headers()

        # handle input
        input_data = json_decode(self.request.body) if self.request.body else {}
        input_data['path'] = view_name

        # set or get session cookie
        if not self.get_cookie(COOKIE_NAME) or 'username' in input_data:
            sess_id = uuid4().hex
            self.set_cookie(COOKIE_NAME, sess_id)  # , domain='127.0.0.1'
        else:
            sess_id = self.get_cookie(COOKIE_NAME)
        # h_sess_id = "HTTP_%s" % sess_id
        input_data = {'data': input_data,
                      '_zops_remote_ip': self.request.remote_ip}
        log.info("New Request for %s: %s" % (sess_id, input_data))

        self.application.pc.register_websocket(sess_id, self)
        self.application.pc.redirect_incoming_message(sess_id,
                                                      json_encode(input_data),
                                                      self.request)

    def write_message(self, output):
        log.debug("WRITE MESSAGE To CLIENT: %s" % output)
        # if 'login_process' not in output:
        #     # workaround for premature logout bug (empty login form).
        #     # FIXME: find a better way to handle HTTP and SOCKET connections for same sess_id.
        #     return
        self.write(output)
        self.finish()
        self.flush()




URL_CONFS = [
    (r'/ws', SocketHandler),
    (r'/(\w+)', HttpHandler),
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
    pc = QueueManager(zioloop)
    app.pc = pc
    pc.connect()
    app.listen(port, host)
    zioloop.start()


if __name__ == '__main__':
    runserver()
