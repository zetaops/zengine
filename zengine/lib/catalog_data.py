# -*-  coding: utf-8 -*-
"""

"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from collections import defaultdict
from zengine.config import settings
from zengine.lib.cache import Cache, CatalogCache


class CatalogData(object):
    def __init__(self, current):
        self.lang = current.lang_code if current else settings.DEFAULT_LANG

    def get_from_db(self, key):
        from pyoko.db.connection import client
        data = client.bucket_type('catalog').bucket('ulakbus_settings_fixtures').get(key).data
        return self.parse_db_data(data, key)

    def parse_db_data(self, data, key):
        lang_dict = defaultdict(list)
        for k, v in data.items():
            for lang_code, lang_val in v.items():
                try:
                    k = int(k)
                except:
                    pass
                lang_dict[lang_code].append({'value': k, "name": lang_val})
        for lang_code, lang_set in lang_dict.items():
            CatalogCache(lang_code, key).set(lang_set)
        return lang_dict[self.lang]

    def get(self, key):
        """
        if data can't found in cache then it will be fetched from db,
         parsed and stored to cache for each lang_code.

        :param key: key of catalog data
        :return:
        """
        return CatalogCache(self.lang, key).get() or self.get_from_db(key)
