# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.lib.translation import gettext as _, ngettext, markonly as N_


def output_message(current):
    current.output['message'] = _('This is a translateable message.')
    current.output['untranslated'] = _('This message has not been translated.')
    current.output['singular'] = ngettext('One', 'Many', 1)
    current.output['plural'] = ngettext('One', 'Many', 50)
    marked_message = N_('This message is marked, but not translated yet.')
    current.output['marked'] = marked_message
    current.output['marked_translated'] = _(marked_message)
