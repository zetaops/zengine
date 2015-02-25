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


def test_simple():
    engine = TestEngine()
    engine.set_current(workflow_name='simple_login')
    engine.load_or_create_workflow()
    engine.run()
    assert 'login_form' == engine.current.jsonout['form']
