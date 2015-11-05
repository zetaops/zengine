# -*-  coding: utf-8 -*-
"""

"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from collections import defaultdict
from zengine.config import settings
from zengine.lib.cache import Cache


class CatalogData(object):
    def __init__(self, current):
        self.lang = current.lang_code if current else settings.DEFAULT_LANG
        self.cache_key_tmp = 'CTDT_{key}_{lang_code}'

    def get_from_db(self, key):
        from pyoko.db.connection import client
        data = client.bucket_type('catalog').bucket('ulakbus_settings_fixtures').get(key).data
        return self.parse_db_data(data, key)

    def parse_db_data(self, data, key):
        lang_dict = defaultdict(list)
        for k, v in data.items():
            for lang_code, lang_val in v.items():
                lang_dict[lang_code].append({'value': k, "name": lang_val})
        for lang_code, lang_set in lang_dict.items():
            Cache(self.cache_key_tmp.format(key=key, lang_code=lang_code), serialize=True).set(
                lang_set)
        return lang_dict[self.lang]

    def get_from_cache(self, key):
        return Cache(self.cache_key_tmp.format(key=key, lang_code=self.lang), serialize=True).get()

    def get(self, key):
        return self.get_from_cache(key) or self.get_from_db(key)
