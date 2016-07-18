# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from pyoko import Model, field, ListNode
from passlib.hash import pbkdf2_sha512


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


class User(Model):
    """
    Basic User model
    """
    username = field.String("Username", index=True)
    password = field.String("Password")
    superuser = field.Boolean("Super user", default=False)

    class Meta:
        """ meta class
        """
        list_fields = ['username', 'superuser']

    def __unicode__(self):
        return "User %s" % self.username

    def __repr__(self):
        return "User_%s" % self.key

    def set_password(self, raw_password):
        """
        Encrypts user password.

        Args:
            raw_password: Clean password string.

        """
        self.password = pbkdf2_sha512.encrypt(raw_password,
                                              rounds=10000,
                                              salt_size=10)

    def check_password(self, raw_password):
        """
        Checks given clean password against stored encrtyped password.

        Args:
            raw_password: Clean password.

        Returns:
            Boolean. True if given password match.
        """
        return pbkdf2_sha512.verify(raw_password, self.password)

    def get_permissions(self):
        """
        Permissions of the user.

        Returns:
            List of Permission objects.
        """
        users_primary_role = self.role_set[0].role
        return users_primary_role.get_permissions()

    def get_role(self, role_id):
        """
            Gets the first role of the user with given key.

        Args:
            role_id: Key of the Role object.

        Returns:
            :class:`Role` object
        """
        return self.role_set.node_dict[role_id]

    def send_message(self, title, message, sender=None):
        from zengine.notifications import Notify
        Notify(self.key).set_message(title, message, typ=Notify.Message, sender=sender)


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
