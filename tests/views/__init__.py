# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from falcon import HTTPError

from pyoko import form
# from zengine.models import User
from zengine.lib.forms import JsonForm
from zengine.views.crud import CrudView, obj_filter, view_method


class UserCrud(CrudView):
    class Meta:
        model = 'User'
        init_view = 'list_form'
        attributes = {
            'Permission': {
                'permission_id': [{'name': 'exclude', 'value': {'code': 'delete'}}]
            },
            'Main': {
                'permission_id': [{'name': 'exclude', 'value': {'code': 'delete'}}]
            }
        }

    class CrudForm(JsonForm):
        save_list = form.Button("Btn1", cmd="list_form::list_form")

    @obj_filter
    def silinemez_kullanicilar(self, obj, result):
        if obj.username in ['admin']:
            result['can_delete'] = False
        return result

    @view_method
    def delete(self):
        if self.object.username in ['admin']:
            raise HTTPError()
        super(UserCrud, 'delete').delete()
