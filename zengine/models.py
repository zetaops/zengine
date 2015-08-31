# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from pyoko import field
from pyoko.model import Model, ListNode
from passlib.hash import pbkdf2_sha512


class Permission(Model):
    name = field.String("Name", index=True)
    code = field.String("Code Name", index=True)


class User(Model):
    username = field.String("Username", index=True)
    password = field.String("Password")

    class Permissions(ListNode):
        permission = Permission()

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
