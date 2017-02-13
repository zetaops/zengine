# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.views.crud import CrudView
from zengine.forms import JsonForm
from zengine.forms import fields
from zengine.lib.utils import gettext as _
from zengine import settings
from pyoko.lib.utils import get_object_from_path

AuthBackend = get_object_from_path(settings.AUTH_BACKEND)


class RoleSwitching(CrudView):
    """
    Switches current user's role.
    """

    def list_user_roles(self):
        """
        Lists user roles as selectable except user's current role.
        """
        _form = JsonForm(current=self.current, title=_(u"Switch Role"))
        _form.help_text = "Your current role: %s %s" % (self.current.role.unit.name,
                                                        self.current.role.abstract_role.name)
        switch_roles = self.get_user_switchable_roles()
        _form.role_options = fields.Integer(_(u"Please, choose the role you want to switch:")
                                            , choices=switch_roles, default=switch_roles[0][0],
                                            required=True)
        _form.switch = fields.Button(_(u"Switch"))
        self.form_out(_form)

    def change_user_role(self):
        """
        Changes user's role from current role to chosen role.
        """

        # Get chosen role_key from user form.
        role_key = self.input['form']['role_options']
        # Assign chosen switch role key to user's last_login_role_key field
        self.current.user.last_login_role_key = role_key
        self.current.user.save()
        auth = AuthBackend(self.current)
        # According to user's new role, user's session set again.
        auth.set_user(self.current.user)
        # Dashboard is reloaded according to user's new role.
        self.current.output['cmd'] = 'reload'

    def get_user_switchable_roles(self):
        """
        Returns user's role list except current role as a tuple
        (role.key, role.name)

        Returns:
            (list): list of tuples, user's role list except current role

        """
        roles = []
        for rs in self.current.user.role_set:
            # rs.role != self.current.role is not True after python version 2.7.12
            if rs.role.key != self.current.role.key:
                roles.append((rs.role.key, '%s %s' % (rs.role.unit.name,
                                                      rs.role.abstract_role.name)))
        return roles
