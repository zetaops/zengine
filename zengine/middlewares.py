# -*-  coding: utf-8 -*-
"""
Middlewares for request / response handling.
"""
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
import falcon
import sys
from zengine.config import settings
from zengine.log import log


class CORS(object):
    """
    Sets required headers to allow origins for the hosts listed in
    :attr:`~zengine.settings.ALLOWED_ORIGINS`

    Note:
        When :attr:`~zengine.settings.DEBUG` set to ``True``
        all hosts are allowed
    """

    def process_response(self, request, response, resource):
        """
        Do response processing
        """
        origin = request.get_header('Origin')
        if not settings.DEBUG:
            if origin in settings.ALLOWED_ORIGINS or not origin:
                response.set_header('Access-Control-Allow-Origin', origin)
            else:
                log.debug("CORS ERROR: %s not allowed, allowed hosts: %s" % (origin,
                                                                             settings.ALLOWED_ORIGINS))
                raise falcon.HTTPForbidden("Denied", "Origin not in ALLOWED_ORIGINS: %s" % origin)
                # response.status = falcon.HTTP_403
        else:
            response.set_header('Access-Control-Allow-Origin', origin or '*')

        response.set_header('Access-Control-Allow-Credentials', "true")
        response.set_header('Access-Control-Allow-Headers', 'Content-Type')
        # This could be overridden in the resource level
        response.set_header('Access-Control-Allow-Methods', 'OPTIONS')


class RequireJSON(object):
    """
    Restrict only to JSON payloads.
    """
    def process_request(self, req, resp):
        """
        Do response processing
        """
        if not req.client_accepts_json:
            raise falcon.HTTPNotAcceptable(
                'This API only supports responses encoded as JSON.',
                href='http://docs.examples.com/api/json')
        if req.method in ('POST', 'PUT'):
            if req.content_length != 0 and \
                            'application/json' not in req.content_type and \
                            'text/plain' not in req.content_type:
                raise falcon.HTTPUnsupportedMediaType(
                    'This API only supports requests encoded as JSON.',
                    href='http://docs.examples.com/api/json')


class JSONTranslator(object):
    """
    Deserializes JSON payload into ``request.context['data']``
    """
    def process_request(self, req, resp):
        """
        Do response processing
        """
        # req.stream corresponds to the WSGI wsgi.input environ variable,
        # and allows you to read bytes from the request body.
        #
        # See also: PEP 3333
        if req.content_length in (None, 0):
            # Nothing to do
            req.context['data'] = req.params.copy()
            req.context['result'] = {}
            return
        else:
            req.context['result'] = {}

        body = req.stream.read()
        if not body:
            raise falcon.HTTPBadRequest('Empty request body',
                                        'A valid JSON document is required.')

        try:
            json_data = body.decode('utf-8')
            req.context['data'] = json.loads(json_data)
            try:
                log.info("REQUEST DATA: %s" % json_data)
            except:
                log.exception("ERR: REQUEST DATA CANT BE LOGGED ")
        except (ValueError, UnicodeDecodeError):
            raise falcon.HTTPError(falcon.HTTP_753,
                                   'Malformed JSON',
                                   'Could not decode the request body. The '
                                   'JSON was incorrect or not encoded as '
                                   'UTF-8.')

    def process_response(self, req, resp, resource):
        """
        Serializes ``req.context['result']`` to resp.body as JSON.

        If :attr:`~zengine.settings.DEBUG` is True,
        ``sys._debug_db_queries`` (set by pyoko) added to response.

        """
        if 'result' not in req.context:
            return
        req.context['result']['is_login'] = 'user_id' in req.env['session']
        if settings.DEBUG:
            req.context['result']['_debug_queries'] = sys._debug_db_queries
            sys._debug_db_queries = []
        if resp.body is None and req.context['result']:
            resp.body = json.dumps(req.context['result'])

        try:
            log.debug("RESPONSE: %s" % resp.body)
        except:
            log.exception("ERR: RESPONSE CANT BE LOGGED ")
