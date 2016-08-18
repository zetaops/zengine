# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


from zengine.views.crud import CrudView


class CrudOne(CrudView):
    class Meta:
        model = 'User'

    def __init__(self, current):
        current.task_data['object_id'] = 'HjgPuHelltHC9USbj8wqd286vbS'
        super(CrudOne, self).__init__(current)
        self.form_out()

class CrudTwo(CrudView):
    class Meta:
        model = 'User'

    def __init__(self, current):
        super(CrudTwo, self).__init__(current)
        self.current.msg_box("test_ok", "object_id:%s" % self.current.task_data['object_id'])

