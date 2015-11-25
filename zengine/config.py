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
from pyoko.lib.utils import get_object_from_path
from pyoko.conf import settings
# settings = importlib.import_module(os.getenv('ZENGINE_SETTINGS'))

# AuthBackend = get_object_from_path(settings.AUTH_BACKEND)

beaker.cache.clsmap = _backends({'redis': redis_.RedisManager})

