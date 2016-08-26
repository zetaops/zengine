# -*-  coding: utf-8 -*-
"""The view for the workflow used to change the language."""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.lib.translation import DEFAULT_PREFS


def change_language(current):
    for k in DEFAULT_PREFS.keys():
        current.session[k] = current.input.get(k)
