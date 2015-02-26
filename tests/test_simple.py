# -*-  coding: utf-8 -*-
""""""
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
__author__ = "Evren Esat Ozkan"

from tests.testengine import TestEngine


__author__ = 'Evren Esat Ozkan'


def test_task_1():
    engine = TestEngine()
    engine.set_current(workflow_name='simple_login')
    engine.load_or_create_workflow()
    engine.run()
    # assert 0
    assert 'login_form' == engine.current.jsonout['form']


def test_task_2():
    engine = TestEngine()
    engine.set_current(workflow_name='simple_login')
    engine.load_or_create_workflow()
    engine.run()
    engine.reset()
    engine.set_current(jsonin={'login_data': {'username': 'user', 'password': 'pass'}})
    engine.run()
    assert True == engine.current.jsonout['success']

