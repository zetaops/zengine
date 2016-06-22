# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from pyoko import Model, field, ListNode
from passlib.hash import pbkdf2_sha512
from zengine.messaging.lib import BaseUser


class Permission(Model):
    """
    Permission model
    """
    name = field.String("Name", index=True)
    code = field.String("Code Name", index=True)
    description = field.String("Description", index=True)

    def __unicode__(self):
        return "Permission %s" % self.name

    def get_permitted_users(self):
        """
        Get users which has this permission

        Returns:
            User list
        """
        return [r.role.user for r in self.role_set]

    def get_permitted_roles(self):
        """
        Get roles which has this permission

        Returns:
            Role list
        """
        return [rset.role for rset in self.role_set]


class User(Model, BaseUser):
    """
    Basic User model
    """
    username = field.String("Username", index=True)
    password = field.String("Password")
    superuser = field.Boolean("Super user", default=False)
    avatar = field.File("Avatar", random_name=True, required=False)

    class Meta:
        """ meta class
        """
        list_fields = ['username', 'superuser']


    def get_permissions(self):
        """
        Permissions of the user.

        Returns:
            List of Permission objects.
        """
        users_primary_role = self.role_set[0].role
        return users_primary_role.get_permissions()


class Role(Model):
    """
    This model binds group of Permissions with a certain User.
    """
    user = User()

    class Meta:
        """
        Meta class
        """
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __unicode__(self):
        try:
            return "%s %s" % (self.abstract_role.name, self.user.username)
        except:
            return "Role #%s" % self.key

    class Permissions(ListNode):
        """
        Stores :class:`Permission`'s of the role
        """
        permission = Permission()

    def get_permissions(self):
        """
        Returns:
            :class:`Permission`'s of the role
        """
        return [p.permission.code for p in self.Permissions]

    def add_permission(self, perm):
        """
        Adds a :class:`Permission` to the role

        Args:
            perm: :class:`Permission` object.
        """
        self.Permissions(permission=perm)
        self.save()

    def add_permission_by_name(self, code, save=False):
        """
        Adds a permission with given name.

        Args:
            code (str): Code name of the permission.
            save (bool): If False, does nothing.
        """
        if not save:
            return ["%s | %s" % (p.name, p.code) for p in
                    Permission.objects.filter(code__contains=code)]
        for p in Permission.objects.filter(code__contains=code):
            if p not in self.Permissions:
                self.Permissions(permission=p)
        if p:
            self.save()
