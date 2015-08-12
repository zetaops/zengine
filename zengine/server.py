# -*-  coding: utf-8 -*-
"""
We created a Falcon based WSGI server.
Integrated session support with beaker.
Then route all requests to workflow engine.

We process request and response objects for json data in middleware layer,
so activity methods (which will be invoked from workflow engine)
can read json data from request.input
and writeback to request.output

"""
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

import falcon
from beaker.middleware import SessionMiddleware
from zengine.lib.utils import DotDict
from zengine.config import ENABLED_MIDDLEWARES, SESSION_OPTIONS
from zengine.engine import ZEngine


class ZRequest(falcon.Request):
    context_type = DotDict


falcon_app = falcon.API(middleware=ENABLED_MIDDLEWARES, request_type=ZRequest)
app = SessionMiddleware(falcon_app, SESSION_OPTIONS, environ_key="session")


class Connector(object):
    """
    this is a callable object to catch all requests and map them to workflow engine.
    domain.com/show_dashboard/blah/blah/x=2&y=1 will invoke a workflow named show_dashboard
    """
    # def __init__(self):
    # self.logger = logging.getLogger('dispatch.' + __name__)
    def __init__(self):
        self.engine = ZEngine()

    def on_get(self, req, resp, wf_name):
        self.on_post(req, resp, wf_name)

    def on_post(self, req, resp, wf_name):
        self.engine.current.update(request=req,
                                response=resp,
                                workflow_name=wf_name,
                                )
        self.engine.process_client_commands(req.context['data'], wf_name)
        self.engine.load_or_create_workflow()
        self.engine.run()


workflow_connector = Connector()
falcon_app.add_route('/{wf_name}/', workflow_connector)


def runserver(port=9001, addr='0.0.0.0'):
    from wsgiref import simple_server
    httpd = simple_server.make_server(addr, port, app)
    httpd.serve_forever()


# Useful for debugging problems in your API; works with pdb.set_trace()
if __name__ == '__main__':
    runserver()
