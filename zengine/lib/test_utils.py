# -*-  coding: utf-8 -*-
import os
from time import sleep
import falcon
from falcon.errors import HTTPForbidden
from werkzeug.test import Client
from zengine.server import app
from pprint import pprint
import json
from zengine.models import User, Permission
from zengine.log import log


class RWrapper(object):
    def __init__(self, *args):
        self.content = list(args[0])
        self.code = args[1]
        self.headers = list(args[2])
        try:
            self.json = json.loads(self.content[0])
        except:
            self.json = {}

        self.token = self.json.get('token')

        if self.code == falcon.HTTP_403:
            self.raw()

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


# encrypted form of test password (123)
user_pass = '$pbkdf2-sha512$10000$nTMGwBjDWCslpA$iRDbnITHME58h1/eVolNmPsHVq' \
            'xkji/.BH0Q0GQFXEwtFvVwdwgxX4KcN/G9lUGTmv7xlklDeUp4DD4ClhxP/Q'

username = 'test_user'


class BaseTestCase:
    client = None
    # log = getlogger()

    @classmethod
    def create_user(self):
        self.client.user, new = User.objects.get_or_create({"password": user_pass},
                                                           username=username)
        if new:
            for perm in Permission.objects.raw("code:crud* OR code:login* OR code:User*"):
                self.client.user.Permissions(permission=perm)
            self.client.user.save()
            sleep(2)

    @classmethod
    def prepare_client(self, workflow_name, reset=False, login=True):
        """
        setups the workflow, logs in if necessary

        :param workflow_name: change or set workflow name
        :param reset: create a new client
        :param login: login to system
        :return:
        """
        if not self.client or reset:
            self.client = TestClient(workflow_name)
        if login and self.client.user is None:
            self.create_user()
            self._do_login()
        self.client.set_workflow(workflow_name)

    @classmethod
    def _do_login(self):
        """
        logs in the test user

        """
        self.client.set_workflow("login")
        resp = self.client.post()
        assert resp.json['forms']['schema']['title'] == 'LoginForm'
        assert not resp.json['is_login']
        resp = self.client.post(username=username, password="123", cmd="do")
        assert resp.json['is_login']
        # assert resp.json['msg'] == 'Success'
