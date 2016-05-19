# -*-  coding: utf-8 -*-
"""
Zengine's engine!
"""
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from __future__ import print_function, absolute_import, division
from __future__ import division

import importlib
import traceback
from io import BytesIO
import os, sys
from uuid import uuid4
from SpiffWorkflow.bpmn.BpmnWorkflow import BpmnWorkflow
from SpiffWorkflow.bpmn.storage.BpmnSerializer import BpmnSerializer
from SpiffWorkflow.bpmn.storage.CompactWorkflowSerializer import \
    CompactWorkflowSerializer
from SpiffWorkflow import Task
from SpiffWorkflow.specs import WorkflowSpec
from SpiffWorkflow.bpmn.storage.Packager import Packager
from beaker.session import Session
import lazy_object_proxy

from zengine.auth.permissions import PERM_REQ_TASK_TYPES
from zengine.client_queue import ClientQueue
from zengine.notifications import Notify

from zengine import signals
from pyoko.lib.utils import get_object_from_path, lazy_property
from pyoko.model import super_context, model_registry
from zengine.config import settings
from zengine.lib.cache import WFCache
from zengine.lib.camunda_parser import CamundaBMPNParser
from zengine.lib.exceptions import HTTPError
from zengine.log import log

DEFAULT_LANE_CHANGE_MSG = {
    'title': settings.MESSAGES['lane_change_message_title'],
    'body': settings.MESSAGES['lane_change_message_body'],
}


# crud_view = CrudView()


class InMemoryPackager(Packager):
    """
    Creates spiff's wf packages on the fly.
    """
    PARSER_CLASS = CamundaBMPNParser

    @classmethod
    def package_in_memory(cls, workflow_name, workflow_files):
        """
        Generates wf packages from workflow diagrams.

        Args:
            workflow_name: Name of wf
            workflow_files:  Diagram  file.

        Returns:
            Workflow package (file like) object
        """
        s = BytesIO()
        p = cls(s, workflow_name, meta_data=[])
        p.add_bpmn_files_by_glob(workflow_files)
        p.create_package()
        return s.getvalue()


class Current(object):
    """
    This object holds the whole state of the app for passing to view methods (views/tasks)

    :type spec: WorkflowSpec | None
    :type session: Session | None
    """

    def __init__(self, **kwargs):

        self.task_data = {'cmd': None}
        self.session = {}
        self.headers = {}
        self.input = {}  # when we want to use engine functions independently,
        self.output = {}  # we need to create a fake current object
        try:
            self.session = kwargs['session']
            self.input = kwargs['input']
        except KeyError:
            self.request = kwargs.pop('request', {})
            self.response = kwargs.pop('response', {})
            if 'env' in self.request:
                self.session = self.request.env['session']
                self.input = self.request.context['data']
                self.output = self.request.context['result']

        self.remote_addr = None
        self.user_id = self.session.get('user_id')
        self.role_id = self.session.get('role_id')

        self.lang_code = self.input.get('lang_code', settings.DEFAULT_LANG)
        self.log = log
        self.pool = {}
        AuthBackend = get_object_from_path(settings.AUTH_BACKEND)
        self.auth = lazy_object_proxy.Proxy(lambda: AuthBackend(self))
        self.user = lazy_object_proxy.Proxy(lambda: self.auth.get_user())
        self.role = lazy_object_proxy.Proxy(lambda: self.auth.get_role())
        log.debug("\n\nINPUT DATA: %s" % self.input)
        self.permissions = []

    @lazy_property
    def msg_cache(self):
        """
        A lazy proxy for Notify object.

        Returns: Notify
        """
        return Notify(self.user_id)

    @lazy_property
    def client_queue(self):
        """
        A lazy proxy for ClientQueue object.

        Returns: ClientQueue
        """
        return ClientQueue(self.user_id, self.session.key)

    def write_output(self, msg, json_msg=None):
        """
        Write to client without waiting to return of the view method

        Args:
            msg: Any JSON serializable object
            json_msg: JSON string
        """
        return self.client_queue.send_to_queue(msg, json_msg)

    def set_message(self, title, msg, typ, url=None):
        """
        Sets user notification message.
        See :attr:`~zengine.notifications.Notify` for details.

        Args:
            title: Msg. title
            msg:  Msg. text
            typ: Msg. type
            url: Additional URL (if exists)

        Returns:
            Message ID.
        """
        return self.msg_cache.set_message(title=title, msg=msg, typ=typ, url=url)

    @lazy_property
    def is_auth(self):
        """
        A property that indicates if current user is logged in or not.

        Returns:
            Boolean.
        """
        if self.user_id is None:
            self.user_id = self.session.get('user_id')
        return bool(self.user_id)

    def has_permission(self, perm):
        """
        Checks if current user (or role) has the given permission.

        Args:
            perm: Permmission code or object.
             Depends on the :attr:`~zengine.auth.auth_backend.AuthBackend` implementation.

        Returns:
            Boolean.
        """
        return self.user.superuser or self.auth.has_permission(perm)

    def get_permissions(self):
        """
        Returns permission objects.

        Returns:
            Permission objects or codes.
            Depends on the :attr:`~zengine.auth.auth_backend.AuthBackend` implementation.
        """
        return self.auth.get_permissions()

    def msg_box(self, msg, title=None, typ='info'):
        """
        Create a message box

        :param str msg:
        :param str title:
        :param str typ: 'info', 'error', 'warning'
        """
        self.output['msgbox'] = {'type': typ, "title": title or msg[:20],
                                 "msg": msg}


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
        self.flow_enabled = True
        self.task_name = ''
        self.activity = ''
        self.lane_permissions = []
        self.lane_relations = ''
        self.old_lane = ''
        self.lane_owners = None
        self.lane_name = ''

        if 'token' in self.input:
            self.token = self.input['token']
            # log.info("TOKEN iNCOMiNG: %s " % self.token)
            self.new_token = False
        else:
            self.token = uuid4().hex
            self.new_token = True
            # log.info("TOKEN NEW: %s " % self.token)

        self.wfcache = WFCache(self.token)
        # log.debug("\n\nWF_CACHE: %s" % self.wfcache.get())
        self.set_client_cmds()

    def sendoff_current_user(self):
        """
        Tell current user that s/he finished it's job for now.
        We'll notify if workflow arrives again to his/her WF Lane.
        """
        msgs = self.task_data.get('LANE_CHANGE_MSG', DEFAULT_LANE_CHANGE_MSG)
        self.msg_box(title=msgs['title'], msg=msgs['body'])

    def invite_other_parties(self, possible_owners):
        """
        Invites the next lane's (possible) owner(s) to participate
        """
        signals.lane_user_change.send(sender=self,
                                      current=self,
                                      old_lane=self.old_lane,
                                      possible_owners=possible_owners
                                      )

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
            self.lane_auto_sendoff = 'False' not in lane_data.get('auto_sendoff', '')
            self.lane_auto_invite = 'False' not in lane_data.get('auto_invite', '')

    def get_wf_url(self):
        """
        Returns:
            Relative URL for the current workflow.
        """
        return "#/%s/%s" % (self.workflow_name, self.token)

    def _update_task(self, task):
        """
        Assigns current task step to self.task
        then updates the task's data with self.task_data

        Args:
            task: Task object.
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

        filters = self.input.get('filters', {})

        try:
            if isinstance(filters, dict):
                # this is the new form, others will be removed when ui be ready
                self.task_data['object_id'] = filters.get('object_id')['values'][0]
            elif filters[0]['field'] == 'object_id':
                self.task_data['object_id'] = filters[0]['values'][0]
        except:
            if 'object_id' in self.input:
                self.task_data['object_id'] = self.input.get('object_id')


class ZEngine(object):
    """
    Workflow Engine Class

    This object handles following jobs;

    - Loading of BPMN workflow diagrams,
    - Iteration of task steps,
    - Importing and calling view and service tasks of task steps.
    - Caching and reloading of workflow states between steps.

    .. code-block:: python

        wf_engine = ZEngine()
        wf_engine.start_engine(request=request_object,
                               response=response_object,
                               workflow_name=wf_name)
        wf_engine.run()

    """

    def __init__(self):
        self.use_compact_serializer = True
        # self.current = None
        self.wf_activities = {}
        self.workflow = BpmnWorkflow
        self.workflow_spec_cache = {}
        self.workflow_spec = WorkflowSpec()
        self.user_model = get_object_from_path(settings.USER_MODEL)
        self.permission_model = get_object_from_path(settings.PERMISSION_MODEL)
        self.role_model = get_object_from_path(settings.ROLE_MODEL)

    def save_workflow_to_cache(self, wf_name, serialized_wf_instance):
        """
        If we aren't come to the end of the wf,
        saves the wf state and task_data to cache

        Task_data items that starts with underscore "_" are treated as
         local and does not passed to subsequent task steps.
        """
        if self.current.task_name.startswith('End'):
            self.current.wfcache.delete()
            self.current.log.info("Delete WFCache: %s %s" % (self.current.workflow_name,
                                                             self.current.token))
        else:
            # self.current.task_data['flow'] = None
            task_data = self.current.task_data.copy()
            for k, v in list(task_data.items()):
                if k.startswith('_'):
                    del task_data[k]
            if 'cmd' in task_data:
                del task_data['cmd']
            wf_cache = {'wf_state': serialized_wf_instance, 'data': task_data,}
            if self.current.lane_name:
                self.current.pool[self.current.lane_name] = self.current.role.key
            wf_cache['pool'] = self.current.pool
            self.current.wfcache.set(wf_cache)

    def get_pool_context(self):
        # TODO: Add in-process caching
        """
        Builds context for the WF pool.

        Returns:
            Context dict.
        """
        context = {self.current.lane_name: self.current.role, 'self': self.current.role}
        if self.current.lane_owners:
            model_name = self.current.lane_owners.split('.')[0]
            context[model_name] = model_registry.get_model(model_name)
        for lane_name, role_id in self.current.pool.items():
            if role_id:
                context[lane_name] = lazy_object_proxy.Proxy(
                    lambda: self.role_model(super_context).objects.get(role_id))
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
        # gets the serialized wf data from cache and deserializes it
        serialized_wf = self.load_workflow_from_cache()
        if serialized_wf:
            return self.deserialize_workflow(serialized_wf)

    def deserialize_workflow(self, serialized_wf):
        """
        Creates WF object instance from given state data.

        Args:
            serialized_wf: WF state data.

        Returns:
            BpmnWorkflow instance.
        """
        return CompactWorkflowSerializer().deserialize_workflow(serialized_wf,
                                                                workflow_spec=self.workflow_spec)

    def serialize_workflow(self):
        """
        Serializes the current WF.

        Returns:
            WF state data.
        """
        self.workflow.refresh_waiting_tasks()
        return CompactWorkflowSerializer().serialize_workflow(self.workflow,
                                                              include_spec=False)

    def create_workflow(self):
        """
        Creates WF instance for current WF spec.
        Returns:
            BpmnWorkflow
        """
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
        Tries to find the path of the workflow diagram file
        in `WORKFLOW_PACKAGES_PATHS`.

        Returns:
            Path of the workflow spec file (BPMN diagram)
        """
        for pth in settings.WORKFLOW_PACKAGES_PATHS:
            path = "%s/%s.bpmn" % (pth, self.current.workflow_name)
            if os.path.exists(path):
                return path
        err_msg = "BPMN file cannot found: %s" % self.current.workflow_name
        log.error(err_msg)
        raise RuntimeError(err_msg)

    def get_worfklow_spec(self):
        """
        Generates and caches the workflow spec package from
        BPMN diagrams that read from disk

        Returns:
            SpiffWorkflow Spec object.
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
        Calls the real save method if we pass the beggining of the wf
        """
        if not self.current.task_type.startswith('Start'):
            self.save_workflow_to_cache(self.current.workflow_name, self.serialize_workflow())

    def start_engine(self, **kwargs):
        """
        Initializes the workflow with given request, response objects and diagram name.

        Args:
            request: Falcon Request object.
            response: Falcon Response object.
            workflow_name (str): Name of workflow diagram without ".bpmn" suffix.
             File must be placed under one of configured :py:attr:`~zengine.settings.WORKFLOW_PACKAGES_PATHS`

        """
        self.current = WFCurrent(**kwargs)
        self.check_for_authentication()
        self.check_for_permission()
        self.workflow = self.load_or_create_workflow()
        log_msg = ("\n\n::::::::::: ENGINE STARTED :::::::::::\n"
                   "\tWF: %s (Possible) TASK:%s\n"
                   "\tCMD:%s\n"
                   "\tSUBCMD:%s" % (
                       self.workflow.name,
                       self.workflow.get_tasks(Task.READY),
                       self.current.input.get('cmd'), self.current.input.get('subcmd')))
        log.debug(log_msg)
        sys._zops_wf_state_log = log_msg
        self.current.workflow = self.workflow

    def generate_wf_state_log(self):
        """
        Logs the state of workflow and content of task_data.
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
        output += "\n\tLANE: %s" % self.current.lane_name
        output += "\n\tTOKEN: %s" % self.current.token
        sys._zops_wf_state_log = output
        return output

    def log_wf_state(self):
        log.debug(self.generate_wf_state_log() + "\n= = = = = =\n")

    def run(self):
        """
        Main loop of the workflow engine

        - Updates ::class:`~WFCurrent` object.
        - Checks for Permissions.
        - Activates all READY tasks.
        - Runs referenced activities (method calls).
        - Saves WF states.
        - Stops if current task is a UserTask or EndTask.
        - Deletes state object if we finish the WF.

        """
        # FIXME: raise if first task after line change isn't a UserTask
        # actually this check should be done at parser
        while (self.current.flow_enabled and
                       self.current.task_type != 'UserTask' and not
        self.current.task_type.startswith('End')):
            for task in self.workflow.get_tasks(state=Task.READY):
                self.current.old_lane = self.current.lane_name
                self.current._update_task(task)
                self.check_for_permission()
                self.check_for_lane_permission()
                self.log_wf_state()
                self.run_activity()
                self.parse_workflow_messages()
                self.workflow.complete_task_from_id(self.current.task.id)
                self._save_workflow()

        self.current.output['token'] = self.current.token

        # look for incoming ready task(s)
        for task in self.workflow.get_tasks(state=Task.READY):
            self.current._update_task(task)
            self.catch_lane_change()
            self.handle_wf_finalization()

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
                    self.current.sendoff_current_user()
                    self.current.flow_enabled = False
                    if self.current.lane_auto_invite:
                        self.current.invite_other_parties(self._get_possible_lane_owners())
            self.current.old_lane = self.current.lane_name

    def parse_workflow_messages(self):
        """
        Transmits client message that defined in
        a workflow task's inputOutput extension

       .. code-block:: xml

            <bpmn2:extensionElements>
            <camunda:inputOutput>
            <camunda:inputParameter name="client_message">
            <camunda:map>
              <camunda:entry key="title">Teşekkürler</camunda:entry>
              <camunda:entry key="body">İşlem Başarılı</camunda:entry>
              <camunda:entry key="type">info</camunda:entry>
            </camunda:map>
            </camunda:inputParameter>
            </camunda:inputOutput>
            </bpmn2:extensionElements>

        """
        if 'client_message' in self.current.spec.data:
            m = self.current.spec.data['client_message']
            self.current.msg_box(title=m.get('title'),
                                 msg=m.get('body'),
                                 typ=m.get('type', 'info'))

    def _get_possible_lane_owners(self):
        if self.current.lane_owners:
            return eval(self.current.lane_owners, self.get_pool_context())
        else:
            users = set()
            for perm in self.current.lane_permissions:
                users.update(self.permission_model.objects.get(perm).get_permitted_users())
            return list(users)

    def run_activity(self):
        """
        runs the method that referenced from current task
        """
        activity = self.current.activity
        if activity:
            if activity not in self.wf_activities:
                self._load_activity(activity)
            self.current.log.debug(
                "Calling Activity %s from %s" % (activity, self.wf_activities[activity]))
            self.wf_activities[self.current.activity](self.current)

    def _import_object(self, path, look_for_cls_method):
        """
        Imports the module that contains the referenced method.

        Args:
            path: python path of class/function
            look_for_cls_method (bool): If True, treat the last part of path as class method.

        Returns:
            Tuple. (class object, class name, method to be called)

        """
        last_nth = 2 if look_for_cls_method else 1
        path = path.split('.')
        module_path = '.'.join(path[:-last_nth])
        class_name = path[-last_nth]
        module = importlib.import_module(module_path)
        if look_for_cls_method and path[-last_nth:][0] == path[-last_nth]:
            class_method = path[-last_nth:][1]
        else:
            class_method = None
        return getattr(module, class_name), class_name, class_method

    def _load_activity(self, activity):
        """
        Iterates trough the all enabled `~zengine.settings.ACTIVITY_MODULES_IMPORT_PATHS` to find the given path.
        """
        fpths = []
        full_path = ''
        errors = []
        paths = settings.ACTIVITY_MODULES_IMPORT_PATHS
        number_of_paths = len(paths)
        for index_no in range(number_of_paths):
            full_path = "%s.%s" % (paths[index_no], activity)
            for look4kls in (0, 1):
                try:
                    self.current.log.info("try to load from %s[%s]" % (full_path, look4kls))
                    kls, cls_name, cls_method = self._import_object(full_path, look4kls)
                    if cls_method:
                        self.current.log.info("WILLCall %s(current).%s()" % (kls, cls_method))
                        self.wf_activities[activity] = lambda crnt: getattr(kls(crnt), cls_method)()
                    else:
                        self.wf_activities[activity] = kls
                    return
                except (ImportError, AttributeError):
                    fpths.append(full_path)
                    errmsg = "{activity} not found under these paths:\n\n >>> {paths} \n\n" \
                             "Error Messages:\n {errors}"
                    errors.append("\n========================================================>\n"
                                  "| PATH | %s"
                                  "\n========================================================>\n\n"
                                  "%s" % (full_path, traceback.format_exc()))
                    assert index_no != number_of_paths - 1, errmsg.format(activity=activity,
                                                                          paths='\n >>> '.join(
                                                                              set(fpths)),
                                                                          errors='\n\n'.join(errors)
                                                                          )
                except:
                    self.current.log.exception("Cannot found the %s" % activity)

    def check_for_authentication(self):
        """
        Checks current workflow against :py:data:`~zengine.settings.ANONYMOUS_WORKFLOWS` list.

        Raises:
            HTTPUnauthorized: if WF needs an authenticated user and current user isn't.
        """
        auth_required = self.current.workflow_name not in settings.ANONYMOUS_WORKFLOWS
        if auth_required and not self.current.is_auth:
            self.current.log.debug("LOGIN REQUIRED:::: %s" % self.current.workflow_name)
            raise HTTPError(401, "Login required for %s" % self.current.workflow_name)

    def check_for_lane_permission(self):
        """
        One or more permissions can be associated with a lane
        of a workflow. In a similar way, a lane can be
        restricted with relation to other lanes of the workflow.

        This method called on lane changes and checks user has
        required permissions and relations.

        Raises:
             HTTPForbidden: if the current user hasn't got the
              required permissions and proper relations

        """
        # TODO: Cache lane_data in app memory
        if self.current.lane_permissions:
            log.debug("HAS LANE PERMS: %s" % self.current.lane_permissions)
            for perm in self.current.lane_permissions:
                if not self.current.has_permission(perm):
                    raise HTTPError(403, "You don't have required lane permission: %s" % perm)

        if self.current.lane_relations:
            context = self.get_pool_context()
            log.debug("HAS LANE RELS: %s" % self.current.lane_relations)
            try:
                cond_result = eval(self.current.lane_relations, context)
            except:
                log.exception("CONDITION EVAL ERROR : %s || %s" % (
                    self.current.lane_relations, context))
                raise
            if not cond_result:
                log.debug("LANE RELATION ERR: %s %s" % (self.current.lane_relations, context))
                raise HTTPError(403, "You aren't qualified for this lane: %s" %
                                self.current.lane_relations)

    def check_for_permission(self):
        # TODO: Works but not beautiful, needs review!
        """
        Checks if current user (or role) has the required permission
        for current workflow step.

        Raises:
            HTTPError: if user doesn't have required permissions.
        """
        if self.current.task:
            permission = "%s.%s" % (self.current.workflow_name, self.current.task_name)
        else:
            permission = self.current.workflow_name
        log.debug("CHECK PERM: %s" % permission)
        if (self.current.task_type not in PERM_REQ_TASK_TYPES or
                permission.startswith(
                    tuple(settings.ANONYMOUS_WORKFLOWS))):  # FIXME:needs hardening
            return
        log.debug("REQUIRE PERM: %s" % permission)
        if not self.current.has_permission(permission):
            raise HTTPError(403, "You don't have required permission: %s" % permission)

    def handle_wf_finalization(self):
        """
        Removes the ``token`` key from ``current.output`` if WF is over.
        """
        if ((self.current.flow_enabled or self.current.task_type.startswith('End')) and
                    'token' in self.current.output):
            del self.current.output['token']
