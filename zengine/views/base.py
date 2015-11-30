# -*-  coding: utf-8 -*-
"""Base view classes"""

# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

NEXT_CMD_SPLITTER = '::'


class BaseView(object):
    """
    All view classes should extend this class
    """

    def __init__(self, current=None):
        self.client_cmd = set()
        if current:
            self.set_current(current)

    def set_current(self, current):
        self.current = current
        self.input = current.input
        self.req = current.request
        self.resp = current.response
        self.output = current.output
        self.cmd = current.task_data['cmd']

        if self.cmd and NEXT_CMD_SPLITTER in self.cmd:
            self.cmd, self.next_cmd = self.cmd.split(NEXT_CMD_SPLITTER)
        else:
            self.next_cmd = None

    def reload(self):
        self.set_client_cmd('reload')

    def reset(self):
        self.set_client_cmd('reset')

    def set_client_cmd(self, cmd):
        self.client_cmd.add(cmd)
        self.output['client_cmd'] = list(self.client_cmd)

    def form_out(self, _form=None):
        _form = _form or self.object_form
        self.output['forms'] = _form.serialize()
        self.modify_form_properties(self.output['forms'])
        self.set_client_cmd('form')

    def modify_form_properties(self, serialized_form):
        pass


class SimpleView(BaseView):
    """
    simple form based views can be build  up on this class.
    we call self.%s_view() method with %s substituted with self.input['cmd']
    self.show_view() will be called if client doesn't give any cmd
    """
    DEFAULT_VIEW = ''

    def __init__(self, current):
        super(SimpleView, self).__init__(current)
        view = "%s_view" % (self.cmd or self.DEFAULT_VIEW or 'show')
        if view in self.__class__.__dict__:
            self.__class__.__dict__[view](self)
