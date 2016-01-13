# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from pyoko import field
from pyoko import Model, ListNode
from passlib.hash import pbkdf2_sha512


class Permission(Model):
    name = field.String("Name", index=True)
    code = field.String("Code Name", index=True)
    description = field.String("Description", index=True)

    def __unicode__(self):
        return "Permission %s" % self.name


class User(Model):
    username = field.String("Username", index=True)
    password = field.String("Password")
    superuser = field.Boolean("Super user", default=False)

    class Meta:
        list_fields = ['username', 'superuser']

    def __unicode__(self):
        return "User %s" % self.username

    def __repr__(self):
        return "User_%s" % self.key

    def set_password(self, raw_password):
        self.password = pbkdf2_sha512.encrypt(raw_password,
                                              rounds=10000,
                                              salt_size=10)

    def check_password(self, raw_password):
        return pbkdf2_sha512.verify(raw_password, self.password)

    def get_permissions(self):
        return (p.permission.code for p in self.Permissions)

    def get_role(self, role_id):
        return self.role_set.node_dict[role_id]


class Role(Model):
    """
    This model binds group of Permissions with a certain User.
    """
    user = User()

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __unicode__(self):
        try:
            return "%s %s" % (self.abstract_role.name, self.user.username)
        except:
            return "Role #%s" % self.key

    class Permissions(ListNode):
        permission = Permission()

    def get_permissions(self):
        return [p.permission.code for p in self.Permissions]

    def add_permission(self, perm):
        self.Permissions(permission=perm)
        self.save()

    def add_permission_by_name(self, code, save=False):
        if not save:
            return ["%s | %s" % (p.name, p.code) for p in
                    Permission.objects.filter(code='*' + code + '*')]
        for p in Permission.objects.filter(code='*' + code + '*'):
            if p not in self.Permissions:
                self.Permissions(permission=p)
        if p:
            self.save()
