# -*-  coding: utf-8 -*-
from uuid import uuid4
from time import sleep
import json
import os

from pyoko.conf import settings
from pyoko.manage import FlushDB, LoadData
from pyoko.lib.utils import pprnt
from pprint import pprint

from zengine.lib.cache import ClearCache
from zengine.lib.exceptions import HTTPError
from zengine.log import log
from zengine.wf_daemon import Worker
from zengine.lib.json_interface import ZEngineJSONEncoder

from zengine.models import User
from zengine.messaging.model import Message


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
        self.form_data = self.json['forms']['model'] if 'forms' in self.json else {}

        if 'object_key' in self.form_data:
            self.object_key = self.form_data['object_key']
        else:
            self.object_key = self.json.get('object_id', None)

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
        try:
            pprnt(self.json)
        except TypeError:  # If there is a custom type in the output (i.e. lazy translations)
            print(json.dumps(self.json, cls=ZEngineJSONEncoder, indent=4, sort_keys=True))
        if not self.json:
            pprint(self.content)


class BaseTestClient(Worker):
    """
    TestClient to simplify writing API tests for Zengine based apps.
    """

    def __init__(self, path, *args, **kwargs):
        """
        this is a wsgi test client based on zengine.worker

        :param str path: Request uri
        """
        super(BaseTestClient, self).__init__(*args, **kwargs)
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

    def _prepare_post(self, wf_meta, data):
        """
        by default data dict encoded as json and content type set as application/json
        when form data is post, UI should send wf_meta info to backend, but some tests works on
        lack of wf_meta scenario so wf_meta info is done optional as True, False.

        :param dict conf: additional configs for test client's post method.
                          pass "no_json" in conf dict to prevent json encoding
        :param data: post data,
        wf_meta(bool): fake wf_meta will be created or not
        :return: RWrapper response object
        :rtype: ResponseWrapper
        """
        if 'token' not in data and self.token:
            data['token'] = self.token
        if self.response_wrapper:
            form_data = self.response_wrapper.form_data.copy()
        else:
            form_data = {}
        if self.path:
            data['path'] = self.path.replace('/', '')

        if 'form' in data:
            form_data.update(data['form'])

        data['form'] = form_data

        if wf_meta and hasattr(self, 'current') and hasattr(self.current, 'spec'):
            if self.current.task.parent.task_spec.__class__.__name__ == 'UserTask':
                data['wf_meta'] = {'name': self.current.workflow_name,
                                   'current_lane': self.current.task.parent.task_spec.lane,
                                   'current_step': self.current.task.parent.task_spec.name}

        post_data = {'data': data,
                     '_zops_remote_ip': '127.0.0.1',
                     '_zops_source': 'Remote',
                     }
        log.info("PostData : %s" % post_data)
        print("PostData : %s" % post_data)
        return post_data

    def post(self, wf_meta=True, **data):
        post_data = json.dumps(self._prepare_post(wf_meta, data))
        fake_method = type('FakeMethod', (object,), {'routing_key': self.sess_id})
        self.handle_message(None, fake_method, None, post_data)
        # update client token from response
        self.token = self.response_wrapper.token
        return self.response_wrapper



class TestClient(BaseTestClient):
    def send_output(self, output):
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

        # if not '--ignore=fixture' in sys.argv:
        #     if hasattr(self, 'fixture'):
        #         print("\nREPORT:: Running test cases own fixture() method")
        #         self.fixture()
        #         sleep(2)
        #
        #     else:
        #         fixture_guess = 'fixtures/%s.csv' % method.__self__.__module__.split('.test_')[1]
        #         if os.path.exists(fixture_guess) and fixture_guess not in sys.LOADED_FIXTURES:
        #             sys.LOADED_FIXTURES.append(fixture_guess)
        #             FlushDB(model='all', wait_sync=True,
        #                     exclude=settings.TEST_FLUSHING_EXCLUDES).run()
        #             print("\nREPORT:: Test fixture will be loaded: %s" % fixture_guess)
        #             LoadData(path=fixture_guess, update=True).run()
        #             sleep(2)
        #         else:
        #             print(
        #                 "\nREPORT:: Test case does not have a fixture file like %s" % fixture_guess)
        #
        # else:
        #     print("\nREPORT:: Fixture loading disabled by user. (by --ignore=fixture)")
        # clear all caches
        if not hasattr(sys, 'cache_cleared'):
            sys.cache_cleared = True
            print(ClearCache.flush())
            print("\nREPORT:: Cache cleared")

    @classmethod
    def prepare_client(cls, path='', reset=False, user=None, login=None, token='', username=None):
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
        log.debug("login result :\n%s" % resp.json)
        assert resp.json['cmd'] == 'upgrade'

    def get_user_token(self, username):
        user = User.objects.get(username=username)
        token = self.client.current.token
        return token, user
