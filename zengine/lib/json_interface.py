# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


import json
from zengine.lib.translation import LazyProxy


class ZEngineJSONEncoder(json.JSONEncoder):
    def default(self, o):
        # If the object is a deferred translation, do the translation now
        if isinstance(o, LazyProxy):
            return str(o)
        # Otherwise, let the default encoder handle the serialization
        return json.JSONEncoder.default(self, o)
