# -*-  coding: utf-8 -*-

from zengine.forms.json_form import JsonForm
from zengine.lib.test_utils import BaseTestCase
from zengine.models import User


class TestCase(BaseTestCase):
    def test_serialize(self):

        serialized_form = JsonForm(User(username='test_user'),
                                   types={"password": "password"},
                                   all=True
                                   ).serialize()

        assert serialized_form['model']['username'] == 'test_user'
