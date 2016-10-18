# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


from zengine.lib.test_utils import BaseTestCase
from .models import Task, BPMNWorkflow, Unit, AbstractRole, User, TaskInvitation, WFInstance, Role, Teacher, Exam
from datetime import datetime, timedelta
import time


class TestCase(BaseTestCase):

    def test_workflow_management(self):

        task = Task()
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        task.name = task.wf.title
        task.unit = Unit.objects.get(name="Test Unit")
        task.abstract_role = AbstractRole.objects.get(name='Test AbstractRole')
        task.start_date = datetime.strptime('10.10.2016', '%d.%m.%Y')
        task.finish_date = datetime.strptime('12.10.2016', '%d.%m.%Y')
        task.run = True
        task.save()

        usr = User.objects.get(username='test_user')
        self.prepare_client('/workflow_management/', user=usr)
        self.client.post()
        time.sleep(1)
        resp = self.client.post(view='_zops_get_tasks', state='finished')

        assert resp.json['task_list'][0]['wf_type'] == 'workflow_management'
        assert resp.json['task_list'][0]['title'] == 'workflow_management'

        key = resp.json['task_list'][0]['key']  # TaskInvitation key
        instance_key = resp.json['task_list'][0]['token']   # WFInstance key
        resp = self.client.post(view='_zops_get_task_detail', key=key)

        assert resp.json['task_detail'] == 'Açıklama: \n    Durum: 40'

        resp = self.client.post(view='_zops_get_task_actions', key=key)

        assert len(resp.json['actions'][0]) == 2

        resp = self.client.post(view='_zops_get_task_types')

        assert len(resp.json['task_types']) == 8

        wf_instance = WFInstance.objects.get(instance_key)

        # Remove test data
        task = Task.objects.get(key=wf_instance.task.key)
        task.blocking_delete()
        task_inv = TaskInvitation.objects.get(key=key)
        task_inv.blocking_delete()
        wf_instance.blocking_delete()

    def test_oe_not_girisi_is_akisi_atama(self):
        now = datetime.now()
        one_day = timedelta(1)
        tomorrow = now + one_day
        yesterday = now - one_day
        usr = User.objects.get(username='test_user2')
        task = Task()
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        task.name = task.wf.title
        task.unit = Unit.objects.get(name="Test Unit")
        task.abstract_role = AbstractRole.objects.get(name='Test AbstractRole')
        task.role = Role.objects.get(user=usr)
        task.object_type = 'Exam'
        task.object_query_code = {'teacher_id': Teacher.objects.filter()[0].key}
        task.start_date = datetime.strptime(yesterday.strftime("%d.%m.%Y"), '%d.%m.%Y')
        task.finish_date = datetime.strptime(tomorrow.strftime("%d.%m.%Y"), '%d.%m.%Y')
        task.run = True
        task.save()

        usr = User.objects.get(username='test_user2')
        self.prepare_client('/workflow_management/', user=usr)
        self.client.post()
        time.sleep(1)
        resp = self.client.post(view='_zops_get_tasks', state='active')

        assert resp.json['task_list'][0]['wf_type'] == 'workflow_management'
        assert resp.json['task_list'][0]['title'] == 'workflow_management'
        assert resp.json['task_list'][0]['state'] == 30

        key = resp.json['task_list'][0]['key']  # TaskInvitation key
        instance_key = resp.json['task_list'][0]['token']   # WFInstance key
        resp = self.client.post(view='_zops_get_task_detail', key=key)

        assert resp.json['task_detail'] == 'Açıklama: Alan Turing\n    Durum: 30'

        resp = self.client.post(view='_zops_get_task_actions', key=key)

        assert len(resp.json['actions'][0]) == 2

        resp = self.client.post(view='_zops_get_task_types')

        assert len(resp.json['task_types']) == 8

        wf_instance = WFInstance.objects.get(instance_key)

        # Remove test data
        task = Task.objects.get(key=wf_instance.task.key)
        task.blocking_delete()
        task_inv = TaskInvitation.objects.get(key=key)
        task_inv.blocking_delete()
        wf_instance.blocking_delete()

    def test_sistem_is_akisi_atama(self):
        now = datetime.now()
        one_week = timedelta(7)
        next_week = now + one_week
        next_week_tomorrow = next_week + timedelta(1)
        task = Task()
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        task.abstract_role = AbstractRole.objects.get(name='Test AbstractRole')
        task.name = task.wf.title
        task.start_date = datetime.strptime(next_week.strftime("%d.%m.%Y"), '%d.%m.%Y')
        task.finish_date = datetime.strptime(next_week_tomorrow.strftime("%d.%m.%Y"), '%d.%m.%Y')
        task.run = True
        task.save()

        usr = User.objects.get(username='test_user2')
        self.prepare_client('/workflow_management/', user=usr)
        self.client.post()
        time.sleep(1)
        resp = self.client.post(view='_zops_get_tasks', state='future')

        assert resp.json['task_list'][0]['wf_type'] == 'workflow_management'
        assert resp.json['task_list'][0]['title'] == 'workflow_management'
        assert resp.json['task_list'][0]['state'] == 10

        key = resp.json['task_list'][0]['key']  # TaskInvitation key
        instance_key = resp.json['task_list'][0]['token']   # WFInstance key
        resp = self.client.post(view='_zops_get_task_detail', key=key)

        assert resp.json['task_detail'] == 'Açıklama: \n    Durum: 10'

        resp = self.client.post(view='_zops_get_task_actions', key=key)

        assert len(resp.json['actions'][0]) == 2

        resp = self.client.post(view='_zops_get_task_types')

        assert len(resp.json['task_types']) == 8

        wf_instance = WFInstance.objects.get(instance_key)

        # Remove test data
        task = Task.objects.get(key=wf_instance.task.key)
        task.blocking_delete()
        task_inv = TaskInvitation.objects.get(key=key)
        task_inv.blocking_delete()
        wf_instance.blocking_delete()
