# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


def output_message(current):
    current.output['message'] = _('This is a translateable message.')
    current.output['untranslated'] = _('This message has not been translated.')