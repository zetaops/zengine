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
    Base view class.
    """

    def __init__(self, current=None):
        self.client_cmd = set()
        if current:
            self.set_current(current)

    def set_current(self, current):
        """
        Creates some aliases for attributes of ``current``.

        Args:
            current: :attr:`~zengine.engine.WFCurrent` object.
        """
        self.current = current
        self.input = current.input
        # self.req = current.request
        # self.resp = current.response
        self.output = current.output
        self.cmd = current.task_data['cmd']

        if self.cmd and NEXT_CMD_SPLITTER in self.cmd:
            self.cmd, self.next_cmd = self.cmd.split(NEXT_CMD_SPLITTER)
        else:
            self.next_cmd = None

    def reload(self):
        """
        Generic view for reloading client
        """
        self.set_client_cmd('reload')

    def reset(self):
        """
        Generic view for resetting current WF.
        """
        self.set_client_cmd('reset')

    def set_client_cmd(self, *args):
        """
        Adds given cmd(s) to ``self.output['client_cmd']``

        Args:
            *args: Client commands.
        """
        self.client_cmd.update(args)
        self.output['client_cmd'] = list(self.client_cmd)



class SimpleView(BaseView):
    """
    Simple form based views can be build  up on this class.

    We call self.%s_view() method with %s substituted with
    ``self.input['cmd']`` if given or with
    :attr:`DEFAULT_VIEW` which has ``show`` as
    default value.
    """
    DEFAULT_VIEW = 'show'

    def __init__(self, current):
        super(SimpleView, self).__init__(current)
        view = "%s_view" % (self.cmd or self.DEFAULT_VIEW)
        if view in self.__class__.__dict__:
            self.__class__.__dict__[view](self)
