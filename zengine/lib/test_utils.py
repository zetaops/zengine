# -*-  coding: utf-8 -*-
from uuid import uuid4
from time import sleep
import json
import os

from pyoko.conf import settings
from pyoko.manage import FlushDB, LoadData
from pyoko.lib.utils import pprnt
from pprint import pprint
from zengine.lib.exceptions import HTTPError
from zengine.log import log
from zengine.wf_daemon import Worker


class ResponseWrapper(object):
    """
    Wrapper object for test client's response
    """

    def __init__(self, output):
        self.content = output

        try:
            self.json = output
            print(self.json)
        except:
            log.exception('ERROR at RWrapper JSON load')
            self.json = {}

        self.code = self.json.get('code', None)

        self.token = self.json.get('token')

        if self.code and int(self.code) >= 400:
            self.raw()
            raise HTTPError(self.code,
                            (self.json.get('title', '') +
                             self.json.get('description', '') +
                             self.json.get('error', '')))

    def raw(self):
        """
        Pretty prints the response
        """
        pprint(self.code)
        pprnt(self.json)
        if not self.json:
            pprint(self.content)


class TestClient(Worker):
    """
    TestClient to simplify writing API tests for Zengine based apps.
    """

    def __init__(self, path, *args, **kwargs):
        """
        this is a wsgi test client based on zengine.worker

        :param str path: Request uri
        """
        super(TestClient, self).__init__(*args, **kwargs)
        self.test_client_sessid = None
        self.response_wrapper = None
        self.set_path(path, None)
        self.user = None
        self.username = None
        self.path = ''
        self.sess_id = uuid4().hex
        import sys
        sys._called_from_test = True

    def set_path(self, path, token=''):
        """
        Change the path (workflow)

        Args:
            path: New path (or wf name)
            token: WF token.
        """
        self.path = path
        self.token = token

    def post(self, **data):
        """
        by default data dict encoded as json and
        content type set as application/json

        :param dict conf: additional configs for test client's post method.
                          pass "no_json" in conf dict to prevent json encoding
        :param data: post data,
        :return: RWrapper response object
        :rtype: ResponseWrapper
        """
        if 'token' not in data and self.token:
            data['token'] = self.token

        data['path'] = self.path.replace('/', '')

        data = {'data': data, '_zops_remote_ip': '127.0.0.1'}
        data = json.dumps(data)
        fake_method = type('FakeMethod', (object,), {'routing_key': self.sess_id})
        self.handle_message(None, fake_method, None, data)
        # update client token from response
        self.token = self.response_wrapper.token
        return self.response_wrapper

    def send_output(self, output, sessid):
        self.response_wrapper = ResponseWrapper(output)


# encrypted form of test password (123)
user_pass = '$pbkdf2-sha512$10000$nTMGwBjDWCslpA$iRDbnITHME58h1/eVolNmPsHVq' \
            'xkji/.BH0Q0GQFXEwtFvVwdwgxX4KcN/G9lUGTmv7xlklDeUp4DD4ClhxP/Q'

username = 'test_user'
import sys

sys.LOADED_FIXTURES = []


class BaseTestCase:
    """
    Base test case.
    """
    client = None

    def setup_method(self, method):
        """
        Creates a new user and Role with all Permissions.
        """

        if not '--ignore=fixture' in sys.argv:
            if hasattr(self, 'fixture'):
                print("REPORT:: Running test cases own fixture() method")
                self.fixture()
                sleep(2)

            else:
                fixture_guess = 'fixtures/%s.csv' % method.__self__.__module__.split('.test_')[1]
                if os.path.exists(fixture_guess) and fixture_guess not in sys.LOADED_FIXTURES:
                    sys.LOADED_FIXTURES.append(fixture_guess)
                    FlushDB(model='all', wait_sync=True,
                            exclude=settings.TEST_FLUSHING_EXCLUDES).run()
                    print("REPORT:: Test fixture will be loaded: %s" % fixture_guess)
                    LoadData(path=fixture_guess, update=True).run()
                    sleep(2)
                else:
                    print("REPORT:: Test case does not have a fixture file like %s" % fixture_guess)

        else:
            print("REPORT:: Fixture loading disabled by user. (by --ignore=fixture)")

    @classmethod
    def prepare_client(cls, path, reset=False, user=None, login=None, token='', username=None):
        """
        Setups the path, logs in if necessary

        Args:
            path: change or set path
            reset: Create a new client
            login: Login to system
            token: Set token
        """

        if not cls.client or reset or user:
            cls.client = TestClient(path)
            login = True if login is None else login

        if username:
            cls.client.username = username

        if user:
            cls.client.user = user
            login = True if login is None else login

        if login:
            cls._do_login()

        cls.client.set_path(path, token)

    @classmethod
    def _do_login(self):
        """
        logs in the "test_user"
        """
        self.client.sess_id = uuid4().hex
        self.client.set_path("/login/")
        resp = self.client.post()
        assert resp.json['forms']['schema']['title'] == 'LoginForm'
        req_fields = resp.json['forms']['schema']['required']
        assert all([(field in req_fields) for field in ('username', 'password')])
        resp = self.client.post(username=self.client.username or self.client.user.username,
                                password="123", cmd="do")
        assert resp.json['cmd'] == 'upgrade'
