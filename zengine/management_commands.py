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
