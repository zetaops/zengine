# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.lib.test_client import TestClient

from zengine.models import User
from time import sleep


from zengine.log import getlogger

RESPONSES = {"get_login_form": {
    'forms': {'model': {'username': None,
                        'password': None},
              'form': ['username', 'password'],
              'schema': {'required': ['username',
                                      'password'],
                         'type': 'object',
                         'properties': {
                             'username': {
                                 'type': 'string',
                                 'title': 'Username'},
                             'password': {
                                 'type': 'password',
                                 'title': 'Password'}},
                         'title': 'LoginForm'}},
    'is_login': False},
    "successful_login": {u'screen': u'dashboard',
                         u'is_login': True}}

# encrypted form of test password (123)
user_pass = '$pbkdf2-sha512$10000$nTMGwBjDWCslpA$iRDbnITHME58h1/eVolNmPsHVq' \
            'xkji/.BH0Q0GQFXEwtFvVwdwgxX4KcN/G9lUGTmv7xlklDeUp4DD4ClhxP/Q'


class BaseTestCase:
    client = None
    log = getlogger()
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
        else:
            self.client.set_workflow(workflow_name)

        if login and self.client.user is None:
            self.client.set_workflow("login")
            self.client.user, new = User.objects.get_or_create({"password": user_pass},
                                                               username='test_user')
            self._do_login()
            self.client.set_workflow(workflow_name)

    @classmethod
    def _do_login(self):
        """
        logs in the test user with test client

        """
        resp = self.client.post()
        output = resp.json
        del output['token']
        assert output == RESPONSES["get_login_form"]
        data = {"username": "test_user", "password": "123", "cmd": "do"}
        resp = self.client.post(**data)
        output = resp.json
        del output['token']
        assert output == RESPONSES["successful_login"]
