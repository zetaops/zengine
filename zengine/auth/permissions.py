# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from SpiffWorkflow.bpmn.specs.UserTask import UserTask
from SpiffWorkflow.bpmn.specs.ServiceTask import ServiceTask


class CustomPermission(object):
    """
    CustomPermissions registry
    Use "add_perm" object to create and use custom permissions
    eg: add_perm("can_see_everything")
    """
    registry = {}

    @classmethod
    def add_multi(cls, perm_list):
        for perm in perm_list:
            cls.add(*perm)

    @classmethod
    def add(cls, code_name, name='', description=''):
        """
        create a custom permission
        """
        if code_name not in cls.registry:
            cls.registry[code_name] = (code_name, name or code_name, description)
        return code_name

    @classmethod
    def get_permissions(cls):
        """
        Returns:
            Permission list.
        """
        return list(cls.registry.values())

# skip permmission checking for this taks types
PERM_REQ_TASK_TYPES = ('UserTask', 'ServiceTask')


def _get_workflows():
    from zengine.engine import ZEngine, WFCurrent
    from zengine.models import BPMNWorkflow

    workflows = []
    for wf in BPMNWorkflow.objects.all():
        engine = ZEngine()
        engine.current = WFCurrent(workflow_name=wf.name)
        workflows.append(engine.load_or_create_workflow())
    return workflows



def _get_workflow_permissions(permission_list=None):
    # [('code_name', 'name', 'description'),...]
    permissions = permission_list or []
    for wf in _get_workflows():
        wf_name = wf.spec.name
        wf_description = wf.spec.description or wf.spec.name
        # Add workflow permission
        permissions.append((wf_name, wf_description, ""))
        # Add lane permissions
        permissions.extend(list(_get_lane_permissions(permissions, wf.spec)))
        # Add task permissions
        for name, task_spec in wf.spec.task_specs.items():
            # Skip spec objects like StartTask, ExclusiveGateway etc.
            if not isinstance(task_spec, (UserTask, ServiceTask)):
                continue
            # `name` field of Modeler is used as `description` by SpiffWorkflow
            description = task_spec.description
            lane = task_spec.lane_id or ''
            permissions.append(
                # Code
                ("%s.%s.%s" % (wf_name, lane, name),
                # Name
                "%s %s" % (description if description != "" else name, task_spec.__class__.__name__),
                # Description
                "")
            )
    return permissions

def _get_lane_permissions(permissions, spec):
    # Using a set to get unique lanes
    return {('{}.{}'.format(spec.name, task.lane_id), task.lane, '')
            for task in spec.task_specs.values()
            # Exclude the ones that don't have lane ids, or have lane ids that are empty
            if getattr(task, 'lane_id', None)}

def _get_object_menu_models():
    """
    we need to create basic permissions
    for only CRUD enabled models
    """
    from pyoko.conf import settings
    enabled_models = []
    for entry in settings.OBJECT_MENU.values():
        for mdl in entry:
            if 'wf' not in mdl:
                enabled_models.append(mdl['name'])
    return enabled_models

def _get_model_permissions(permission_list=None):
    from pyoko.model import model_registry
    from zengine.views.crud import CrudView
    generic_commands = CrudView().VIEW_METHODS.keys()
    permissions = permission_list or []
    enabled_models = _get_object_menu_models()
    for model in model_registry.get_base_models():
        model_name = model.__name__
        permissions.append((model_name, model_name, ""))
        if model_name not in enabled_models:
            # no matter if it's available as CRUD or not,
            # we may need a ListBox for any model
            permissions.append(("%s.select_list" % model_name, "Listbox for %s" % model_name, ""))
            continue


        for cmd in generic_commands:
            if cmd in ['do']:
                continue
            permissions.append(("%s.%s" % (model_name, cmd),
                                "Can %s %s" % (cmd, model_name),
                                ""))

    return permissions


def get_all_permissions():
    """
    Default permission provider

    Returns:
        List of  permissions
    """
    permissions = _get_workflow_permissions()
    _get_model_permissions(permissions)
    return permissions + CustomPermission.get_permissions()

CustomPermission.add_multi(
    # ('code_name', 'human_readable_name', 'description'),
    [
        ('can_manage_user_perms', 'Able to manage user permissions',
     'This perm authorizes a person for management of related permissions'),
    ])
