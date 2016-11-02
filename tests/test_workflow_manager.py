# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


from zengine.lib.test_utils import BaseTestCase
from .models import Task, BPMNWorkflow, Unit, AbstractRole, User, TaskInvitation, WFInstance, Role, Teacher
from datetime import datetime, timedelta
from pyoko.conf import settings
from pyoko.lib.utils import get_object_from_path
import time

RoleModel = get_object_from_path(settings.ROLE_MODEL)

class TestCase(BaseTestCase):

    def test_workflow_management_state_finished(self):
        # create test task manager object with bpmn workflow, unit and abstract role models
        task = Task()
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        task.name = task.wf.title
        task.unit = Unit.objects.get(name="Test Unit")
        task.abstract_role = AbstractRole.objects.get(name='Test AbstractRole')
        # add past time
        task.start_date = datetime.strptime('10.10.2016', '%d.%m.%Y')
        task.finish_date = datetime.strptime('12.10.2016', '%d.%m.%Y')
        task.run = True
        task.save()

        usr = User.objects.get(username='test_user')
        self.prepare_client(user=usr)
        time.sleep(1)
        # call finished data
        resp = self.client.post(view='_zops_get_tasks', state='finished')
        # We control the get_tasks view
        assert resp.json['task_list'][0]['wf_type'] == 'workflow_management'
        assert resp.json['task_list'][0]['title'] == 'workflow_management'

        key = resp.json['task_list'][0]['key']  # TaskInvitation key
        instance_key = resp.json['task_list'][0]['token']   # WFInstance key
        resp = self.client.post(view='_zops_get_task_detail', key=key)
        # We control the get_task_detail view
        assert resp.json['task_detail'] == 'Explain: \n    State: 40'

        resp = self.client.post(view='_zops_get_task_actions', key=key)
        # We control the get_task_actions view
        assert len(resp.json['actions'][0]) == 2

        resp = self.client.post(view='_zops_get_task_types')
        # We control the get_task_types view
        assert len(resp.json['task_types']) == 8

        wf_instance = WFInstance.objects.get(instance_key)

        # Remove test data
        task = Task.objects.get(key=wf_instance.task.key)
        task.blocking_delete()
        task_inv = TaskInvitation.objects.get(key=key)
        task_inv.blocking_delete()
        wf_instance.blocking_delete()

    def test_workflow_management_state_active(self):
        # creating active date
        now = datetime.now()
        one_day = timedelta(1)
        tomorrow = now + one_day
        yesterday = now - one_day

        usr = User.objects.get(username='test_user2')
        # create test task manager object with bpmn workflow, unit, abstract role and role models
        task = Task()
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        task.name = task.wf.title
        task.unit = Unit.objects.get(name="Test Unit")
        task.abstract_role = AbstractRole.objects.get(name='Test AbstractRole')
        task.role = Role.objects.get(user=usr)
        task.object_type = 'Exam'   # Exam model
        # search operation is done in Exam model
        task.object_query_code = {'teacher_id': Teacher.objects.filter()[0].key}
        task.start_date = datetime.strptime(yesterday.strftime("%d.%m.%Y"), '%d.%m.%Y')
        task.finish_date = datetime.strptime(tomorrow.strftime("%d.%m.%Y"), '%d.%m.%Y')
        task.run = True
        task.save()

        usr = User.objects.get(username='test_user2')
        self.prepare_client(user=usr)
        time.sleep(1)
        # call active data
        resp = self.client.post(view='_zops_get_tasks', state='active')
        # We control the get_tasks view
        assert resp.json['task_list'][0]['wf_type'] == 'workflow_management'
        assert resp.json['task_list'][0]['title'] == 'workflow_management'
        assert resp.json['task_list'][0]['state'] == 30

        key = resp.json['task_list'][0]['key']  # TaskInvitation key
        instance_key = resp.json['task_list'][0]['token']   # WFInstance key
        resp = self.client.post(view='_zops_get_task_detail', key=key)
        # We control the get_task_detail view
        assert resp.json['task_detail'] == 'Explain: Alan Turing\n    State: 30'

        resp = self.client.post(view='_zops_get_task_actions', key=key)
        # We control the get_task_actions view
        assert len(resp.json['actions'][0]) == 2

        resp = self.client.post(view='_zops_get_task_types')
        # We control the get_task_types view
        assert len(resp.json['task_types']) == 8

        wf_instance = WFInstance.objects.get(instance_key)

        # Remove test data
        task = Task.objects.get(key=wf_instance.task.key)
        task.blocking_delete()
        task_inv = TaskInvitation.objects.get(key=key)
        task_inv.blocking_delete()
        wf_instance.blocking_delete()

    def test_workflow_management_state_future(self):
        # creating future date
        now = datetime.now()
        one_week = timedelta(7)
        next_week = now + one_week
        next_week_tomorrow = next_week + timedelta(1)
        # create test task manager object with bpmn workflow and abstract role models
        task = Task()
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        task.abstract_role = AbstractRole.objects.get(name='Test AbstractRole')
        task.name = task.wf.title
        # add future date
        task.start_date = datetime.strptime(next_week.strftime("%d.%m.%Y"), '%d.%m.%Y')
        task.finish_date = datetime.strptime(next_week_tomorrow.strftime("%d.%m.%Y"), '%d.%m.%Y')
        task.run = True
        task.save()

        usr = User.objects.get(username='test_user2')
        self.prepare_client(user=usr)
        time.sleep(1)
        # call future data
        resp = self.client.post(view='_zops_get_tasks', state='future')
        # We control the get_tasks view
        assert resp.json['task_list'][0]['wf_type'] == 'workflow_management'
        assert resp.json['task_list'][0]['title'] == 'workflow_management'
        assert resp.json['task_list'][0]['state'] == 10

        key = resp.json['task_list'][0]['key']  # TaskInvitation key
        instance_key = resp.json['task_list'][0]['token']   # WFInstance key

        resp = self.client.post(view='_zops_get_task_detail', key=key)
        # We control the get_task_detail view
        assert resp.json['task_detail'] == 'Explain: \n    State: 10'

        resp = self.client.post(view='_zops_get_task_actions', key=key)
        # We control the get_task_actions view
        assert len(resp.json['actions'][0]) == 2

        resp = self.client.post(view='_zops_get_task_types')
        # We control the get_task_types view
        assert len(resp.json['task_types']) == 8

        wf_instance = WFInstance.objects.get(instance_key)

        # Remove test data
        task = Task.objects.get(key=wf_instance.task.key)
        task.blocking_delete()
        task_inv = TaskInvitation.objects.get(key=key)
        task_inv.blocking_delete()
        wf_instance.blocking_delete()

    def test_object_and_query_task_manager(self):
        # We send the object. Individual workflow assignment method to sub roles
        # create new task manager
        task = Task()
        # workflow is chosen
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        # task name is workflow title
        task.name = task.wf.title
        # upper unit is chosen
        task.unit = Unit.objects.get(name="Test Parent Unit 2")
        # abstract role is chosen
        task.abstract_role = AbstractRole.objects.get(name='Test AbstractRole')
        # selected model needed for workflow
        task.object_type = 'Program'   # Program model
        # model query code is written.
        task.object_query_code = {'role': 'role'}
        # set start and end time of the workflow
        task.start_date = datetime.strptime('05.05.2016', '%d.%m.%Y')
        task.finish_date = datetime.strptime('06.05.2016', '%d.%m.%Y')
        # assignment to subunits of the selected unit
        task.recursive_units = True
        task.run = True
        task.save()

        time.sleep(1)

        # expected task manager objects numbers

        tsk = Task.objects.filter(start_date=datetime(2016, 5, 5, 0, 0))

        taskinv = TaskInvitation.objects.filter(start_date=datetime(2016, 5, 5, 0, 0))

        assert len(tsk) == 1
        wfi = WFInstance.objects.filter(task=tsk[0])
        assert len(wfi) == 5
        assert len(taskinv) == 5

        # delete test datas
        tsk.delete()
        wfi.delete()
        taskinv.delete()

    def test_abstractrole_and_unit_task_manager(self):
        # task manager creates person-specific workflows for persons which has the same abstract roles
        # object is in the workflow

        # create new task manager
        task = Task()
        # workflow is chosen
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        # task name is workflow title
        task.name = task.wf.title
        # upper unit is chosen
        task.unit = Unit.objects.get(name='Test Parent Unit')
        # abstract role is chosen
        task.abstract_role = AbstractRole.objects.get(name='Test AbstractRole 2')
        # set start and end time of the workflow
        task.start_date = datetime.strptime('06.06.2016', '%d.%m.%Y')
        task.finish_date = datetime.strptime('07.06.2016', '%d.%m.%Y')
        # assignment to subunits of the selected unit
        task.recursive_units = True

        task.run = True
        task.save()

        time.sleep(1)

        # expected task manager objects numbers
        tsk = Task.objects.filter(start_date=datetime(2016, 6, 6, 0, 0))
        assert len(tsk) == 1
        wfi = WFInstance.objects.filter(task=tsk[0])
        assert len(wfi) == 1
        taskinv = TaskInvitation.objects.filter(start_date=datetime(2016, 6, 6, 0, 0))
        assert len(taskinv) == 1

        # delete test datas
        tsk.delete()
        wfi.delete()
        taskinv.delete()

    def test_wf_and_role_getter_task_manager(self):
        # A workflow assignment method that users with the same abstract role will see.
        # object is in the workflow
        # create new task manager
        task = Task()
        # workflow is chosen
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        # task name is workflow title
        task.name = task.wf.title
        # the selected abstract role for workflow
        task.get_roles_from = 'get_test_role'
        # set start and end time of the workflow
        task.start_date = datetime.strptime('07.07.2016', '%d.%m.%Y')
        task.finish_date = datetime.strptime('08.07.2016', '%d.%m.%Y')
        task.run = True
        task.save()

        time.sleep(1)

        # expected task manager objects numbers
        tsk = Task.objects.filter(start_date=datetime(2016, 7, 7, 0, 0))
        assert len(tsk) == 1
        wfi = WFInstance.objects.filter(task=task)
        assert len(wfi) == 1
        taskinv = TaskInvitation.objects.filter(start_date=datetime(2016, 7, 7, 0, 0))
        assert len(taskinv) == 2

        # delete test datas
        tsk.delete()
        wfi.delete()
        taskinv.delete()

    def test_role_getter_object_and_query_task_manager(self):
        # A workflow assignment method that users with the same abstract role will see.
        # We send the object.
        # create new task manager
        task = Task()
        # workflow is chosen
        task.wf = BPMNWorkflow.objects.get(name='workflow_management')
        # task name is workflow title
        task.name = task.wf.title
        # the selected abstract role for workflow
        task.get_roles_from = 'get_test_role'
        # selected model needed for workflow
        task.object_type = 'Program'   # Program model
        # model query code is written.
        task.object_query_code = {'type': 1} # Program.objects.filter(type = 1)
        # set start and end time of the workflow
        task.start_date = datetime.strptime('08.08.2016', '%d.%m.%Y')
        task.finish_date = datetime.strptime('09.08.2016', '%d.%m.%Y')
        task.run = True
        task.save()

        time.sleep(1)

        # expected task manager objects numbers
        tsk = Task.objects.filter(start_date=datetime(2016, 8, 8, 0, 0))
        assert len(tsk) == 1
        wfi = WFInstance.objects.filter(task=task)
        assert len(wfi) == 3
        taskinv = TaskInvitation.objects.filter(start_date=datetime(2016, 8, 8, 0, 0))
        assert len(taskinv) == 6

        # delete test datas
        tsk.delete()
        wfi.delete()
        taskinv.delete()
