# -*-  coding: utf-8 -*-
"""Base view classes"""
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

class BaseView(object):
    """
    this class constitute a base for all view classes.
    """

    def __init__(self, current=None):
        if current:
            self.set_current(current)

    def set_current(self, current):
        self.current = current
        self.input = current.input
        self.output = current.output
        if hasattr(current, 'task_data'):
            self.cmd = current.task_data['cmd']
        else:
            self.cmd = current.input.get('cmd')
        self.subcmd = current.input.get('subcmd')
        self.do = self.subcmd in ['do_show', 'do_list', 'do_edit', 'do_add']
        self.next_task = self.subcmd.split('_')[1] if self.do else None

    def go_next_task(self):
        if self.next_task:
            self.current.set_task_data(self.next_task)


class SimpleView(BaseView):
    """
    simple form based views can be build  up on this class.
    we call self.%s_view() method with %s substituted with self.input['cmd']
    self.show_view() will be called if client doesn't give any cmd
    """

    def __init__(self, current):
        super(SimpleView, self).__init__(current)
        self.__class__.__dict__["%s_view" % (self.cmd or 'show')](self)

