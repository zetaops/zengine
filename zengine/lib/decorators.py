# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from importlib import import_module

from pyoko.conf import settings

def runtime_importer():
    """
    auto imports modules listed under settings.AUTO_IMPORT_MODULES
    """
    for path in settings.AUTO_IMPORT_MODULES:
        import_module(path)


ROLE_GETTER_CHOICES = []
ROLE_GETTER_METHODS = {}

def role_getter(title):
    def act_dec(func):
        ROLE_GETTER_CHOICES.append((func.__name__, title))
        ROLE_GETTER_METHODS[func.__name__] = func
        return func
    return act_dec



VIEW_METHODS = {}

def view(path=None, debug_only=False):
    def act_dec(func):
        if not debug_only or settings.DEBUG:
            VIEW_METHODS["_zops_%s" % (path or func.__name__)] = func
        return func
    return act_dec

JOB_METHODS = {}

def bg_job(name=None):
    def act_dec(func):
        JOB_METHODS[name or func.__name__] = func
        return func
    return act_dec


