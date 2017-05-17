# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import time

from zengine.lib.exceptions import HTTPError
from zengine.lib.test_utils import BaseTestCase
from zengine.models import User

# role_key:(permission wf,non-permission wf)
role_permission_wfs = {'WOJt2XKpYEfhAPFl5jPJXIZSrGD': ('workflow_management', 'sequential_cruds'),
                       'NdOZ5WODiDYSdmjHCKt6Ax1sryA': ('edit_catalog_data', 'jump_to_wf')}


class TestCase(BaseTestCase):
    def test_role_switching(self):

        user = User.objects.get(username='test_user')
        # User's last_login_role_key field assigned to None.
        user.last_login_role_key = None
        user.blocking_save()

        for i in range(2):
            # Role switching wf is started.
            user = User.objects.get(username='test_user')
            self.prepare_client('role_switching', user=user)
            # Current role is taken.
            if i ==1:
                assert new_last_login_role == self.client.current.role
            assert self.client.current.role.key == self.client.current.role_id
            # Current role is assigned to current_role field.
            current_role = self.client.current.role
            # Switch user's role is tried about permission to wf's.
            permission_control = []
            for k in range(2):
                # In first loop user should have a permission to wf.
                # In second loop user shouldn't have a permission to wf.
                # These wf permissions are controlled.
                self.prepare_client(role_permission_wfs[current_role.key][k],
                                    user=user)
                try:
                    self.client.post()
                    permission_control.append((k,True))
                except HTTPError as error:
                    code, msg = error.args
                    assert code == 403
                    permission_control.append((k,False))

            assert sorted(permission_control) == [(0,True),(1,False)]

            # Role switching wf is started again.
            self.prepare_client('role_switching', username='test_user')
            # After re-starting wf, current role is controlled about no role change.
            assert current_role == self.client.current.role
            resp = self.client.post()
            assert 'wf_meta' in resp.json
            assert resp.json['wf_meta']['name'] == 'role_switching'
            assert resp.json['wf_meta']['current_step'] == 'ListUserRoles'
            # If user's last_login_role_key is exist, controlled login operation
            # with this role.
            if i == 1:
                last_login_role = user.last_login_role()
                assert last_login_role == self.client.current.role
            # Controlled in role select screen.
            assert 'Switch Role' == resp.json['forms']['schema']["title"]
            # All user's roles' keys are put to roles list.
            roles_list = [role_set.role.key for role_set in user.role_set]
            switch_key = resp.json['forms']['model']["role_options"]
            # Role to switch is controlled whether in roles_list or not.
            assert resp.json['forms']['model']["role_options"] in roles_list
            # Current role is controlled not equal to switch role.
            assert current_role.key != switch_key
            # User's total role number is more than one according to selectable roles at screen.
            # Because user's current role should be not selectable.
            assert len(roles_list) == len(resp.json['forms']['form'][1]["titleMap"]) + 1
            # Role to switch is chosen.
            switch_key = resp.json['forms']['model']["role_options"]
            # Role switch operation is done.
            resp = self.client.post(form={'switch': 1})
            # Dashboard reload is controlled.
            assert resp.json['cmd'] == 'reload'
            # Current role's changes is controlled.
            assert current_role.key != self.client.current.role.key
            # Role and role_id are controlled about equality.
            assert self.client.current.role.key == self.client.current.role_id
            # New current role is assigned to switch role, is controlled.
            assert self.client.current.role.key == switch_key
            # User is taken again from database.
            user = User.objects.get(username='test_user')
            # User's last_login_role_key field is controlled about not None.
            assert user.last_login_role_key != None
            # User's last_login_role_key field is controlled about assigning to switch role key.
            assert user.last_login_role_key == switch_key
            # User's last login role is taken.
            new_last_login_role = user.last_login_role()
            # Current role and last_login_role are controlled about same.
            assert new_last_login_role == self.client.current.role
            # Wf is restarting. (Logout and login)
            self.prepare_client('/role_switching/', user=user)
            # Current role should be last_login_role, is controlled.
            assert new_last_login_role == self.client.current.role

        user.last_login_role_key = None
        user.blocking_save()