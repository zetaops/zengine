# -*-  coding: utf-8 -*-

# from tests.deep_eq import deep_eq
from zengine.forms.json_form import JsonForm
from zengine.lib.test_utils import BaseTestCase
from zengine.models import User


class TestCase(BaseTestCase):
    def test_serialize(self):
        self.prepare_client('/login/')
        serialized_form = JsonForm(User(), types={"password": "password"}, all=True).serialize()
        # print("=====================================")
        # pprint(serialized_form)
        # print("=====================================")
        # assert len(serialized_form['form']) == 4
        # perms = serialized_form['schema']['properties']['Permissions']
        # assert perms['fields'][0]['name'] == 'idx'

        serialized_form = JsonForm(self.client.user,
                                   types={"password": "password"},
                                   all=True
                                   ).serialize()
        # print("\n\n=====================================\n\n")
        # pprint(serialized_form)
        # print("\n\n=====================================\n\n")

        # perms = serialized_form['schema']['properties']['Permissions']
        # assert perms['models'][0]['content'][0]['value'] == 'crud'

        assert serialized_form['model']['username'] == 'test_user'
