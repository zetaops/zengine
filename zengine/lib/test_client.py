# -*-  coding: utf-8 -*-
import os
from time import sleep
from pyoko.model import model_registry
from werkzeug.test import Client
from zengine.log import getlogger
from zengine.server import app
from ulakbus.models import User, AbstractRole, Role
import os
from time import sleep
from pyoko.model import model_registry
from werkzeug.test import Client
from zengine.log import getlogger
from zengine.server import app
from ulakbus.models import User, AbstractRole, Role
from pprint import pprint
import json

class RWrapper(object):
    def __init__(self, *args):
        self.content = list(args[0])
        self.code = args[1]
        self.headers = list(args[2])
        try:
            self.json = json.loads(self.content[0])
            self.token = self.json.get('token')
        except:
            self.json = None

    def raw(self):
        pprint(self.code)
        pprint(self.json)
        pprint(self.headers)
        pprint(self.content)


class TestClient(object):
    def __init__(self, workflow):
        """
        this is a wsgi test client based on werkzeug.test.Client

        :param str workflow: workflow name
        """
        self.workflow = workflow
        self._client = Client(app, response_wrapper=RWrapper)
        self.user = None
        self.token = None

    def set_workflow(self, workflow):
        self.workflow = workflow
        self.token = ''

    def post(self, conf=None, **data):
        """
        by default data dict encoded as json and
        content type set as application/json

        :param dict conf: additional configs for test client's post method.
                          pass "no_json" in conf dict to prevent json encoding
        :param data: post data,
        :return: RWrapper response object
        :rtype: RWrapper
        """
        conf = conf or {}
        make_json = not conf.pop('no_json', False)
        if make_json:
            conf['content_type'] = 'application/json'
            if 'token' not in data and self.token:
                data['token'] = self.token
            data = json.dumps(data)
        response_wrapper = self._client.post(self.workflow, data=data, **conf)
        # update client token from response
        self.token = response_wrapper.token
        return response_wrapper

