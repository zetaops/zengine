# -*-  coding: utf-8 -*-
"""
ZEnging engine class
import, extend and override load_workflow and save_workflow methods

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
    WORKFLOW_DIRECTORY = ''
    ACTIVITY_MODULES_PATH = ''

    def __init__(self):

        self.current = DotDict()
        self.modules = {}
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
        self.workflow = self.load_workflow() or self.create_workflow()

    def get_worfklow_spec(self):
        """
        :return: workflow spec package
        """
        return open(os.path.join("{path}/{name}.zip".format(**{
            'path': self.WORKFLOW_DIRECTORY,
            'name': self.current.workflow_name})))

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

    def run_module_method(self, module_method):
        if module_method not in self.modules:
            mod_parts = module_method.split('.')
            module = "%s.%s" % (self.ACTIVITY_MODULES_PATH, mod_parts[:-1])
            method = mod_parts[-1]
            self.modules[module_method] = getattr(import_module(module), method)
        self.modules[module_method](self.current)

    def process_activities(self):
        if 'activities' in self.current.spec.data:
            for cb in self.current.spec.data.callbacks:
                self.run_module_method(cb)
