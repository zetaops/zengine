# -*-  coding: utf-8 -*-

# from tests.deep_eq import deep_eq
from zengine.models import User
from zengine.lib.forms import JsonForm

serialized_empty_user = {
    'model': {'username': None, 'password': None},
    'form': ['username', 'password'],
    'schema': {
        'required': ['username', 'password'],
        'type': 'object',
        'properties': {
            'username': {'type': 'string', 'title': 'Username'},
            'password': {'type': 'password', 'title': 'Password'},
        },
        'title': 'User'}}


def test_simple_serialize():
    serialized_form = JsonForm(User(), types={"password": "password"}).serialize()
    # assert serialized_empty_test_employee['model'] == serialized_form['model']
    assert serialized_empty_user == serialized_form
    # assert deep_eq(serialized_empty_user, serialized_form, _assert=True)
