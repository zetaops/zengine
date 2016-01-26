# -*-  coding: utf-8 -*-
"""
We created a Falcon based WSGI server.
Integrated session support with beaker.
Then route all requests to ZEngine.run() that runs SpiffWorkflow engine
and invokes associated activity methods.

Request and response objects for json data processing at middleware layer,
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

from zengine.config import settings
from zengine.engine import ZEngine, Current

# receivers should be imported at right time, right place
# they will not registered if not placed in a central location
# but they can cause "cannot import settings" errors if imported too early
from zengine.receivers import *

falcon_app = falcon.API(middleware=[get_object_from_path(mw_class)()
                                    for mw_class in settings.ENABLED_MIDDLEWARES])
app = SessionMiddleware(falcon_app, settings.SESSION_OPTIONS, environ_key="session")


# class crud_handler(object):
#     """
#     this object redirects /ModelName/ type queries to /crud with ModelName as part of JSON payload
#     """
#     @staticmethod
#     def on_get(req, resp, model_name):
#         req.context['data']['model'] = model_name
#         wf_connector(req, resp, 'crud')
#
#     @staticmethod
#     def on_post(req, resp, model_name):
#         req.context['data']['model'] = model_name
#         wf_connector(req, resp, 'crud')


wf_engine = ZEngine()


def wf_connector(req, resp, wf_name):
    """
    This will be used to catch all unhandled requests from falcon and
    map them to workflow engine.

    A request to http://HOST_NAME/show_dashboard/ will invoke a workflow
    named show_dashboard with the payload json data
    """
    try:
        wf_engine.start_engine(request=req, response=resp, workflow_name=wf_name)
        wf_engine.run()
    except HTTPError:
        raise
    except:
        if settings.DEBUG:
            resp.status = falcon.HTTP_500
            resp.body = json.dumps({'error': traceback.format_exc()})
        else:
            raise


def view_connector(view_path):
    """
    A connector for non-workflow views
    """

    view = get_object_from_path(view_path)
    class Caller(object):
        @staticmethod
        def on_get(req, resp, *args, **kwargs):
            Caller.on_post(req, resp, *args, **kwargs)

        @staticmethod
        def on_post(req, resp, *args, **kwargs):
            try:
                current = Current(request=req, response=resp)
                if not (current.is_auth or view_path in settings.ANONYMOUS_WORKFLOWS):
                    raise falcon.HTTPUnauthorized("Login required", view_path)
                view(current, *args, **kwargs)
            except HTTPError:
                raise
            except:
                if settings.DEBUG:
                    resp.status = falcon.HTTP_500
                    resp.body = json.dumps({'error': traceback.format_exc()})
                else:
                    raise

    return Caller


# falcon_app.add_route('/crud/{model_name}/', crud_handler)

for url, view_path in settings.VIEW_URLS:
    falcon_app.add_route(url, view_connector(view_path))

falcon_app.add_sink(wf_connector, '/(?P<wf_name>.*)')


class Ping(object):
    @staticmethod
    def on_get(req, resp):
        resp.body = 'OK'


falcon_app.add_route('/ping', Ping)
