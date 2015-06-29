# -*-  coding: utf-8 -*-
from __future__ import print_function, absolute_import, division

from __future__ import division
from io import BytesIO

from SpiffWorkflow.bpmn.storage.Packager import Packager, main
from SpiffWorkflow.bpmn.parser.BpmnParser import BpmnParser
from zengine.camunda_parser import CamundaBMPNParser
from zengine.utils import DotDict

"""
ZEnging engine class
import, extend and override load_workflow and save_workflow methods
override the cleanup method if you need to run some cleanup code after each run cycle
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
__author__ = "Evren Esat Ozkan"
import os.path
from importlib import import_module
from SpiffWorkflow.bpmn.BpmnWorkflow import BpmnWorkflow
from SpiffWorkflow.bpmn.storage.BpmnSerializer import BpmnSerializer
from SpiffWorkflow.bpmn.storage.CompactWorkflowSerializer import CompactWorkflowSerializer
from SpiffWorkflow import Task
from SpiffWorkflow.specs import WorkflowSpec
from SpiffWorkflow.storage import DictionarySerializer



class InMemoryPackager(Packager):

    PARSER_CLASS = CamundaBMPNParser

    @classmethod
    def package_in_memory(cls, workflow_name, workflow_files):
        s = BytesIO()
        p = cls(s, workflow_name, meta_data=[])
        p.add_bpmn_files_by_glob(workflow_files)
        p.create_package()
        return s.getvalue()

class ZEngine(object):
    """

    """
    WORKFLOW_DIRECTORY = ''  # relative or absolute directory path
    ACTIVITY_MODULES_PATH = ''  # python import path

    def __init__(self):

        self.current = DotDict()
        self.activities = {}
        self.workflow = BpmnWorkflow
        self.workflow_spec = WorkflowSpec

    def _load_workflow(self):
        serialized_wf = self.load_workflow(self.current.workflow_name)
        if serialized_wf:
            # return BpmnWorkflow.deserialize(DictionarySerializer(), serialized_wf)
            return CompactWorkflowSerializer().deserialize_workflow(
                serialized_wf, workflow_spec=self.current.spec)

    def create_workflow(self):
        # wf_pkg_file = self.get_worfklow_spec()
        # self.workflow_spec = BpmnSerializer().deserialize_workflow_spec(wf_pkg_file)
        self.workflow_spec = self.get_worfklow_spec()
        return BpmnWorkflow(self.workflow_spec)

    def load_or_create_workflow(self):
        """
        Tries to load the previously serialized (and saved) workflow
        Creates a new one if it can't
        """
        self.workflow = self._load_workflow() or self.create_workflow()

    def get_worfklow_spec(self):
        """
        :return: workflow spec package
        """
        # FIXME: this is a very ugly workaround
        if isinstance(self.WORKFLOW_DIRECTORY, (str, unicode)):
            wfdir = self.WORKFLOW_DIRECTORY
        else:
            wfdir = self.WORKFLOW_DIRECTORY[0]
        # path = "{}/{}.zip".format(wfdir, self.current.workflow_name)
        # return open(path)
        path = "{}/{}.bpmn".format(wfdir, self.current.workflow_name)
        return BpmnSerializer().deserialize_workflow_spec(
            InMemoryPackager.package_in_memory(self.current.workflow_name, path))

    def serialize_workflow(self):
        # return self.workflow.serialize(serializer=DictionarySerializer())
        self.workflow.refresh_waiting_tasks()
        return CompactWorkflowSerializer().serialize_workflow(self.workflow, include_spec=False)


    def _save_workflow(self):
        self.save_workflow(self.current.workflow_name, self.serialize_workflow())

    def save_workflow(self, workflow_name, serilized_workflow_instance):
        """
        override this with your own persisntence method.
        :return:
        """

    def load_workflow(self, workflow_name):
        """
        override this method to load the previously
        saved workflow instance

        :return: serialized workflow instance

        """
        return ''

    def set_current(self, **kwargs):
        """
        workflow_name should be given in kwargs
        :param kwargs:
        :return:
        """
        self.current.update(kwargs)
        if 'task' in kwargs:
            task = kwargs['task']
            self.current.task_type = task.task_spec.__class__.__name__
            self.current.spec = task.task_spec
            self.current.name = task.get_name()

    def complete_current_task(self):
        self.workflow.complete_task_from_id(self.current.task.id)

    def run(self):
        ready_tasks = self.workflow.get_tasks(state=Task.READY)
        if ready_tasks:
            for task in ready_tasks:
                self.set_current(task=task)
                # print("TASK >> %s" % self.current.name, self.current.task.data, "TYPE", self.current.task_type)
                # self.process_activities()

                # self.process_activities()
                if hasattr(self.current.spec, 'service_class'):
                    self.run_activity(self.current.spec.service_class)

                self.complete_current_task()
            if not self.current.task_type.startswith('Start'):
                self._save_workflow()
        self.cleanup()
        if self.current.task_type != 'UserTask' and not self.current.task_type.startswith('End'):
            self.run()

    def run_activity(self, activity):
        """

        :param activity:
        :return:
        """
        if activity not in self.activities:
            mod_parts = activity.split('.')
            module = ".".join([self.ACTIVITY_MODULES_PATH] + mod_parts[:-1])
            method = mod_parts[-1]
            self.activities[activity] = getattr(import_module(module), method)
        self.activities[activity](self.current)

    # def process_activities(self):
    #     if 'activities' in self.current.spec.data:
    #         for cb in self.current.spec.data.activities:
    #             self.run_activity(cb)

    def cleanup(self):
        """
        this method will be called after each run cycle
        override this if you need some codes to be called after WF engine finished it's tasks and activities
        :return: None
        """
        pass
