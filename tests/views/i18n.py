# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import datetime
from zengine.lib.translation import gettext as _, ngettext, markonly as N_,\
    format_datetime, format_decimal, get_day_names, gettext_lazy


MSG_LAZY = gettext_lazy(u'This is a translateable message.')

def output_message(current):
    current.output['message'] = _(u'This is a translateable message.')
    current.output['lazy'] = MSG_LAZY
    current.output['untranslated'] = _(u'This message has not been translated.')
    current.output['singular'] = ngettext(u'One', u'Many', 1)
    current.output['plural'] = ngettext(u'One', u'Many', 50)
    marked_message = N_(u'This message is marked, but not translated yet.')
    current.output['marked'] = marked_message
    current.output['marked_translated'] = _(marked_message)
    current.output['datetime'] = format_datetime(datetime.datetime(2016, 7, 21, 17, 32))
    current.output['decimal'] = format_decimal(1.23456)
    current.output['second_day'] = get_day_names()[1]
