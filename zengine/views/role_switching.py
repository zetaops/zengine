# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.views.crud import CrudView
from zengine.forms import JsonForm
from zengine.forms import fields
from pyoko import ListNode
from ulakbus.models import User, Role
from zengine.lib.translation import gettext as _, gettext_lazy as __
from ulakbus.models.auth import AuthBackend


class RoleForm(JsonForm):
    """
    """

    class Meta:
        inline_edit = ['choice']

    class RoleList(ListNode):
        choice = fields.Boolean(_(u"Choice"), type="checkbox")
        role = fields.String(_(u'User Role'), index=True)
        key = fields.String(hidden=True)


class RoleSwitching(CrudView):
    """


    """

    class Meta:
        model = "User"

    def list_user_roles(self):
        """


        """
        user = self.current.user
        _form = RoleForm(current=self.current, title=_(u"Choose Role"))
        _form.help_text = "Current Role: %s" % self.current.role.abstract_role.name
        for role_set in user.role_set:
            if role_set.role != self.current.role:
                _form.RoleList(choice=False, role=role_set.role.abstract_role.name, key=role_set.role.key)

        _form.sec = fields.Button(_(u"Choose"))
        self.form_out(_form)

    def change_user_role(self):
        """

        """
        user = self.current.user
        role = get_chosen_role(self)
        auth = AuthBackend(self.current)
        auth.set_user(user, role)


def get_chosen_role(self):
    chosen_role_key = ''
    for line in self.input['form']['RoleList']:
        if line['choice']:
            chosen_role_key = line['key']

    return Role.objects.get(chosen_role_key)
