# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from time import sleep
from pyoko.model import model_registry
from zengine.lib.test_utils import BaseTestCase, username

RESPONSES = {}

class TestCase(BaseTestCase):
    def test_list_search_add_delete_with_user_model(self):

        # setup workflow
        self.prepare_client('/crud/')

        # calling the crud view without any model should list available models
        resp = self.client.post()
        resp.raw()
        assert resp.json['models'] == [[m.Meta.verbose_name_plural, m.__name__] for m in
                                       model_registry.get_base_models()]
        model_name = 'User'
        # calling with just model name (without any cmd) equals to cmd="list"
        resp = self.client.post(model=model_name, filters={"username": username})
        assert 'nobjects' in resp.json
        assert resp.json['nobjects'][1][1] == username

        resp = self.client.post(model=model_name, cmd='list')
        # count number of records
        num_of_objects = len(resp.json['nobjects']) - 1

        # add a new employee record, then go to list view (do_list subcmd)
        self.client.post(model=model_name, cmd='add')
        resp = self.client.post(model=model_name,
                                cmd='add',
                                subcmd="do_show",
                                form=dict(username="fake_user", password="123"))
        assert resp.json['object']['username'] == 'fake_user'

        # we should have 1 more object relative to previous listing
        # assert num_of_objects + 1 == len(resp.json['nobjects']) - 1
        # since we are searching for a just created record, we have to wait
        sleep(1)
        # resp = self.client.post(model=model_name, filters={"username": "fake_user"})

        # delete the first object then go to list view
        resp = self.client.post(model=model_name,
                                cmd='delete',
                                subcmd="do_list",
                                object_id=resp.json['object']['key'])

        # resp = self.client.post(model=model_name, cmd='list')
        # number of objects should be equal to starting point
        assert num_of_objects == len(resp.json['nobjects']) - 1







