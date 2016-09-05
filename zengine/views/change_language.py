# -*-  coding: utf-8 -*-
"""The view for the workflow used to change the language."""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.lib.translation import DEFAULT_PREFS


def change_language(current):
    user = current.user
    for locale_pref in current.input.keys():
        # Make sure that an actual preference has been passed to the workflow
        if locale_pref in DEFAULT_PREFS:
            pref = current.input.get(locale_pref)
            # Set the locale preference in the session to change the current locale
            current.session[locale_pref] = pref
            # If the user is not anonymous, set the locale in their user model for future logins
            if user.key:
                setattr(user, locale_pref, pref)
    if user.key:
        user.save()
