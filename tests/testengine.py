# -*-  coding: utf-8 -*-
"""
test wf engine
 """
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
__author__ = "Evren Esat Ozkan"

import re
import os.path
from zengine.engine import ZEngine

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

# path of the activity modules which will be invoked by workflow tasks
ACTIVITY_MODULES_IMPORT_PATH = 'tests.activities'
# absolute path to the workflow packages
WORKFLOW_PACKAGES_PATH = os.path.join(BASE_DIR, 'workflows')


class TestEngine(ZEngine):
    WORKFLOW_DIRECTORY = WORKFLOW_PACKAGES_PATH
    ACTIVITY_MODULES_PATH = ACTIVITY_MODULES_IMPORT_PATH

    def __init__(self):
        super(TestEngine, self).__init__()
        self.set_current(session={}, jsonin={}, jsonout={})

    def get_linear_dump(self):
        tree_dmp = self.workflow.task_tree.get_dump()
        return ','.join(re.findall('Task of ([\w|_]*?) \(', tree_dmp))

    def save_workflow(self, wf_name, serialized_wf_instance):
        if 'workflows' not in self.current.session:
            self.current.session['workflows'] = {}
        self.current.session['workflows'][wf_name] = serialized_wf_instance

    def load_workflow(self, workflow_name):
        try:
            return self.current.session['workflows'].get(workflow_name, None)
        except KeyError:
            return None

    def reset(self):
        """
        we need to cleanup the data dicts to simulate real request cylces
        :return:
        """
        self.set_current(jsonin={}, jsonout={})

#
# if __name__ == '__main__':
#     engine = TestEngine()
#     engine.set_current(workflow_name='simple_login')
#     engine.load_or_create_workflow()
#     engine.run()
