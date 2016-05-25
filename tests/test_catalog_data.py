# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.lib.test_utils import BaseTestCase
from pyoko.db.connection import client

RESPONSES = {}
fixture_bucket = client.bucket_type('catalog').bucket('ulakbus_settings_fixtures')


class TestCase(BaseTestCase):
    def test_catalog_data_edit_save(self):
        # setup workflow
        self.prepare_client('/edit_catalog_data/', username='test_user')

        resp = self.client.post(filters={})
        # check if forms in response object
        assert 'forms' in resp.json
        # check is forms schema has ListNode named 'catalog' and its title is 'Catalogs'
        assert resp.json['forms']['schema']['properties']['catalog']['title'] == 'Catalogs'

        resp = self.client.post(cmd="get_catalog",form={"edit":1,"catalog":"tip_fakultesi_roller"})

        # check if forms object returns with model data
        assert 'catalog_key' in resp.json['forms']['model']['CatalogDatas'][0]

        # check add/edit catalog data and save
        # must be return notify success
        resp = self.client.post(
            cmd="save_catalog",
            object_key="test catalog",
            flow="start",
            form={"CatalogDatas": [{"catalog_key": "0", "en": "test_tr", "tr": "test_tr"}]})
        assert 'updated' in resp.json['notify']

        resp = self.client.post(cmd="get_catalog",form={"edit":1,"catalog":"tip_fakultesi_roller"})
        resp = self.client.post(
            cmd="cancel",
            object_key="test catalog",
            flow="start",
            form={"CatalogDatas": [{"catalog_key": "0", "en": "test_tr", "tr": "test_tr"}]})

        assert 'canceled' in resp.json['notify']


