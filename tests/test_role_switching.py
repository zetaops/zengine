# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import time

from zengine.lib.test_utils import BaseTestCase
from zengine.models import User


class TestCase(BaseTestCase):
    def test_role_switching(self):

        for i in range(2):
            # Login with test_user.
            user = User.objects.get(username='test_user')
            # User's last_login_role_key field assigned to None.
            if i == 0:
                user.last_login_role_key = None
                user.save()
            # Role switching wf is started.
            self.prepare_client('/role_switching/', username='test_user')
            resp = self.client.post()
            # If user's last_login_role_key is exist, controlled login operation
            # with this role.
            if i == 1:
                last_login_role = user.last_login_role()
                assert last_login_role == self.client.current.role
            # Current role is taken.
            assert self.client.current.role.key == self.client.current.role_id
            # Current role is assigned to current_role field.
            current_role = self.client.current.role
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
