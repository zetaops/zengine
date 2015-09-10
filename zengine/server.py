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

import falcon
from beaker.middleware import SessionMiddleware
from pyoko.lib.utils import get_object_from_path

from zengine.config import settings
from zengine.engine import ZEngine

falcon_app = falcon.API(middleware=[get_object_from_path(mw_class)()
                                    for mw_class in settings.ENABLED_MIDDLEWARES])
app = SessionMiddleware(falcon_app, settings.SESSION_OPTIONS, environ_key="session")


class Connector(object):
    """
    this is object will be used to catch all requests from falcon
    and map them to workflow engine.
    a request to domain.com/show_dashboard/ will invoke a workflow
    named show_dashboard with the payload json data
    """
    def __init__(self):
        self.engine = ZEngine()

    def on_get(self, req, resp, wf_name):
        self.on_post(req, resp, wf_name)

    def on_post(self, req, resp, wf_name):
        self.engine.start_engine(request=req, response=resp,
                                 workflow_name=wf_name)
        self.engine.run()


workflow_connector = Connector()
falcon_app.add_route('/{wf_name}/', workflow_connector)
