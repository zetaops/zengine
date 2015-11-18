# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from __future__ import print_function, absolute_import, division
from __future__ import division
from io import BytesIO
import os
from uuid import uuid4
from SpiffWorkflow.bpmn.BpmnWorkflow import BpmnWorkflow
from SpiffWorkflow.bpmn.storage.BpmnSerializer import BpmnSerializer
from SpiffWorkflow.bpmn.storage.CompactWorkflowSerializer import \
    CompactWorkflowSerializer
from SpiffWorkflow import Task
from SpiffWorkflow.specs import WorkflowSpec
from SpiffWorkflow.bpmn.storage.Packager import Packager
from beaker.session import Session
from falcon import Request, Response
import falcon
import lazy_object_proxy
from zengine.notifications import Notify

from zengine import signals
from pyoko.lib.utils import get_object_from_path
from pyoko.model import super_context, model_registry
from zengine.config import settings, AuthBackend
from zengine.lib.cache import WFCache
from zengine.lib.camunda_parser import CamundaBMPNParser
from zengine.lib.exceptions import ZengineError
from zengine.log import log
from zengine.auth.permissions import NO_PERM_TASKS_TYPES
from zengine.views.crud import CrudView

crud_view = CrudView()

class InMemoryPackager(Packager):
    PARSER_CLASS = CamundaBMPNParser

    @classmethod
    def package_in_memory(cls, workflow_name, workflow_files):
        s = BytesIO()
        p = cls(s, workflow_name, meta_data=[])
        p.add_bpmn_files_by_glob(workflow_files)
        p.create_package()
        return s.getvalue()


class Current(object):
    """
    This object holds the whole state of the app for passing to view methods (views/tasks)

    :type response: Response | None
    :type request: Request | None
    :type spec: WorkflowSpec | None
    :type session: Session | None
    """

    def __init__(self, **kwargs):
        self.task_data = {'cmd': None}
        self.request = kwargs.pop('request', {})
        self.response = kwargs.pop('response', {})
        try:
            self.session = self.request.env['session']
            self.input = self.request.context['data']
            self.output = self.request.context['result']
            self.user_id = self.session.get('user_id')
        except AttributeError:
            # when we want to use engine functions independently,
            # we need to create a fake current object
            self.session = {}
            self.input = {}
            self.output = {}
            self.user_id = None

        self.lang_code = self.input.get('lang_code', settings.DEFAULT_LANG)
        self.log = log
        self.pool = {}
        self.auth = lazy_object_proxy.Proxy(lambda: AuthBackend(self))
        self.user = lazy_object_proxy.Proxy(lambda: self.auth.get_user())

        self.msg_cache = Notify(self.user_id)
        log.debug("\n\nINPUT DATA: %s" % self.input)
        self.permissions = []

    def set_message(self, title, msg, typ, url=None):
        self.msg_cache.set_message(
            {'title': title, 'body': msg, 'type': typ, 'url': url, 'id': uuid4().hex})

    @property
    def is_auth(self):
        if self.user_id is None:
            self.user_id = self.session.get('user_id', '')
        return bool(self.user_id)

    def has_permission(self, perm):
        return self.user.superuser or self.auth.has_permission(perm)

    def get_permissions(self):
        return self.auth.get_permissions()


class WFCurrent(Current):
    """
    Workflow specific version of Current object
    """

    def __init__(self, **kwargs):
        super(WFCurrent, self).__init__(**kwargs)
        self.workflow_name = kwargs.pop('workflow_name', '')
        self.spec = None
        self.workflow = None
        self.task_type = ''
        self.task = None
        self.pool = {}
        self.task_name = ''
        self.activity = ''
        self.lane_permissions = []
        self.lane_relations = ''
        self.old_lane = ''
        self.lane_owners = None
        self.lane_name = ''

        if 'token' in self.input:
            self.token = self.input['token']
            log.info("TOKEN iNCOMiNG: %s " % self.token)
            self.new_token = False
        else:
            self.token = uuid4().hex
            self.new_token = True
            log.info("TOKEN NEW: %s " % self.token)

        self.wfcache = WFCache(self.token)
        log.debug("\n\nWF_CACHE: %s" % self.wfcache.get())
        self.set_client_cmds()

    def _set_lane_data(self):
        # TODO: Cache lane_data in process
        if 'lane_data' in self.spec.data:
            self.lane_name = self.spec.lane
            lane_data = self.spec.data['lane_data']
            if 'permissions' in lane_data:
                self.lane_permissions = lane_data['permissions'].split(',')
            if 'relations' in lane_data:
                self.lane_relations = lane_data['relations']
            if 'owners' in lane_data:
                self.lane_owners = lane_data['owners']

    def get_wf_url(self):
        return "#/%s/%s" % (self.workflow_name, self.token)

    def _update_task(self, task):
        """
        assigns current task step to self.task
        then updates the task's data with self.task_data
        """
        self.task = task
        self.task.data.update(self.task_data)
        self.task_type = task.task_spec.__class__.__name__
        self.spec = task.task_spec
        self.task_name = task.get_name()
        self.activity = getattr(self.spec, 'service_class', '')
        self._set_lane_data()

    def set_client_cmds(self):
        """
        This is method automatically called on each request and
        updates "object_id", "cmd" and "flow"  client variables
        from current.input.

        "flow" and "object_id" variables will always exists in the
        task_data so app developers can safely check for their
        values in workflows.
        Their values will be reset to None if they not exists
        in the current input data set.

        On the other side, if there isn't a "cmd" in the current.input
        cmd will be removed from task_data.

        """
        self.task_data['cmd'] = self.input.get('cmd')

        self.task_data['flow'] = self.input.get('flow')

        self.task_data['object_id'] = self.input.get('object_id')


class ZEngine(object):
    def __init__(self):
        self.use_compact_serializer = True
        # self.current = None
        self.workflow_methods = {'crud_view': crud_view}
        self.workflow = BpmnWorkflow
        self.workflow_spec_cache = {}
        self.workflow_spec = WorkflowSpec()
        self.user_model = get_object_from_path(settings.USER_MODEL)

    def save_workflow_to_cache(self, wf_name, serialized_wf_instance):
        """
        if we aren't come to the end of the wf,
        saves the wf state and task_data to cache

        task_data items that starts with underscore "_" are treated as
         local and does not passed to following task steps.
        """
        if self.current.task_name.startswith('End'):
            self.current.wfcache.delete()
        else:
            task_data = self.current.task_data.copy()
            for k, v in list(task_data.items()):
                if k.startswith('_'):
                    del task_data[k]
            if 'cmd' in task_data:
                del task_data['cmd']
            wf_cache = {'wf_state': serialized_wf_instance, 'data': task_data, }
            if self.current.lane_name:
                self.current.pool[self.current.lane_name] = self.current.user_id
            wf_cache['pool'] = self.current.pool
            self.current.wfcache.set(wf_cache)

    def get_pool_context(self):
        # TODO: Add in-process caching
        context = {self.current.lane_name: self.current.user, 'self': self.current.user}
        if self.current.lane_owners:
            model_name = self.current.lane_owners.split('.')[0]
            context[model_name] = model_registry.get_model(model_name).objects
        for lane_name, user_id in self.current.pool.items():
            if user_id:
                context[lane_name] = lazy_object_proxy.Proxy(
                    lambda: self.user_model(super_context).objects.get(user_id))
        return context

    def load_workflow_from_cache(self):
        """
        loads the serialized wf state and data from cache
        updates the self.current.task_data
        """
        if not self.current.new_token:
            wf_cache = self.current.wfcache.get()
            self.current.task_data = wf_cache['data']
            self.current.set_client_cmds()
            self.current.pool = wf_cache['pool']
            return wf_cache['wf_state']

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
        return BpmnWorkflow(self.workflow_spec)

    def load_or_create_workflow(self):
        """
        Tries to load the previously serialized (and saved) workflow
        Creates a new one if it can't
        """
        self.workflow_spec = self.get_worfklow_spec()
        return self._load_workflow() or self.create_workflow()
        # self.current.update(workflow=self.workflow)

    def find_workflow_path(self):
        """
        tries to find the path of the workflow diagram file
        in WORKFLOW_PACKAGES_PATHS
        :return: path of the workflow spec file (BPMN diagram)
        """
        for pth in settings.WORKFLOW_PACKAGES_PATHS:
            path = "%s/%s.bpmn" % (pth, self.current.workflow_name)
            if os.path.exists(path):
                return path
        err_msg = "BPMN file cannot found: %s" % self.current.workflow_name
        log.error(err_msg)
        raise RuntimeError(err_msg)

    def get_task_specs(self):
        return self.workflow.spec.task_specs

    def get_worfklow_spec(self):
        """
        generates and caches the workflow spec package from
        bpmn diagrams that read from disk

        :return: workflow spec package
        """
        # TODO: convert from in-process to redis based caching
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
            self.save_workflow_to_cache(self.current.workflow_name, self.serialize_workflow())

    def start_engine(self, **kwargs):
        self.current = WFCurrent(**kwargs)
        self.check_for_authentication()
        self.check_for_permission()
        self.workflow = self.load_or_create_workflow()
        log.debug("\n\n::::::::::: ENGINE STARTED :::::::::::\n"
                  "\tWF: %s (Possible) TASK:%s\n"
                  "\tCMD:%s\n"
                  "\tSUBCMD:%s" % (
                      self.workflow.name,
                      self.workflow.get_tasks(Task.READY),
                      self.current.input.get('cmd'), self.current.input.get('subcmd')))
        self.current.workflow = self.workflow

    def log_wf_state(self):
        """
        logging the state of the workflow and data
        """
        output = '\n- - - - - -\n'
        output += "WORKFLOW: %s ( %s )" % (self.current.workflow_name.upper(),
                                           self.current.workflow.name)

        output += "\nTASK: %s ( %s )\n" % (self.current.task_name, self.current.task_type)
        output += "DATA:"
        for k, v in self.current.task_data.items():
            if v:
                output += "\n\t%s: %s" % (k, v)
        output += "\nCURRENT:"
        output += "\n\tACTIVITY: %s" % self.current.activity
        output += "\n\tPOOL: %s" % self.current.pool
        output += "\n\tTOKEN: %s" % self.current.token
        log.debug(output + "\n= = = = = =\n")

    def run(self):
        """
        Main loop of the workflow engine
        Activates all READY tasks, calls their diagrams, saves wf state,
        Stops if current task is a UserTask or EndTask

        """
        # FIXME: raise if first task after line change isn't a UserTask
        while (self.current.task_type != 'UserTask' and
                   not self.current.task_type.startswith('End')):
            for task in self.workflow.get_tasks(state=Task.READY):
                self.current._update_task(task)
                self.check_for_permission()
                self.check_for_lane_permission()
                self.log_wf_state()
                self.run_activity()
                self.workflow.complete_task_from_id(self.current.task.id)
                self._save_workflow()
                self.catch_lane_change()
        self.current.output['token'] = self.current.token
        # look for incoming ready task(s)
        for task in self.workflow.get_tasks(state=Task.READY):
            self.current._update_task(task)
            self.catch_lane_change()

    def catch_lane_change(self):
        """
        trigger a lane_user_change signal if we switched to a new lane
        and new lane's user is different from current one
        """
        if self.current.lane_name:
            if self.current.old_lane and self.current.lane_name != self.current.old_lane:
                # if lane_name not found in pool or it's user different from the current(old) user
                if (self.current.lane_name not in self.current.pool or
                            self.current.pool[self.current.lane_name] != self.current.user_id):
                    # if self.current.lane_owners
                    possible_owners = eval(self.current.lane_owners, self.get_pool_context())
                    signals.lane_user_change.send(sender=self,
                                                  current=self.current,
                                                  old_lane=self.current.old_lane,
                                                  possible_owners=possible_owners
                                                  )
            self.current.old_lane = self.current.lane_name

    def run_activity(self):
        """
        imports, caches and calls the associated activity of the current task
        """
        activity = self.current.activity
        if activity:
            if activity not in self.workflow_methods:
                self._load_activity(activity)
            self.current.log.debug(
                "Calling Activity %s from %s" % (activity, self.workflow_methods[activity]))
            self.workflow_methods[self.current.activity](self.current)

    def _load_activity(self, activity):
        """
        imports, caches and calls the associated activity of the current task
        """
        errors = []
        full_path = ''
        paths = settings.ACTIVITY_MODULES_IMPORT_PATHS
        for activity_package in paths:
            try:
                full_path = "%s.%s" % (activity_package, activity)
                activity_object = get_object_from_path(full_path)
                if getattr(activity_object, '__base__', None) == CrudView:
                    activity_object = activity_object(self.current)
                self.workflow_methods[activity] = activity_object
                break
            except (ImportError, AttributeError):
                errors.append(full_path)
                number_of_paths = len(paths)
                index_no = paths.index(activity_package)
                if index_no + 1 == number_of_paths:
                    # raise if cant find the activity in the last path
                    err_msg = "{activity} not found under these paths: {paths}".format(
                        activity=activity, paths=errors)
                    raise ZengineError(err_msg)

    def check_for_authentication(self):
        """
        Checks current workflow against anonymous_workflows list,
        raises HTTPUnauthorized error when WF needs an authenticated user
        and current user isn't.
        """
        auth_required = self.current.workflow_name not in settings.ANONYMOUS_WORKFLOWS
        if auth_required and not self.current.is_auth:
            self.current.log.debug("LOGIN REQUIRED:::: %s" % self.current.workflow_name)
            raise falcon.HTTPUnauthorized("Login required", "")

    def check_for_lane_permission(self):
        """
        One or more permissions can be associated with a lane of a workflow.
        In a similar way, a lane can be restricted with relation to other lanes of the workflow.

        When this method called on lane changes, it checks if the current user has the required
         permissions and proper relations. Raises a HTTPForbidden error if it is not.

        """
        # TODO: Cache lane_data in app memory
        if self.current.lane_permissions:
            log.debug("HAS LANE PERMS: %s" % self.current.lane_permissions)
            for perm in self.current.lane_permissions:
                if not self.current.has_permission(perm):
                    raise falcon.HTTPForbidden("Permission denied",
                                               "You don't have required lane permission: %s" % perm)
        if self.current.lane_relations:
            context = self.get_pool_context()
            log.debug("HAS LANE RELS: %s" % self.current.lane_relations)
            if not eval(self.current.lane_relations, context):
                log.debug("LANE RELATION ERR: %s %s" % (self.current.lane_relations, context))
                raise falcon.HTTPForbidden(
                    "Permission denied",
                    "You aren't qualified for this lane: %s" % self.current.lane_relations)

    def check_for_permission(self):
        # TODO: Works but not beautiful, needs review!
        if self.current.task:
            permission = "%s.%s" % (self.current.workflow_name, self.current.task_name)
        else:
            permission = self.current.workflow_name
        log.debug("CHECK PERM: %s" % permission)
        if (self.current.task_type in NO_PERM_TASKS_TYPES or
                permission.startswith(tuple(settings.ANONYMOUS_WORKFLOWS))):
            return
        log.debug("REQUIRE PERM: %s" % permission)
        if not self.current.has_permission(permission):
            raise falcon.HTTPForbidden("Permission denied",
                                       "You don't have required permission: %s" % permission)
