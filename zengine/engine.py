# -*-  coding: utf-8 -*-
"""
Zengine's engine!
"""
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from __future__ import division
from __future__ import print_function, absolute_import, division

import importlib
import os
import sys
import traceback
import lazy_object_proxy
from SpiffWorkflow import Task
from SpiffWorkflow.bpmn.BpmnWorkflow import BpmnWorkflow
from SpiffWorkflow.bpmn.storage.CompactWorkflowSerializer import CompactWorkflowSerializer
from SpiffWorkflow.specs import WorkflowSpec
from datetime import datetime
from pyoko.lib.utils import get_object_from_path
from pyoko.model import super_context
from zengine.auth.permissions import PERM_REQ_TASK_TYPES
from zengine.config import settings
from zengine.current import WFCurrent
from zengine.lib.camunda_parser import ZopsSerializer
from zengine.lib.exceptions import HTTPError
from zengine.lib import translation
from zengine.log import log
from zengine.models import BPMNWorkflow, ObjectDoesNotExist
from zengine.models.workflow_manager import TaskInvitation, WFCache


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
        self.wf_state = {}
        self.workflow = BpmnWorkflow
        self.workflow_spec_cache = {}
        self.workflow_spec = WorkflowSpec()
        self.user_model = get_object_from_path(settings.USER_MODEL)
        self.permission_model = get_object_from_path(settings.PERMISSION_MODEL)
        self.role_model = get_object_from_path(settings.ROLE_MODEL)

    def are_we_in_subprocess(self):
        are_we = False
        if self.current.task:
            are_we = self.current.task.workflow.name != self.current.workflow.name
        self.current.log.debug("Are We in subprocess: %s" % are_we)
        return are_we

    def save_workflow_to_cache(self, serialized_wf_instance):
        """
        If we aren't come to the end of the wf,
        saves the wf state and task_data to cache

        Task_data items that starts with underscore "_" are treated as
         local and does not passed to subsequent task steps.
        """
        # self.current.task_data['flow'] = None
        task_data = self.current.task_data.copy()
        for k, v in list(task_data.items()):
            if k.startswith('_'):
                del task_data[k]
        if 'cmd' in task_data:
            del task_data['cmd']

        self.wf_state.update({'step': serialized_wf_instance,
                              'data': task_data,
                              'name': self.current.workflow_name,
                              'wf_id': self.workflow_spec.wf_id
                              })

        if self.current.lane_id:
            self.current.pool[self.current.lane_id] = self.current.role.key
        self.wf_state['pool'] = self.current.pool
        self.current.log.debug("POOL Content before WF Save: %s" % self.current.pool)
        self.current.wf_cache.save(self.wf_state)

    def get_pool_context(self):
        # TODO: Add in-process caching
        """
        Builds context for the WF pool.

        Returns:
            Context dict.
        """
        context = {self.current.lane_id: self.current.role, 'self': self.current.role}
        for lane_id, role_id in self.current.pool.items():
            if role_id:
                context[lane_id] = lazy_object_proxy.Proxy(
                    lambda: self.role_model(super_context).objects.get(role_id))
        return context

    def load_workflow_from_cache(self):
        """
        loads the serialized wf state and data from cache
        updates the self.current.task_data
        """
        if not self.current.new_token:
            self.wf_state = self.current.wf_cache.get(self.wf_state)
            self.current.task_data = self.wf_state['data']
            self.current.set_client_cmds()
            self.current.pool = self.wf_state['pool']
            return self.wf_state['step']

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
            # path = self.find_workflow_path()
            # spec_package = InMemoryPackager.package_in_memory(self.current.workflow_name, path)
            # spec = BpmnSerializer().deserialize_workflow_spec(spec_package)

            try:
                self.current.wf_object = BPMNWorkflow.objects.get(name=self.current.workflow_name)
            except ObjectDoesNotExist:
                self.current.wf_object = BPMNWorkflow.objects.get(name='not_found')
                self.current.task_data['non-existent-wf'] = self.current.workflow_name
                self.current.workflow_name = 'not_found'
            xml_content = self.current.wf_object.xml.body
            spec = ZopsSerializer().deserialize_workflow_spec(xml_content, self.current.workflow_name)

            spec.wf_id = self.current.wf_object.key
            self.workflow_spec_cache[self.current.workflow_name] = spec
        return self.workflow_spec_cache[self.current.workflow_name]

    def _save_or_delete_workflow(self):
        """
        Calls the real save method if we pass the beggining of the wf
        """
        if not self.current.task_type.startswith('Start'):
            if self.current.task_name.startswith('End') and not self.are_we_in_subprocess():
                self.wf_state['finished'] = True
                self.wf_state['finish_date'] = datetime.now().strftime(
                    settings.DATETIME_DEFAULT_FORMAT)

                if self.current.workflow_name not in settings.EPHEMERAL_WORKFLOWS and not \
                self.wf_state['in_external']:
                    wfi = WFCache(self.current).get_instance()
                    TaskInvitation.objects.filter(instance=wfi, role=self.current.role,
                                              wf_name=wfi.wf.name).delete()

                self.current.log.info("Delete WFCache: %s %s" % (self.current.workflow_name,
                                                                 self.current.token))
            self.save_workflow_to_cache(self.serialize_workflow())

    def start_engine(self, **kwargs):
        """
        Initializes the workflow with given request, response objects and diagram name.

        Args:
            session:
            input:
            workflow_name (str): Name of workflow diagram without ".bpmn" suffix.
             File must be placed under one of configured :py:attr:`~zengine.settings.WORKFLOW_PACKAGES_PATHS`

        """
        self.current = WFCurrent(**kwargs)
        self.wf_state = {'in_external': False, 'finished': False}
        if not self.current.new_token:
            self.wf_state = self.current.wf_cache.get(self.wf_state)
            self.current.workflow_name = self.wf_state['name']
            # if we have a pre-selected object to work with,
            # inserting it as current.input['id'] and task_data['object_id']
            if 'subject' in self.wf_state:
                self.current.input['id'] = self.wf_state['subject']
                self.current.task_data['object_id'] = self.wf_state['subject']
        self.check_for_authentication()
        self.check_for_permission()
        self.workflow = self.load_or_create_workflow()

        # if form data exists in input (user submitted)
        # put form data in wf task_data
        if 'form' in self.current.input:
            form = self.current.input['form']
            if 'form_name' in form:
                self.current.task_data[form['form_name']] = form

        # in wf diagram, if property is stated as init = True
        # demanded initial values are assigned and put to cache
        start_init_values = self.workflow_spec.wf_properties.get('init', 'False') == 'True'
        if start_init_values:
            WFInit = get_object_from_path(settings.WF_INITIAL_VALUES)()
            WFInit.assign_wf_initial_values(self.current)

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
        output += "\n\tIN EXTERNAL: %s" % self.wf_state['in_external']
        output += "\n\tLANE: %s" % self.current.lane_name
        output += "\n\tTOKEN: %s" % self.current.token
        sys._zops_wf_state_log = output
        return output

    def log_wf_state(self):
        log.debug(self.generate_wf_state_log() + "\n= = = = = =\n")

    def switch_from_external_to_main_wf(self):

        """
        Main workflow switcher.

        This method recreates main workflow from `main wf` dict which
        was set by external workflow swicther previously.

        """

        # in external assigned as True in switch_to_external_wf.
        # external_wf should finish EndEvent and it's name should be
        # also EndEvent for switching again to main wf.
        if self.wf_state['in_external'] and self.current.task_type == 'EndEvent' and \
                self.current.task_name == 'EndEvent':

            # main_wf information was copied in switch_to_external_wf and it takes this information.
            main_wf = self.wf_state['main_wf']

            # main_wf_name is assigned to current workflow name again.
            self.current.workflow_name = main_wf['name']

            # For external WF, check permission and authentication. But after cleaning current task.
            self._clear_current_task()

            # check for auth and perm. current task cleared, do against new workflow_name
            self.check_for_authentication()
            self.check_for_permission()

            # WF knowledge is taken for main wf.
            self.workflow_spec = self.get_worfklow_spec()

            # WF instance is started again where leave off.
            self.workflow = self.deserialize_workflow(main_wf['step'])

            # Current WF is this WF instance.
            self.current.workflow = self.workflow

            # in_external is assigned as False
            self.wf_state['in_external'] = False

            # finished is assigned as False, because still in progress.
            self.wf_state['finished'] = False

            # pool info of main_wf is assigned.
            self.wf_state['pool'] = main_wf['pool']
            self.current.pool = self.wf_state['pool']

            # With main_wf is executed.
            self.run()

    def switch_to_external_wf(self):
        """
        External workflow switcher.

        This method copies main workflow information into
        a temporary dict `main_wf` and makes external workflow
        acting as main workflow.

        """

        # External WF name should be stated at main wf diagram and type should be service task.
        if (self.current.task_type == 'ServiceTask' and
                self.current.task.task_spec.type == 'external'):

            log.debug("Entering to EXTERNAL WF")

            # Main wf information is copied to main_wf.
            main_wf = self.wf_state.copy()

            # workflow name from main wf diagram is assigned to current workflow name.
            # workflow name must be either in task_data with key 'external_wf' or in main diagram's
            # topic.
            self.current.workflow_name = self.current.task_data.pop('external_wf', False) or self.\
                current.task.task_spec.topic

            # For external WF, check permission and authentication. But after cleaning current task.
            self._clear_current_task()

            # check for auth and perm. current task cleared, do against new workflow_name
            self.check_for_authentication()
            self.check_for_permission()

            # wf knowledge is taken for external wf.
            self.workflow_spec = self.get_worfklow_spec()
            # New WF instance is created for external wf.
            self.workflow = self.create_workflow()
            # Current WF is this WF instance.
            self.current.workflow = self.workflow
            # main_wf: main wf information.
            # in_external: it states external wf in progress.
            # finished: it shows that main wf didn't finish still progress in external wf.
            self.wf_state = {'main_wf': main_wf, 'in_external': True, 'finished': False}

    def _clear_current_task(self):

        """
        Clear tasks related attributes, checks permissions
        While switching WF to WF, authentication and permissions are checked for new WF.
        """
        self.current.task_name = None
        self.current.task_type = None
        self.current.task = None


    def _should_we_run(self):
        not_a_user_task = self.current.task_type != 'UserTask'
        wf_in_progress = not (self.current.task_name == 'End' and
                               self.current.task_type == 'Simple')
        if wf_in_progress and self.wf_state['finished']:
            wf_in_progress = False

        if not wf_in_progress and self.are_we_in_subprocess():
            wf_in_progress = True
        return self.current.flow_enabled and not_a_user_task and wf_in_progress

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
        # FIXME: raise if last task of a workflow is a UserTask
        # actually this check should be done at parser
        is_lane_changed = False

        while self._should_we_run():
            self.check_for_rerun_user_task()
            task = None
            for task in self.workflow.get_tasks(state=Task.READY):
                self.current.old_lane = self.current.lane_name
                self.current._update_task(task)
                if self.catch_lane_change():
                    return
                self.check_for_permission()
                self.check_for_lane_permission()
                self.log_wf_state()
                self.switch_lang()
                self.run_activity()
                self.parse_workflow_messages()
                self.workflow.complete_task_from_id(self.current.task.id)
                self._save_or_delete_workflow()
                self.switch_to_external_wf()

            if task is None:
                break
        self.switch_from_external_to_main_wf()
        self.current.output['token'] = self.current.token

        # look for incoming ready task(s)
        for task in self.workflow.get_tasks(state=Task.READY):
            self.current._update_task(task)
            self.catch_lane_change()
            self.handle_wf_finalization()

    def check_for_rerun_user_task(self):
        """
        Checks that the user task needs to re-run.
        If necessary, current task and pre task's states are changed and re-run.
        If wf_meta not in data(there is no user interaction from pre-task) and last completed task
        type is user task and current step is not EndEvent and there is no lane change,
        this user task is rerun.
        """
        data = self.current.input
        if 'wf_meta' in data:
            return

        current_task = self.workflow.get_tasks(Task.READY)[0]
        current_task_type = current_task.task_spec.__class__.__name__
        pre_task = current_task.parent
        pre_task_type = pre_task.task_spec.__class__.__name__

        if pre_task_type != 'UserTask':
            return

        if current_task_type == 'EndEvent':
            return

        pre_lane = pre_task.task_spec.lane
        current_lane = current_task.task_spec.lane
        if pre_lane == current_lane:
            pre_task._set_state(Task.READY)
            current_task._set_state(Task.MAYBE)

    def switch_lang(self):
        """Switch to the language of the current user.

        If the current language is already the specified one, nothing will be done.
        """
        locale = self.current.locale
        translation.InstalledLocale.install_language(locale['locale_language'])
        translation.InstalledLocale.install_locale(locale['locale_datetime'], 'datetime')
        translation.InstalledLocale.install_locale(locale['locale_number'], 'number')

    def catch_lane_change(self):
        """
        trigger a lane_user_change signal if we switched to a new lane
        and new lane's user is different from current one
        """
        if self.current.lane_name:
            if self.current.old_lane and self.current.lane_name != self.current.old_lane:
                # if lane_name not found in pool or it's user different from the current(old) user
                if (self.current.lane_id not in self.current.pool or
                            self.current.pool[self.current.lane_id] != self.current.user_id):
                    self.current.log.info("LANE CHANGE : %s >> %s" % (self.current.old_lane,
                                                                      self.current.lane_name))
                    if self.current.lane_auto_sendoff:
                        self.current.sendoff_current_user()
                    self.current.flow_enabled = False
                    if self.current.lane_auto_invite:
                        self.current.invite_other_parties(self._get_possible_lane_owners())
                    return True
                    # self.current.old_lane = self.current.lane_name

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
            roles = set()
            perm = self.current.lane_permission
            roles.update(self.permission_model.objects.get(perm).get_permitted_roles())
            return list(roles)

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
        if self.current.lane_permission:
            log.debug("HAS LANE PERM: %s" % self.current.lane_permission)
            perm = self.current.lane_permission
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
            lane = self.current.lane_id
            permission = "%s.%s.%s" % (self.current.workflow_name, lane, self.current.task_name)
        else:
            permission = self.current.workflow_name
        log.debug("CHECK PERM: %s" % permission)

        if (self.current.task_type not in PERM_REQ_TASK_TYPES or
                permission.startswith(tuple(settings.ANONYMOUS_WORKFLOWS)) or
                (self.current.is_auth and permission.startswith(tuple(settings.COMMON_WORKFLOWS)))):
            return
        # FIXME:needs hardening

        log.debug("REQUIRE PERM: %s" % permission)
        if not self.current.has_permission(permission):
            raise HTTPError(403, "You don't have required permission: %s" % permission)

    def handle_wf_finalization(self):
        """
        Removes the ``token`` key from ``current.output`` if WF is over.
        """
        if ((not self.current.flow_enabled or (
            self.current.task_type.startswith('End') and not self.are_we_in_subprocess())) and
                    'token' in self.current.output):
            del self.current.output['token']
