# -*-  coding: utf-8 -*-

# from tests.deep_eq import deep_eq
from zengine.lib.test_utils import BaseTestCase
from zengine.models import User
from zengine.lib.forms import JsonForm

serialized_empty_user = {'model': {'username': None, 'password': None},
                         'form': ['username', 'password'],
                         'schema': {'required': ['username', 'password'], 'type': 'object',
                                    'properties': {
                                        'username': {'name': 'username', 'title': 'Username',
                                                     'default': None, 'storage': 'main',
                                                     'section': 'main', 'required': True,
                                                     'type': 'string', 'value': ''},
                                        'password': {'name': 'password', 'title': 'Password',
                                                     'default': None, 'storage': 'main',
                                                     'section': 'main', 'required': True,
                                                     'type': 'password', 'value': ''}},
                                    'title': 'User'}}
serialized_user = {}

class TestCase(BaseTestCase):
    def test_serialize(self):
        self.prepare_client('login')
        serialized_form = JsonForm(User(), types={"password": "password"}, all=True).serialize()
        assert serialized_empty_user == serialized_form


        serialized_form = JsonForm(self.client.user,
                                   types={"password": "password"},
                                   all=True
                                   ).serialize()
        print("=====================================")
        print(list(serialized_form))
        print("=====================================")
        assert serialized_user == serialized_form

