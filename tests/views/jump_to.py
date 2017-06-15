# -*-  coding: utf-8 -*-
"""
"""


# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


# testing if we are preserving task_data between wf jumps
def main_wf(current):
    current.task_data['from_main'] = True
    current.output['from_jumped'] = current.task_data.get('from_jumped')
    assert current.workflow.name == 'jump_to_wf'


def jumped_wf(current):
    current.output['from_main'] = current.task_data['from_main']
    current.task_data['from_jumped'] = True
    assert current.workflow.name == 'jump_to_wf2'


def set_external_wf(current):
    current.task_data['external_wf'] = 'jump_to_wf2'
