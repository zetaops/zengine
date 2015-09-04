# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pyoko.manage import *


class UpdatePermissions(Command):
    CMD_NAME = 'update_permissions'
    HELP = 'Syncs permissions with DB'

    def run(self):
        from pyoko.lib.utils import get_object_from_path
        from zengine.permissions import get_all_permissions
        from zengine.config import settings
        model = get_object_from_path(settings.PERMISSION_MODEL)
        perms = []
        new_perms = []
        for code, name, desc in get_all_permissions():
            perm, new = model.objects.get_or_create({'description': desc}, code=code, name=name)
            perms.append(perm)
            if new:
                new_perms.append(perm)
        report = "Total %s permission exist. " \
                 "%s new permission record added.\n\n" % (len(perms), len(new_perms))
        if new_perms:
            report += "\n + " + "\n + ".join([p.name for p in new_perms])
        return report


class CreateUser(Command):
    CMD_NAME = 'create_user'
    HELP = 'Creates a new user'
    PARAMS = [
        ('username', True, 'Login username'),
        ('password', True, 'Login password'),
        ('super_user', False, 'Is super user'),
    ]

    def run(self):
        from zengine.config import settings
        from pyoko.lib.utils import get_object_from_path
        User = get_object_from_path(settings.USER_MODEL)
        user = User(username=self.manager.args.username,
                    superuser=bool(self.manager.args.super_user)
                    )
        user.set_password(self.manager.args.password)
        user.save()
        return "New user created with ID: %s" % user.key


class SetPermission(Command):
    CMD_NAME = 'set_perm'
    HELP = "Gives permissions to a user. Only works for ZEngine's own User & Permission models"
    PARAMS = [
        ('username', True,
         'Login username. Will list existing perms of the user if no other option given.'),
        ('perms', False, 'Permission codename(s). Separate with commas. Wildcard can be used\n'
                         'eg: login*,*.add*,*.delete*'),
        ('apply', False, 'Apply the result of the perm query.')

    ]

    def run(self):
        from zengine.models import User, Permission
        user = User(username=self.manager.args.username,
                    superuser=bool(self.manager.args.super_user)
                    )

        if self.manager.args.perms:
            perms = []
            for prt in self.manager.args.perms.split(','):
                perms.append("code:%s" % prt)
            query = " OR ".join(perms)
            permissions = list(Permission.objects.raw(query))
            print("Query result:")
            print("\n ~ %s - %s" % (perm.name, perm.code) for perm in permissions)

            if self.manager.args.apply:
                for perm in permissions:
                    user.Permissions(permission=perm)
                user.save()
                print("Applied %s perms to the user" % len(permissions))
        else:
            print("Existing permissions of the user:")
            print("\n ~ %s - %s" % (perm.name, perm.code) for perm in user.Permissions)
