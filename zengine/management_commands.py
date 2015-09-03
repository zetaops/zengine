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
    PERMISSION_MODEL_PATH = 'zengine.models.Permission'
    def run(self):
        from pyoko.lib.utils import get_object_from_path
        from zengine.permissions import get_all_permissions
        model = get_object_from_path(self.PERMISSION_MODEL_PATH)
        perms = []
        new_perms = []
        for code, name, desc in get_all_permissions():
            perm, new = model.objects.get_or_create({'description': desc}, code=code, name=name)
            perms.append(perm)
            if new:
                new_perms.append(perm)
        self.manager.report = "Total %s permission exist. " \
                              "%s new permission record added.\n\n" % (len(perms), len(new_perms))
        if new_perms:

            self.manager.report += "\n + " + "\n + ".join([p.name for p in new_perms])
