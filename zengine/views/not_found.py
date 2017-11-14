# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.lib.utils import gettext as _, gettext_lazy as __
from zengine.views.crud import CrudView


class NotFound(CrudView):
    def show_not_found(self):
        msg = _(u"Workflow %s is not found. It can be non existent or not ready "
                           u"yet.") % self.current.task_data.get('non-existent-wf')
        self.current.msg_box(msg=msg, title=__(u"Not Found"))
