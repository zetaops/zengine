# -*-  coding: utf-8 -*-
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

from importlib import import_module
import os.path
from SpiffWorkflow.bpmn.BpmnWorkflow import BpmnWorkflow
from SpiffWorkflow.bpmn.storage.BpmnSerializer import BpmnSerializer
from SpiffWorkflow import Task
from SpiffWorkflow.specs import WorkflowSpec
from SpiffWorkflow.storage import DictionarySerializer
from utils import DotDict


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
        serialized_wf = self.load_workflow(self.workflow_name)
        self.workflow = BpmnWorkflow.deserialize(DictionarySerializer(), serialized_wf)

    def create_workflow(self):
        wf_pkg_file = self.get_worfklow_spec()
        self.workflow_spec = BpmnSerializer().deserialize_workflow_spec(wf_pkg_file)
        self.workflow = BpmnWorkflow(self.workflow_spec)

    def load_or_create_workflow(self):
        """
        Tries to load the previously serialized (and saved) workflow
        Creates a new one if it can't
        """
        self.workflow = self.load_workflow(self.current.workflow_name) or self.create_workflow()

    def get_worfklow_spec(self):
        """
        :return: workflow spec package
        """
        path = "{}/{}.zip".format(self.WORKFLOW_DIRECTORY, self.current.workflow_name)
        return open(path)

    def serialize_workflow(self):
        return self.workflow.serialize(serializer=DictionarySerializer())

    def _save_workflow(self):
        self.save_workflow(self.current.workflow_name, self.serialize_workflow())

    def save_workflow(self, workflow_name, serilized_workflow_instance):
        """
        implement this method with your own persisntence method.
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
        if 'task' in self.current:
            # TODO: look for a better way for getting the task type
            self.current.type = str(self.current.task).split('(')[1].split(')')[0]
            self.current.spec = self.current.task.task_spec
            self.current.name = self.current.task.get_name()

    def complete_current_task(self):
        self.workflow.complete_task_from_id(self.current.task.id)

    def run(self):
        ready_tasks = self.workflow.get_tasks(state=Task.READY)
        if ready_tasks:
            for task in ready_tasks:
                self.set_current(task=task)
                print("TASK >> %s" % self.current.name, self.current.task.data)
                self.process_activities()
                self.complete_current_task()
            self.save_workflow()
        self.cleanup()

    def run_activity(self, activity):
        """

        :param activity:
        :return:
        """
        if activity not in self.activities:
            mod_parts = activity.split('.')
            module = "%s.%s" % (self.ACTIVITY_MODULES_PATH, mod_parts[:-1])
            method = mod_parts[-1]
            self.activities[activity] = getattr(import_module(module), method)
        self.activities[activity](self.current)

    def process_activities(self):
        if 'activities' in self.current.spec.data:
            for cb in self.current.spec.data.callbacks:
                self.run_activity(cb)

    def cleanup(self):
        """
        this method will be called after each run cycle
        override this if you need some codes to be called after WF engine finished it's tasks  and activities
        :return: None
        """
        pass
