# -*-  coding: utf-8 -*-
"""
Catalog Data module.
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from collections import defaultdict

import six

from zengine.config import settings
from zengine.lib.cache import Cache, CatalogCache


class CatalogData(object):
    """
    Manager object for the user updatable multi language texts
    """

    # this will be set by langua_support middleware
    CURRENT_LANG_CODE = None

    # cache for filling the selectboxes  (list of dicts)
    # ['tr']['country'] = [{'name':'Turkey', 'value':'tr'},]
    CACHE = defaultdict(dict)

    # cache for individual items
    # ['tr']['country']['tr'] = 'Turkey'
    ITEM_CACHE = defaultdict(dict)

    def _get_lang(self):
        return self.CURRENT_LANG_CODE or settings.DEFAULT_LANG

    def _get_from_db(self, cat):
        from pyoko.db.connection import client
        data = client.bucket_type('catalog').bucket('ulakbus_settings_fixtures').get(cat).data
        return self._parse_db_data(data, cat)

    def _parse_db_data(self, data, cat):
        assert data, "Catalog Data is not set for %s" % cat
        lang_dict = defaultdict(list)
        for k, v in data.items():
            for lang_code, lang_val in v.items():
                try:
                    k = int(k)
                except:
                    pass
                # self.ITEM_CACHE[lang_code][cat][k] = lang_val
                lang_dict[lang_code].append({'value': k, "name": lang_val})
        for lang_code, lang_set in lang_dict.items():
            CatalogCache(lang_code, cat).set(lang_set)
            self.CACHE[lang_code][cat] = lang_set
        return lang_dict[self._get_lang()]

    def get_all(self, cat):
        """
        if data can't found in cache then it will be fetched from db,
         parsed and stored to cache for each lang_code.

        :param cat: cat of catalog data
        :return:
        """
        return self._get_from_local_cache(cat) or self._get_from_cache(cat) or self._get_from_db(cat)

    def get_all_as_dict(self, cat):
        """
        Transforms get_all method's results to key value pairs in dict.
        
        Args:
            cat(str): catalog data key name 

        Returns(dict): key-value pair dict.
        
        """
        return {item['value']: item['name'] for item in self.get_all(cat)}

    def _get_from_cache(self, cat):
        lang = self._get_lang()
        self.CACHE[lang][cat] = CatalogCache(self._get_lang(), cat).get()
        return self.CACHE[lang][cat]

    def _get_from_local_cache(self, cat):
        return self.CACHE[self._get_lang()].get(cat)

    def _fill_get_item_cache(self, catalog, key):
        """
        get from redis, cache locally then return

        :param catalog: catalog name
        :param key:
        :return:
        """
        lang = self._get_lang()
        keylist = self.get_all(catalog)
        self.ITEM_CACHE[lang][catalog] = dict([(i['value'],  i['name']) for i in keylist])
        return self.ITEM_CACHE[lang][catalog].get(key)

    def _get_from_static_tuple(self, catalog, key):
        dct = dict(catalog)
        return dct.get(key)

    def __call__(self, catalog, key):
        if isinstance(catalog, six.string_types):
            return self.ITEM_CACHE.get(catalog, {}).get(key) or self._fill_get_item_cache(catalog, key)
        elif callable(catalog):
            return self._get_from_static_tuple(catalog(), key)
        else:
            return self._get_from_static_tuple(catalog, key)

catalog_data_manager = CatalogData()

