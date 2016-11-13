# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.views.crud import CrudView
from zengine.forms import JsonForm
from zengine.forms import fields
from pyoko import ListNode
from ulakbus.models import Role
from zengine.lib.translation import gettext as _
from ulakbus.models.auth import AuthBackend


class RoleForm(JsonForm):
    class Meta:
        inline_edit = ['choice']

    class RoleList(ListNode):
        choice = fields.Boolean(_(u"Choice"), type="checkbox")
        role = fields.String(_(u'User Role'), index=True)
        key = fields.String(hidden=True)


class RoleSwitching(CrudView):
    """
    Switches current user's role.
    """

    def list_user_roles(self):
        """
        Lists user roles as selectable except user's current role.
        """

        _form = RoleForm(current=self.current, title=_(u"Switch Role"))
        _form.help_text = "Your current role: %s" % self.current.role.abstract_role.name

        for role in get_user_roles(self.current.user, self.current.role):
            _form.RoleList(choice=False, role=role.abstract_role.name, key=role.key)
        _form.switch = fields.Button(_(u"Switch"))
        self.form_out(_form)

    def change_user_role(self):
        """
        Changes user's role from current role to chosen role.
        """

        # Get chosen role_key from user form.
        role_key = get_chosen_role_key(self.input['form'])
        # Get chosen role.
        role = Role.objects.get(role_key)
        # Assign chosen switch role key to user's last_login_role_key field
        self.current.user.last_login_role_key = role_key
        self.current.user.save()
        auth = AuthBackend(self.current)
        # According to user's new role, user's session set again.
        auth.set_user(self.current.user, role)
        # Dashboard is reloaded according to user's new role.
        self.current.output['cmd'] = 'reload'


def get_chosen_role_key(form):
    """

    :param form: the form which is coming from user.
    :return: chosen role's key.
    """
    return [role['key'] for role in form['RoleList'] if role['choice']][0]


def get_user_roles(user, current_role):
    """

    :param user: User object
    :return: user's role list except current role, for switchable role options
             at role choosing screen.
    """
    return [role_set.role for role_set in user.role_set if role_set.role != current_role]
