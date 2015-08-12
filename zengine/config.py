# -*-  coding: utf-8 -*-
"""configuration"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import importlib
from beaker.cache import _backends
import os
import beaker
from beaker_extensions import redis_
from zengine import middlewares

settings = importlib.import_module(os.getenv('ZENGINE_SETTINGS'))

AuthBackend = importlib.import_module(settings.AUTH_BACKEND)

beaker.cache.clsmap = _backends({'redis': redis_.RedisManager})

SESSION_OPTIONS = {
    'session.cookie_expires': True,
    'session.type': 'redis',
    'session.url': settings.REDIS_SERVER,
    'session.auto': True,
    'session.path': '/',
}

ENABLED_MIDDLEWARES = [
    middlewares.RequireJSON(),
    middlewares.JSONTranslator(),
    middlewares.CORS(),
]
