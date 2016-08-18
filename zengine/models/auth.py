# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from pyoko import Model, field, ListNode, LinkProxy
from passlib.hash import pbkdf2_sha512
from zengine.lib.cache import Cache
from zengine.messaging.lib import BaseUser


class Unit(Model):
    """Unit model

    Can be used to group users according to their physical or organizational position

    """
    name = field.String("İsim", index=True)
    parent = LinkProxy('Unit', verbose_name='Parent Unit', reverse_name='sub_units')

    class Meta:
        verbose_name = "Unit"
        verbose_name_plural = "Units"
        search_fields = ['name']
        list_fields = ['name',]

    def __unicode__(self):
        return '%s' % self.name


    @classmethod
    def get_user_keys(cls, unit_key):
        stack = User.objects.filter(unit_id=unit_key).values_list('key', flatten=True)
        for unit_key in cls.objects.filter(parent_id=unit_key).values_list('key', flatten=True):
            stack.extend(cls.get_user_keys(unit_key))
        return stack



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
    unit = Unit()

    class Meta:
        """ meta class
        """
        list_fields = ['username', 'superuser']

    def pre_save(self):
        self.encrypt_password()

    def post_creation(self):
        self.prepare_channels()

    def get_permissions(self):
        """
        Permissions of the user.

        Returns:
            List of Permission objects.
        """
        users_primary_role = self.role_set[0].role
        return users_primary_role.get_permissions()


class PermissionCache(Cache):
    """PermissionCache sınıfı Kullanıcıya Permission nesnelerinin
    kontrolünü hızlandırmak için yetkileri cache bellekte saklamak ve
    gerektiğinde okumak için oluşturulmuştur.
    """
    PREFIX = 'PRM'

    def __init__(self, role_id):
        super(PermissionCache, self).__init__(role_id)


class AbstractRole(Model):
    """
    AbstractRoles are stand as a foundation for actual roles
    """
    name = field.String("Name", index=True)
    read_only = field.Boolean("Archived")

    class Meta:
        verbose_name = "Abstract Role"
        verbose_name_plural = "Abstract Roles"
        search_fields = ['name']

    def __unicode__(self):
        return "%s" % self.name

    def get_permissions(self):
        """
        Soyut role ait Permission nesnelerini bulur ve code değerlerini
        döner.

        Returns:
            list: Permission code değerleri

        """
        return [p.permission.code for p in self.Permissions if p.permission.code]

    def add_permission(self, perm):
        """
        Soyut Role Permission nesnesi tanımlamayı sağlar.

        Args:
            perm (object):

        """
        self.Permissions(permission=perm)
        PermissionCache.flush()
        self.save()

    def add_permission_by_name(self, code, save=False):
        """
        Soyut role Permission eklemek veya eklenebilecek Permission
        nesnelerini verilen ``code`` parametresine göre listelemek olmak
        üzere iki şekilde kullanılır.

        Args:
            code (str): Permission nesnelerini filtre etmekte kullanılır
            save (bool): True ise Permission ekler, False ise Permission
                listesi döner.

        Returns:
            list: ``save`` False ise Permission listesi döner.

        """
        if not save:
            return ["%s | %s" % (p.name, p.code) for p in
                    Permission.objects.filter(code__contains=code)]
        PermissionCache.flush()
        for p in Permission.objects.filter(code__contains=code):
            if p not in self.Permissions:
                self.Permissions(permission=p)
        if p:
            self.save()

    class Permissions(ListNode):
        permission = Permission()

class Role(Model):
    """
    This model binds group of Permissions with a certain User.
    """
    arole = AbstractRole()
    user = User()

    class Meta:
        """
        Meta class
        """
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        crud_extra_actions = [{'name': 'Edit Permissions', 'wf': 'permissions', 'show_as': 'button'}]

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

    def remove_permission(self, perm):
        """
        Removes a :class:`Permission` from the role

        Args:
             perm: :class:`Permission` object.
        """
        del self.Permissions[perm.key]
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
