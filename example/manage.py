# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.management_commands import *

# environ.setdefault('PYOKO_SETTINGS', 'example.settings')
environ['PYOKO_SETTINGS'] = 'example.settings'
environ['ZENGINE_SETTINGS'] = 'example.settings'
ManagementCommands(argv[1:], commands=[UpdatePermissions])



