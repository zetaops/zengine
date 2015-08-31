# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from __future__ import print_function, absolute_import, division
from __future__ import division
import importlib
from io import BytesIO
from importlib import import_module
import os
from uuid import uuid4

from SpiffWorkflow.bpmn.BpmnWorkflow import BpmnWorkflow
from SpiffWorkflow.bpmn.storage.BpmnSerializer import BpmnSerializer
from SpiffWorkflow.bpmn.storage.CompactWorkflowSerializer import \
    CompactWorkflowSerializer
from SpiffWorkflow import Task
from SpiffWorkflow.specs import WorkflowSpec
from SpiffWorkflow.storage import DictionarySerializer
from SpiffWorkflow.bpmn.storage.Packager import Packager
from beaker.session import Session
from falcon import Request, Response
import falcon
import lazy_object_proxy
from zengine.config import settings, AuthBackend
from zengine.lib.cache import Cache, cache
from zengine.lib.camunda_parser import CamundaBMPNParser
from zengine.lib.utils import get_object_from_path
from zengine.log import getlogger
from zengine.lib.views import crud_view

log = getlogger()

ALLOWED_CLIENT_COMMANDS = ['edit', 'add', 'update', 'list', 'delete', 'do']


class InMemoryPackager(Packager):
    PARSER_CLASS = CamundaBMPNParser

    @classmethod
    def package_in_memory(cls, workflow_name, workflow_files):
        s = BytesIO()
        p = cls(s, workflow_name, meta_data=[])
        p.add_bpmn_files_by_glob(workflow_files)
        p.create_package()
        return s.getvalue()


class Condition(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return None

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self.__dict__)


class Current(object):
    """
    This object holds and passes the whole state of the app to task activites

    :type task: Task | None
    :type response: Response | None
    :type request: Request | None
    :type spec: WorkflowSpec | None
    :type workflow: Workflow | None
    :type session: Session | None
    """

    def __init__(self, **kwargs):
        self.workflow_name = kwargs.pop('workflow_name', '')
        self.request = kwargs.pop('request', None)
        self.response = kwargs.pop('response', None)
        self.session = self.request.env['session']
        self.spec = None
        self.user_id = None
        self.workflow = None
        self.task_type = ''
        self.task_data = {}
        self.task = None
        self.log = log
        self.name = ''
        self.activity = ''
        self.input = self.request.context['data']
        self.output = self.request.context['result']
        self.auth = lazy_object_proxy.Proxy(lambda: AuthBackend(self.session))
        self.user = lazy_object_proxy.Proxy(lambda: self.auth.get_user())

        if 'token' in self.input:
            self.token = self.input['token']
            log.info("TOKEN iNCOMiNG: %s " % self.token)
            self.new_token = False
        else:
            self.token = uuid4().hex
            self.new_token = True
            log.info("TOKEN NEW: %s " % self.token)

        self.wfcache = Cache(key=self.token, json=True)
        log.info("\n\nWFCACHE: %s" % self.wfcache.get())
        self.set_task_data()
        self.permissions = []

    @property
    def is_auth(self):
        if self.user_id is None:
            self.user_id = self.session.get('user_id', '')
        return bool(self.user_id)



    def has_permission(self, perm):
        return self.auth.has_permission(perm)

    def get_permissions(self):
        return self.auth.get_permissions()

    def update_task(self, task):
        """
        updates self.task with current task step
        then updates the task's data with self.task_data
        """
        self.task = task
        self.task.data.update(self.task_data)
        self.task_type = task.task_spec.__class__.__name__
        self.spec = task.task_spec
        self.name = task.get_name()
        self.activity = getattr(self.spec, 'service_class', '')

    def set_task_data(self, internal_cmd=None):
        """
        updates task data according to client input
        internal_cmd overrides client cmd if exists
        eihter way cmd should be one of ALLOWED_CLIENT_COMMANDS
        """
        if 'IS' not in self.task_data:
            self.task_data['IS'] = Condition()
        for cmd in ALLOWED_CLIENT_COMMANDS:
            self.task_data[cmd] = None
        # this cmd coming from inside of the app
        if internal_cmd and internal_cmd in ALLOWED_CLIENT_COMMANDS:
            self.task_data[internal_cmd] = True
            self.task_data['cmd'] = internal_cmd
        else:
            if 'cmd' in self.input and self.input['cmd'] in ALLOWED_CLIENT_COMMANDS:
                self.task_data[self.input['cmd']] = True
                self.task_data['cmd'] = self.input['cmd']
            else:
                self.task_data['cmd'] = None
        self.task_data['object_id'] = self.input.get('object_id', None)


class ZEngine(object):
    def __init__(self):
        self.use_compact_serializer = True
        self.current = None
        self.activities = {'crud_view': crud_view}
        self.workflow = BpmnWorkflow
        self.workflow_spec_cache = {}
        self.workflow_spec = WorkflowSpec()

    def save_workflow(self, wf_name, serialized_wf_instance):
        """
        if we aren't come to the end of the wf,
        saves the wf state and data to cache
        """
        if self.current.name.startswith('End'):
            self.current.wfcache.delete()
        else:
            task_data = self.current.task_data.copy()
            task_data['IS_srlzd'] = self.current.task_data['IS'].__dict__
            del task_data['IS']
            self.current.wfcache.set((serialized_wf_instance, task_data))

    def load_workflow_from_cache(self):
        """
        loads the serialized wf state and data from cache
        updates the self.current.task_data
        """
        if not self.current.new_token:
            serialized_workflow, task_data = self.current.wfcache.get()
            task_data['IS'] = Condition(**task_data.pop('IS_srlzd'))
            self.current.task_data = task_data
            self.current.set_task_data()
            return serialized_workflow

    def _load_workflow(self):
        """
        gets the serialized wf data from cache and deserializes it
        """
        serialized_wf = self.load_workflow_from_cache()
        if serialized_wf:
            return self.deserialize_workflow(serialized_wf)

    def deserialize_workflow(self, serialized_wf):
        return CompactWorkflowSerializer().deserialize_workflow(serialized_wf,
                                                              workflow_spec=self.workflow_spec)

    def serialize_workflow(self):
        self.workflow.refresh_waiting_tasks()
        return CompactWorkflowSerializer().serialize_workflow(self.workflow,
                                                              include_spec=False)

    def create_workflow(self):
        self.workflow_spec = self.get_worfklow_spec()
        return BpmnWorkflow(self.workflow_spec)

    def load_or_create_workflow(self):
        """
        Tries to load the previously serialized (and saved) workflow
        Creates a new one if it can't
        """
        return self._load_workflow() or self.create_workflow()
        # self.current.update(workflow=self.workflow)

    def find_workflow_path(self):
        """
        tries to find the path of the workflow diagram file.
        first looks to the defined WORKFLOW_PACKAGES_PATH,
        if it cannot be found there, fallbacks to zengine/workflows
        directory for default workflows that shipped with zengine

        :return: path of the workflow spec file (BPMN diagram)
        """
        path = "%s/%s.bpmn" % (settings.WORKFLOW_PACKAGES_PATH, self.current.workflow_name)
        if not os.path.exists(path):
            zengine_path = os.path.dirname(os.path.realpath(__file__))
            path = "%s/workflows/%s.bpmn" % (zengine_path, self.current.workflow_name)
            if not os.path.exists(path):
                raise RuntimeError("BPMN file cannot found: %s" % self.current.workflow_name)
        return path


    def get_worfklow_spec(self):
        """
        generates and caches the workflow spec package from
        bpmn diagrams that read from disk

        :return: workflow spec package
        """
        # TODO: convert from in-memory to redis based caching
        if self.current.workflow_name not in self.workflow_spec_cache:
            path = self.find_workflow_path()
            spec_package = InMemoryPackager.package_in_memory(self.current.workflow_name, path)
            spec = BpmnSerializer().deserialize_workflow_spec(spec_package)
            self.workflow_spec_cache[self.current.workflow_name] = spec
        return self.workflow_spec_cache[self.current.workflow_name]

    def _save_workflow(self):
        """
        calls the real save method if we pass the beggining of the wf
        """
        if not self.current.task_type.startswith('Start'):
            self.save_workflow(self.current.workflow_name, self.serialize_workflow())

    def start_engine(self, **kwargs):
        self.current = Current(**kwargs)
        self.check_for_authentication()
        log.info("::::::::::: ENGINE STARTED :::::::::::\n"
                 "\tCMD:%s\n"
                 "\tSUBCMD:%s" % (self.current.input.get('cmd'), self.current.input.get('subcmd')))
        self.workflow = self.load_or_create_workflow()
        self.current.workflow = self.workflow

    def log_wf_state(self):
        """
        logging the state of the workflow and data
        """
        output = '\n- - - - - -\n'
        output += "WORKFLOW: %s" % self.current.workflow_name.upper()

        output += "\nTASK: %s ( %s )\n" % (self.current.name, self.current.task_type)
        output += "DATA:"
        for k, v in self.current.task_data.items():
            if v:
                output += "\n\t%s: %s" % (k, v)
        output += "\nCURRENT:"
        output += "\n\tACTIVITY: %s" % self.current.activity
        output += "\n\tTOKEN: %s" % self.current.token
        log.info(output + "\n= = = = = =\n")

    def run(self):
        """
        main loop of the workflow engine
        runs all READY tasks, calls their activities, saves wf state,
        breaks if current task is a UserTask or EndTask
        """
        while self.current.task_type != 'UserTask' and not self.current.task_type.startswith('End'):
            for task in self.workflow.get_tasks(state=Task.READY):
                self.current.update_task(task)
                self.log_wf_state()
                self.run_activity()
                self.workflow.complete_task_from_id(self.current.task.id)
                self._save_workflow()
        self.current.output['token'] = self.current.token

    def run_activity(self):
        """
        imports, caches and calls the associated activity of the current task
        """
        if self.current.activity:
            if self.current.activity not in self.activities:
                for activity_package in settings.ACTIVITY_MODULES_IMPORT_PATHS:
                    try:
                        full_path = "%s.%s" % (activity_package, self.current.activity)
                        self.activities[self.current.activity] = get_object_from_path(full_path)
                        break
                    except:
                        number_of_paths = len(settings.ACTIVITY_MODULES_IMPORT_PATHS)
                        index_no = settings.ACTIVITY_MODULES_IMPORT_PATHS.index(activity_package)
                        if index_no + 1 == number_of_paths:
                            # raise if cant find the activity in the last path
                            raise
            self.activities[self.current.activity](self.current)

    def check_for_authentication(self):
        auth_required = self.current.workflow_name not in settings.ANONYMOUS_WORKFLOWS
        if auth_required and not self.current.is_auth:
            self.current.log.info("LOGIN REQUIRED:::: %s" % self.current.workflow_name)
            raise falcon.HTTPUnauthorized("Login required", "")

