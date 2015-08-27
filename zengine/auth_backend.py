# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
try:
    from zengine.lib.exceptions import PermissionDenied
except ImportError:
    class PermissionDenied(Exception):
        pass
from zengine.models import *


class AuthBackend(object):
    def __init__(self, session):
        self.session = session

    def get_user(self):
        return (User.objects.get(self.session['user_id'])
                if 'user_id' in self.session
                else User())

    def set_user(self, user):
        """
        insert current user's data to session
        :param User user: logged in user
        """
        self.session['user_id'] = user.key
        self.session['role_id'] = user.role_set[0].role.key

    def get_permissions(self):
        return self.get_user().get_permissions()

    def has_permission(self, perm):
        return perm in self.get_user().get_permissions()


    def authenticate(self, username, password):
        user = User.objects.filter(username=username).get()
        is_login_ok = user.check_password(password)
        if is_login_ok:
            self.set_user(user)
        return is_login_ok
