# -*-  coding: utf-8 -*-
"""project settings"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


from zengine.settings import *

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

ACTIVITY_MODULES_IMPORT_PATHS += ['tests.views']

WORKFLOW_PACKAGES_PATHS += [os.path.join(BASE_DIR, 'diagrams')]

TRANSLATIONS_DIR = os.path.join(BASE_DIR, 'locale')
TRANSLATION_DOMAINS['messages'] = 'en'