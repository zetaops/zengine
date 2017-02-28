# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


# testing if we are preserving task_data between wf jumps


from zengine.forms import JsonForm
from zengine.forms import fields
from zengine.views.crud import CrudView


class ChannelListForm(JsonForm):
    title = 'A'
    a = fields.String('ads')
    but = fields.Button('sad', cmd='das')


class A(CrudView):
    def user_task_b(self):
        f = ChannelListForm()
        self.form_out(f)
        self.current.output['task_name'] = 'user_task_b'

    def user_task_a(self):
        self.current.output['task_name'] = 'user_task_a'


def user_task_a(current):
    current.output['task_name'] = 'user_task_a'


def user_task_b(current):
    current.output['task_name'] = 'user_task_b'


def service_task_a(current):
    current.output['task_name'] = 'service_task_a'
