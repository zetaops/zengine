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
        self.prepare_client('crud')

        # calling the crud view without any model should list available models
        resp = self.client.post()
        resp.raw()
        assert resp.json['models'] == [[m.Meta.verbose_name, m.__name__] for m in
                                       model_registry.get_base_models()]
        model_name = resp.json['models'][0][0]
        # calling with just model name (without any cmd) equals to cmd="list"
        resp = self.client.post(model=model_name, filters={"username": username})
        assert 'objects' in resp.json
        list_objects = resp.json['objects']
        if list_objects:
            assert list_objects[0]['data']['username'] == username

        resp = self.client.post(model=model_name)
        # count number of records
        num_of_objects = len(resp.json['objects'])

        # add a new employee record, then go to list view (do_list subcmd)
        self.client.post(model=model_name, cmd='add')
        resp = self.client.post(model=model_name,
                                cmd='add',
                                subcmd="do_list",
                                form=dict(username="fake_user", password="123"))

        # we should have 1 more object relative to previous listing
        assert num_of_objects + 1 == len(resp.json['objects'])
        # since we are searching for a just created record, we have to wait
        sleep(1)
        resp = self.client.post(model=model_name, filters={"username": "fake_user"})

        # delete the first object then go to list view
        resp = self.client.post(model=model_name,
                                cmd='delete',
                                subcmd="do_list",
                                object_id=resp.json['objects'][0]['key'])

        # number of objects should be equal to starting point
        assert num_of_objects == len(resp.json['objects'])







