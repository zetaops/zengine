# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import glob
import os


class CustomPermissions(object):
    """
    CustomPermissions registry
    Use "add_perm" object to create and use custom permissions
    eg: add_perm("can_see_everything")
    """
    registry = {}

    def __call__(self, code_name, name='', description=''):
        """
        create a custom permission

        :param code_name:
        :param name:
        :param description:
        :return:
        """
        if code_name not in self.registry:
            self.registry[code_name] = (code_name, name or code_name, description)
        return code_name

    @classmethod
    def get_permissions(cls):
        return cls.registry.values()


add_perm = CustomPermissions()

NO_PERM_TASKS = ('End', 'Root', 'Start', 'Gateway')

def get_workflow_permissions(permission_list=None):
    # [('code_name', 'name', 'description'),...]
    permissions = permission_list or []
    from zengine.config import settings
    from zengine.engine import ZEngine, Current, log
    engine = ZEngine()
    for package_dir in settings.WORKFLOW_PACKAGES_PATHS:
        for bpmn_diagram_path in glob.glob(package_dir + "/*.bpmn"):
            wf_name = os.path.splitext(os.path.basename(bpmn_diagram_path))[0]
            permissions.append((wf_name, wf_name, ""))
            engine.current = Current(workflow_name=wf_name)
            try:
                workflow = engine.load_or_create_workflow()
            except:
                log.exception("Workflow cannot be created.")
            # print(wf_name)
            # pprint(workflow.spec.task_specs)
            for name, task_spec in workflow.spec.task_specs.items():
                if any(no_perm_task in name for no_perm_task in NO_PERM_TASKS):
                    continue
                permissions.append(("%s.%s" % (wf_name, name),
                                    "%s %s of %s" % (name,
                                                     task_spec.__class__.__name__,
                                                     wf_name),
                                    ""))
    return permissions


def get_model_permissions(permission_list=None):
    from pyoko.model import model_registry
    from zengine.engine import ALLOWED_CLIENT_COMMANDS
    permissions = permission_list or []
    for model in model_registry.get_base_models():
        model_name = model.__name__
        permissions.append((model_name, model_name, ""))
        for cmd in ALLOWED_CLIENT_COMMANDS:
            if cmd in ['do']:
                continue
            permissions.append(("%s.%s" % (model_name, cmd),
                                "Can %s %s" % (cmd, model_name),
                                ""))

    return permissions


def get_all_permissions():
    permissions = get_workflow_permissions()
    get_model_permissions(permissions)
    return permissions + CustomPermissions.get_permissions()
