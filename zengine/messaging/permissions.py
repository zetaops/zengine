# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.auth.permissions import CustomPermission

CustomPermission.add_multi(
    # ('code_name', 'human_readable_name', 'description'),
    [
        ('messaging.can_invite_user_by_unit', 'Can invite all users of a unit', ''),
        ('messaging.can_invite_user_by_searching', 'Can invite any user by searching on name', ''),
    ])
