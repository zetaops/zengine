# -*-  coding: utf-8 -*-
import os
from time import sleep
import falcon
from falcon import errors
from werkzeug.test import Client
from zengine.server import app
from pprint import pprint
import json
from zengine.models import User, Permission
from zengine.log import log


CODE_EXCEPTION = {
    falcon.HTTP_400: errors.HTTPBadRequest,
    falcon.HTTP_401: errors.HTTPUnauthorized,
    falcon.HTTP_403: errors.HTTPForbidden,
    falcon.HTTP_404: errors.HTTPNotFound,
    falcon.HTTP_406: errors.HTTPNotAcceptable,
    falcon.HTTP_500: errors.HTTPInternalServerError,
    falcon.HTTP_503: errors.HTTPServiceUnavailable,
                  }
class RWrapper(object):

    def __init__(self, *args):
        self.content = list(args[0])
        self.code = args[1]
        self.headers = list(args[2])
        try:
            self.json = json.loads(self.content[0].decode('utf-8'))
        except:
            log.exception('ERROR at RWrapper JSON load')
            self.json = {}

        self.token = self.json.get('token')

        if int(self.code[:3]) >= 400:
            self.raw()
            if self.code in CODE_EXCEPTION:
                raise CODE_EXCEPTION[self.code](title=self.json.get('title'),
                                                description=self.json.get('description'))
            else:
                raise falcon.HTTPError(title=self.json.get('title'),
                                       description=self.json.get('description'))

    def raw(self):
        pprint(self.code)
        pprint(self.json)
        pprint(self.headers)
        pprint(self.content)


class TestClient(object):
    def __init__(self, path):
        """
        this is a wsgi test client based on werkzeug.test.Client

        :param str path: Request uri
        """
        self.set_path(path, None)
        self._client = Client(app, response_wrapper=RWrapper)
        self.user = None
        self.path = ''

    def set_path(self, path, token=''):
        self.path = path
        self.token = token

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
        response_wrapper = self._client.post(self.path, data=data, **conf)
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
    def create_user(cls):
        cls.client.user, new = User.objects.get_or_create({"password": user_pass,
                                                            "superuser": True},
                                                           username=username)
        if new:
            for perm in Permission.objects.raw("*:*"):
                cls.client.user.Permissions(permission=perm)
            cls.client.user.save()
            sleep(2)

    @classmethod
    def prepare_client(cls, path, reset=False, user=None, login=None, token=''):
        """
        setups the path, logs in if necessary

        :param path: change or set path
        :param reset: create a new client
        :param login: login to system
        :return:
        """

        if not cls.client or reset or user:
            cls.client = TestClient(path)
            login = True if login is None else login

        if not (cls.client.user or user):
            cls.create_user()
            login = True if login is None else login
        elif user:
            cls.client.user = user
            login = True if login is None else login

        if login:
            cls._do_login()

        cls.client.set_path(path, token)

    @classmethod
    def _do_login(self):
        """
        logs in the test user

        """
        self.client.set_path("/login/")
        resp = self.client.post()
        assert resp.json['forms']['schema']['title'] == 'LoginForm'
        assert not resp.json['is_login']
        resp = self.client.post(username=self.client.user.username,
                                password="123", cmd="do")
        assert resp.json['is_login']
        # assert resp.json['msg'] == 'Success'
