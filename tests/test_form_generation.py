# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import datetime
from time import sleep
from zengine.forms import ModelForm, JsonForm
from zengine.forms import fields
# from pyoko.tests.data.test_data import clean_data
# from pyoko.tests.models import *

received_data = {
    'AuthInfo': {
        'email': 'duuper@suup.com',
        'password': '1111',
        'username': 'poser'},
    'bio': "You think water moves fast? You should see ice. It moves like it has a mind. "
           "Like it knows it killed the world once and got a taste for murder. "
           "After the avalanche, it took us a week to climb out.",
    'join_date': datetime.date(2015, 5, 16),
    'name': 'Samuel',
    'deleted': False,
    'number': '20300344',
    'timestamp': None,
    'pno': '2343243433',
    'surname': 'Jackson'}


class LoginForm(JsonForm):
    username = fields.String("Username")
    password = fields.String("Password", type="password")


serialized_login_form = [
    {'type': 'password', 'title': 'Password', 'required': True, 'choices': None, 'cmd': None,
     'value': '', 'default': None, 'name': 'password'},
    {'type': 'string', 'title': 'Username', 'required': True, 'choices': None, 'cmd': None,
     'value': '', 'default': None, 'name': 'username'}]


# noinspection PyMethodMayBeStatic
class TestCase:
    cleaned_up = False


    def test_plain_form(self):
        serialized_model = sorted(LoginForm()._serialize(), key=lambda d: d['name'])
        assert serialized_model[0]['name'] == 'password'

    def test_prefilled_form(self):
        lf = LoginForm()
        lf.foo = fields.String()
        lf.process_form()
        lf.username = 'test_user'
        lf.foo = 'bar'
        serialized_data = lf._serialize()
        serialized_model = sorted(serialized_data, key=lambda d: d['name'])
        assert serialized_model[1]['name'] == 'password'
        assert serialized_model[2]['value'] == 'test_user'
        assert serialized_model[0]['value'] == 'bar'

    def test_plain_form_deserialize(self):
        login_data = {'username': 'Samuel', 'password': 'seeice'}
        model = LoginForm().deserialize(login_data)
        assert model.password == login_data["password"]
        assert model.username == login_data["username"]

    # def test_modelform_deserialize_simple(self):
    #     self.clean(force=True)
    #     student = ModelForm(Student()).deserialize(received_data)
    #     student.save()
    #     sleep(2)
    #     db_student = Student.objects.filter(
    #         auth_info__email=received_data['AuthInfo']['email']).get()
    #     assert db_student.AuthInfo.email == received_data['AuthInfo']['email']
    #     assert db_student.bio == received_data['bio']
    #
    # def test_list_node_with_linked_model(self):
    #     self.clean()
    #     abs_role = AbstractRole(name="Employee Manager").save()
    #     arole = AbstractRole.objects.get(abs_role.key)
    #     serialized_model = sorted(ModelForm(arole, all=True)._serialize(), key=lambda d: d['name'])
    #     # print("=====================================")
    #     # pprint(serialized_model)
    #     # print("=====================================")
    #     assert serialized_model[0]['schema'][0]['model_name'] == 'Permission'
    #     assert serialized_model[1]['title'] == 'Name'
