# -*-  coding: utf-8 -*-
""""""
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
__author__ = "Evren Esat Ozkan"

from tests.testengine import TestEngine


def test_show_login():
    engine = TestEngine()
    engine.set_current(workflow_name='simple_login')
    engine.load_or_create_workflow()
    engine.run()
    assert {'form': 'login_form'} == engine.current.jsonout


def test_login_successful():
    engine = TestEngine()
    engine.set_current(workflow_name='simple_login')
    engine.load_or_create_workflow()
    engine.run()
    engine.set_current(jsonin={'login_data': {'username': 'user', 'password': 'pass'}})
    engine.run()
    assert {'screen': 'dashboard'} == engine.current.jsonout


def test_login_failed():
    engine = TestEngine()
    engine.set_current(workflow_name='simple_login')
    engine.load_or_create_workflow()
    engine.run()
    engine.set_current(jsonin={'login_data': {'username': 'user', 'password': 'WRONG_PASS'}})
    engine.run()
    assert {'form': 'login_form'} == engine.current.jsonout


def test_login_fail_retry_success():
    engine = TestEngine()
    engine.set_current(workflow_name='simple_login')
    engine.load_or_create_workflow()
    engine.run()
    engine.set_current(jsonin={'login_data': {'username': 'user', 'password': 'WRONG_PASS'}})
    engine.run()
    engine.set_current(jsonin={'login_data': {'username': 'user', 'password': 'pass'}})
    engine.run()
    assert {'screen': 'dashboard'} == engine.current.jsonout
