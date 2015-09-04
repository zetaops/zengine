# -*-  coding: utf-8 -*-

# from tests.deep_eq import deep_eq
from pprint import pprint
from zengine.lib.test_utils import BaseTestCase
from zengine.models import User
from zengine.lib.forms import JsonForm

serialized_empty_user = {
    'form': ['username', 'password', 'Permissions'],
    'model': {'Permissions': '!', 'password': None, 'username': None},
    'schema': {'properties': {'Permissions': {'default': None,
                                              'fields': [],
                                              'models': [],
                                              'name': 'Permissions',
                                              'required': None,
                                              'title': 'Permissions',
                                              'type': 'ListNode',
                                              'value': '!'},
                              'password': {'default': None,
                                           'name': 'password',
                                           'required': True,
                                           'title': 'Password',
                                           'type': 'password',
                                           'value': ''},
                              'username': {'default': None,
                                           'name': 'username',
                                           'required': True,
                                           'title': 'Username',
                                           'type': 'string',
                                           'value': ''}},
               'required': ['username', 'password'],
               'title': 'User',
               'type': 'object'}}
serialized_user = {'form': ['username', 'password', 'Permissions'],
                   'model': {'Permissions': '!',
                             'password': u'$pbkdf2-sha512$10000$nTMGwBjDWCslpA$iRDbnITHME58h1/eVol'
                                         u'NmPsHVqxkji/.BH0Q0GQFXEwtFvVwdwgxX4KcN/G9lUGTmv7xlklDeU'
                                         u'p4DD4ClhxP/Q',
                             'username': u'test_user'},
                   'schema': {'properties': {
                       'Permissions':
                           {'default': None,
                            'fields': [{'default': None,
                                        'name': 'permissions.idx',
                                        'required': True,
                                        'title': '',
                                        'type': 'string',
                                        'value': u'898dc81cb37a46c3985d6de9a88dbd90'}],
                            'models': [
                                {'content': [{'default': None,
                                              'name': 'code',
                                              'required': True,
                                              'title': 'Code Name',
                                              'type': 'string',
                                              'value': u'crud'},
                                             {'default': None,
                                              'name': 'name',
                                              'required': True,
                                              'title': 'Name',
                                              'type': 'string',
                                              'value': u'crud'}],
                                 'default': None,
                                 'model_name': 'Permission',
                                 'name': 'permission_id',
                                 'required': None,
                                 'title': 'Permission',
                                 'type': 'model',
                                 'value': u'PTYFPcUHQAcE6a0hFxU9OI8n3LI'}],
                            'name': 'Permissions',
                            'required': None,
                            'title': 'Permissions',
                            'type': 'ListNode',
                            'value': '!'},
                       'password': {'default': None,
                                    'name': 'password',
                                    'required': True,
                                    'title': 'Password',
                                    'type': 'password',
                                    'value': u'$pbkdf2-sha512$10000$nTMGwBjDWCslpA$iRDbnITHME58h'
                                             u'1/eVolNmPsHVqxkji/.BH0Q0GQFXEwtFvVwdwgxX4KcN/G9lU'
                                             u'GTmv7xlklDeUp4DD4ClhxP/Q'},
                       'username': {'default': None,
                                    'name': 'username',
                                    'required': True,
                                    'title': 'Username',
                                    'type': 'string',
                                    'value': u'test_user'}},
                       'required': ['username', 'password'],
                       'title': 'User',
                       'type': 'object'}}


class TestCase(BaseTestCase):
    def test_serialize(self):
        self.prepare_client('login')
        serialized_form = JsonForm(User(), types={"password": "password"}, all=True).serialize()

        # print("=====================================")
        # pprint(serialized_form)
        # print("=====================================")
        assert serialized_empty_user == serialized_form

        serialized_form = JsonForm(self.client.user,
                                   types={"password": "password"},
                                   all=True
                                   ).serialize()
        # print("\n\n=====================================\n\n")
        # pprint(serialized_form)
        # print("\n\n=====================================\n\n")
        assert len(serialized_user['form']) == 3
        perms = serialized_user['schema']['properties']['Permissions']
        assert perms['fields'][0]['name'] == 'permissions.idx'
        assert perms['models'][0]['content'][0]['value'] == 'crud'
        username = serialized_user['schema']['properties']['username']
        assert username['value'] == 'test_user'
