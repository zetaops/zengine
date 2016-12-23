# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.lib.test_utils import BaseTestCase


class TestCase(BaseTestCase):


    def test_wf_initial_values(self):

        # sequential_cruds diagram has a property as init = True
        self.prepare_client('sequential_cruds', username='super_user')
        # WF is started.
        self.client.post()
        # 'wf_initial_values' should be in current task_data.
        # Because it has a property as init=True
        assert 'wf_initial_values' in self.client.current.task_data

        # workflow_management diagram doesn't have a property.
        self.prepare_client('workflow_management', username='super_user')
        # WF is started.
        self.client.post()
        # 'wf_initial_values' shouldn't be in current task_data.
        assert 'wf_initial_values' not in self.client.current.task_data
