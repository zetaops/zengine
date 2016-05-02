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
from riak.client import binary_json_decoder

from pyoko.lib.utils import get_object_from_path
from pyoko.modelmeta import model_registry
from zengine.lib.cache import ClearCache
from zengine.log import log

from zengine.config import settings
from zengine.engine import ZEngine, Current

# receivers should be imported at right time, right place
# they will not registered if not placed in a central location
# but they can cause "cannot import settings" errors if imported too early
from zengine.receivers import *

falcon_app = falcon.API(middleware=[get_object_from_path(mw_class)()
                                    for mw_class in settings.ENABLED_MIDDLEWARES])
app = SessionMiddleware(falcon_app, settings.SESSION_OPTIONS, environ_key="session")

wf_engine = ZEngine()


def wf_connector(req, resp, wf_name):
    """
    This will be used to catch all unhandled requests from falcon and
    map them to workflow engine.

    A request to `http://HOST_NAME/show_dashboard/` will invoke a workflow
    named *show_dashboard* with the payload json data

    Args:
        wf_name (str): Workflow name
        resp: Falcon Response object.
        req: Falcon Request object.
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
            log.exception("500ERROR")
            raise falcon.HTTPInternalServerError("Internal Error",
                                                 settings.ERROR_MESSAGE_500)


def view_connector(view_path):
    """
    A factory method for non-workflow views.

    Falcon's `add_route` method requires an object that
    implements on_get, on_post or on_put methods. This
    method returns a handler object that calls the given
    view class / function.

    Prevention of unauthenticated access and re-raising of
    internal server errors also done at this stage.

    Args:
        view_path: Python path of the view class/function.
    """

    view = get_object_from_path(view_path)

    # noinspection PyMissingOrEmptyDocstring
    class Caller(object):
        @staticmethod
        def on_get(req, resp, *args, **kwargs):
            """
            GET method http handler

            Args:
                req: Request object.
                resp: Response object
            """
            Caller.on_post(req, resp, *args, **kwargs)

        @staticmethod
        def on_post(req, resp, *args, **kwargs):
            """
                POST method http handler

                Args:
                    req: Request object.
                    resp: Response object
            """
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
                    log.exception("500ERROR")
                    raise falcon.HTTPInternalServerError("Internal Error",
                                                         settings.ERROR_MESSAGE_500)

    return Caller


for url, view_path in settings.VIEW_URLS:
    falcon_app.add_route(url, view_connector(view_path))

falcon_app.add_sink(wf_connector, '/(?P<wf_name>.*)')


class Ping(object):
    """
    Simple ping view for health checks
    """

    @staticmethod
    def on_get(req, resp):
        """
        GET method handler
        Args:
            req: Request object.
            resp: Response object.
        """
        resp.body = 'OK'


falcon_app.add_route('/ping', Ping)

class DBStats(object):
    """
    various stats
    """

    @staticmethod
    def on_get(req, resp):
        import sys
        """
        GET method handler
        Args:
            req: Request object.
            resp: Response object.
        """
        read_existing = set(sys.PYOKO_LOGS['read']) - set(sys.PYOKO_LOGS['new'])
        resp.body = "DB Access Stats: {}".format(str(sys.PYOKO_STAT_COUNTER),
                              str(read_existing))
        sys.PYOKO_LOGS = {
            "save": 0,
            "update": 0,
            "read": 0,
            "count": 0,
            "search": 0,
        }




class ReadKeys(object):
    """
    Export read keys
    """

    @staticmethod
    def on_get(req, resp):
        import sys
        """
        GET method handler
        Args:
            req: Request object.
            resp: Response object.
        """
        out = []
        for mdl_name in sys.PYOKO_LOGS.copy():
            try:
                mdl = model_registry.get_model(mdl_name)
            except KeyError:
                continue
            bucket_name = mdl.objects.bucket.name
            mdl.objects.bucket.set_decoder('application/json', lambda a: a)
            for k in set(sys.PYOKO_LOGS[mdl_name]):
                if k not in sys.PYOKO_LOGS['new']:
                    out.append("{}/|{}/|{}".format(
                        bucket_name, k, mdl.objects.data().get(k)[0]))
                    # print(str(mdl.objects.get(k).name))
            sys.PYOKO_LOGS[mdl_name] = []
            mdl.objects.bucket.set_decoder('application/json', binary_json_decoder)
        sys.PYOKO_LOGS['new'] = []
        resp.body = "\n".join(out)



class ResetCache(object):
    """
    Clears all cache entries
    """

    @staticmethod
    def on_get(req, resp):
        """
        GET method handler
        Args:
            req: Request object.
            resp: Response object.
        """

        resp.body = "Following cache entries are removed!\n\n"+"\n".join(ClearCache().flush())

if settings.DEBUG:
    falcon_app.add_route('/read_keys', ReadKeys)
    falcon_app.add_route('/db_stats', DBStats)
    falcon_app.add_route('/reset_cache', ResetCache)
