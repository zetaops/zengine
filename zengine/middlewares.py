import json
import falcon
from zengine.config import settings
from zengine.log import log


class CORS(object):
    """
    allow origins
    """

    def process_response(self, request, response, resource):
        origin = request.get_header('Origin')
        if origin in settings.ALLOWED_ORIGINS or not origin:
            response.set_header(
                'Access-Control-Allow-Origin',
                origin
            )
        else:
            raise falcon.HTTPForbidden("Denied", "Origin not in ALLOWED_ORIGINS: %s" % origin)
            response.status = falcon.HTTP_403

        response.set_header(
            'Access-Control-Allow-Credentials',
            "true"
        )
        response.set_header(
            'Access-Control-Allow-Headers',
            'Content-Type'
        )
        # This could be overridden in the resource level
        response.set_header(
            'Access-Control-Allow-Methods',
            'OPTIONS'
        )


class RequireJSON(object):
    def process_request(self, req, resp):
        if not req.client_accepts_json:
            raise falcon.HTTPNotAcceptable(
                'This API only supports responses encoded as JSON.',
                href='http://docs.examples.com/api/json')
        if req.method in ('POST', 'PUT'):
            if req.content_length != 0 and 'application/json' not in req.content_type and 'text/plain' not in req.content_type:
                raise falcon.HTTPUnsupportedMediaType(
                    'This API only supports requests encoded as JSON.',
                    href='http://docs.examples.com/api/json')


class JSONTranslator(object):
    def process_request(self, req, resp):
        # req.stream corresponds to the WSGI wsgi.input environ variable,
        # and allows you to read bytes from the request body.
        #
        # See also: PEP 3333
        if req.content_length in (None, 0):
            # Nothing to do
            req.context['data'] = {}
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
        if 'result' not in req.context:
            return
        req.context['result']['is_login'] = 'user_id' in req.env['session']
        # print(":::::body: %s\n\n:::::result: %s" % (resp.body, req.context['result']))
        if resp.body is None and req.context['result']:
            resp.body = json.dumps(req.context['result'])


        try:
            log.info("RESPONSE: %s" % resp.body)
        except:
            log.exception("ERR: RESPONSE CANT BE LOGGED ")


