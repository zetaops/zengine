# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import datetime

from zengine.current import Current
from zengine.forms import ModelForm, JsonForm
from zengine.forms import fields

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


class FillableForm(JsonForm):
    class Meta:
        title = "Fillable Form"
        always_blank = False
    duration = fields.Integer()
    name = fields.String()
    budget = fields.Float()
    date = fields.Date()
    ddate = fields.DateTime()
    submit = fields.Button()


class TestCase:
    def test_plain_form(self):
        serialized_model = sorted(LoginForm()._serialize(), key=lambda d: d['name'])
        assert serialized_model[0]['name'] == 'password'

    def test_prefilled_form(self):
        lf = LoginForm()
        lf.foo = fields.String(value='bar')
        lf.username = 'test_user'
        srlzed = lf.serialize()
        assert 'password' in srlzed['form']
        assert srlzed['model']['username'] == 'test_user'
        assert srlzed['model']['foo'] == 'bar'

    def test_plain_form_deserialize(self):
        login_data = {'username': 'Samuel', 'password': 'seeice'}
        model = LoginForm().deserialize(login_data, do_validation=False)
        assert model.password == login_data["password"]
        assert model.username == login_data["username"]

    def test_fillable_form(self):
        current = Current()
        current.task_data = {
            'FillableForm': {
                'duration': 123,
                'name': 'some dummy name',
                'budget': 12345,
                'date': '13.04.2017',
                'ddate': '13.04.2017T00:00:00.00Z',
                'submit': 1
            }
        }
        form = FillableForm(current=current)
        serialized_form = form.serialize()
        assert serialized_form['model']['duration'] == 123
        assert serialized_form['model']['name'] == 'some dummy name'
        assert serialized_form['model']['budget'] == 12345
        assert serialized_form['model']['date'] == '2017-04-13T00:00:00.000000Z'
        assert serialized_form['model']['ddate'] == '2017-04-13T00:00:00.000000Z'
        assert serialized_form['model']['submit'] == 1

