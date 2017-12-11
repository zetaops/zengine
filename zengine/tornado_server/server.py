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

sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))
from ws_to_queue import QueueManager, log, settings

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

    response_queue = {}

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
    def post(self):
        """
        login handler
        """
        sess_id = None
        input_data = {}
        # try:
        self._handle_headers()

        self.corr_id = uuid4().hex
        log.info("new colleration id: {}".format(self.corr_id) )

        # handle input
        input_data = json_decode(self.request.body) if self.request.body else {}
        # input_data['path'] = view_name

        # set or get session cookie
        if not self.get_cookie(COOKIE_NAME) or 'username' in input_data:
            self.sess_id = uuid4().hex
            self.set_cookie(COOKIE_NAME, self.sess_id)  # , domain='127.0.0.1'

        else:
            self.sess_id = self.get_cookie(COOKIE_NAME)

        self.input_data = {'data': input_data,
                           '_zops_remote_ip': self.request.remote_ip,
                           '_zops_sess_id': self.sess_id,
                           '_zops_source': 'Remote',
                           }

        log.info("New Request for %s: %s" % (self.sess_id, self.input_data))

        self.queue_name = "rpc_queue_{}".format(self.sess_id)

        self.application.pc.in_channel.queue_declare(exclusive=True, queue=self.queue_name,
                                                     callback=None)

        log.info("queue {} declared...".format(self.queue_name))

        self.application.pc.in_channel.queue_bind(exchange='output_exc',
                                                  queue=self.queue_name,
                                                  routing_key=self.sess_id,
                                                  callback=self.on_queue_bind)
        log.info("queue {} binded with {}...".format(self.queue_name, self.sess_id))

    def on_queue_bind(self, frame):

        log.info('consuming... consuming..')
        self.application.pc.in_channel.basic_consume(self.on_rpc_response,
                                                     queue=self.queue_name, no_ack=True)

        props = pika.BasicProperties(
            delivery_mode=1,
            correlation_id=self.corr_id,
            reply_to=self.sess_id)

        log.info('Publish rpc call. Self Corr ID: {}'.format(self.corr_id))
        self.application.pc.in_channel.basic_publish(exchange='input_exc',
                                                     routing_key=self.sess_id,
                                                     body=json_encode(self.input_data),
                                                     properties=props, mandatory=1)

    def on_rpc_response(self, channel, method, header, body):
        self.response_queue[header.correlation_id] = body
        if header.correlation_id == self.corr_id:
            self.write(body)
            log.info("wrintg body: %s" % body)
            self.finish()


        else:
            lg = "rpc response failed: #{0}, Corr ID: {2} | Self Corr ID: {3}"
            log.error(lg.format(method.delivery_tag, header.correlation_id, self.corr_id))


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
    app.listen(port, host)
    zioloop.start()


if __name__ == '__main__':
    runserver()
