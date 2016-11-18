# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.lib.test_utils import BaseTestCase
from zengine.models import TaskInvitation
from pyoko.lib.utils import get_object_from_path
from pyoko.conf import settings

RoleModel = get_object_from_path(settings.ROLE_MODEL)


class TestCase(BaseTestCase):

    def test_assign_yourself(self):
        # Test data is reset
        inv = TaskInvitation.objects.get("Ewn4V1Iih7htogD7kLyyWthswxr")
        inv.role = RoleModel()
        inv.save()
        wfi = inv.instance
        wfi.current_actor = RoleModel()
        wfi.save()

        # We will take the workflow to ourselves.
        for i in range(2):
            self.prepare_client('/task_assign_yourself/', username='test_user')
            resp = self.client.post(task_inv_key="Ewn4V1Iih7htogD7kLyyWthswxr")
            if i == 0:
                # The first step is to be successful.
                assert resp.json['msgbox']['title'][0] == "Successful"
            else:
                # We will wait for the second step to fail because the workflow will be assigned.
                assert resp.json['msgbox']['title'][0] == "Unsuccessful"

    def test_assign_to_someone_else(self):
        for i in range(2):
            self.prepare_client('/assign_same_abstract_role/', username='test_user')
            self.client.post()
            resp = self.client.post(task_inv_key="Ewn4V1Iih7htogD7kLyyWthswxr",
                                    form={"select_role": "NdOZ5WODiDYSdmjHCKt6Ax1sryA",
                                          "explain_text": "Test"})
            if i == 0:
                print resp.json['msgbox']['title'][0] == "Successful"
            else:
                print resp.json['msgbox']['title'][0] == "Unsuccessful"

    def test_postponed_workflow(self):
        self.prepare_client('/postpone_workflow/', username='test_user2')
        self.client.post()
        resp = self.client.post(task_inv_key="Ewn4V1Iih7htogD7kLyyWthswxr",
                                form={"start_date": "15.10.2017",
                                      "finish_date": "20.10.2017"})

        assert resp.json['msgbox']['title'][0] == "Successful"

    def test_suspend_workflow(self):
        for i in range(2):
            self.prepare_client('/suspend_workflow/', username='test_user2')
            resp = self.client.post(task_inv_key="Ewn4V1Iih7htogD7kLyyWthswxr")

            if i == 0:
                print resp.json['msgbox']['title'][0] == "Successful"
            else:
                print resp.json['msgbox']['title'][0] == "Unsuccessful"
