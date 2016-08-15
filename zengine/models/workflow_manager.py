# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from pyoko import Model, field, ListNode, LinkProxy
from pyoko.conf import settings
from pyoko.lib.utils import get_object_from_path

UnitModel = get_object_from_path(settings.UNIT_MODEL)
RoleModel = get_object_from_path(settings.ROLE_MODEL)
AbstractRoleModel = get_object_from_path(settings.ABSTRACT_ROLE_MODEL)

class DiagramXML(Model):
    """
    Diagram XML versions
    """
    body = field.String("XML content", index=False)
    name = field.String("Name")

class BPMNWorkflow(Model):
    """

    BPMNWorkflow model holds the XML content of BPMN diagram.
    It's also can hold any WF specific setting and configuration.

    """
    xml = DiagramXML()
    name = field.String("Name")
    description = field.String("Description")
    show_in_menu = field.Boolean(default=False)
    requires_object = field.Boolean(default=False)
    object_field_name = field.String("Object field name")

    class Pool(ListNode):
        order = field.Integer("Lane order")
        actor_name = field.String("Actor name")
        wf_name = field.String("Actor specific name of WF")
        relations = field.String("Lane relations")
        possible_owners = field.String("Possible owners")
        permissions = field.String("Permissions")

    class Meta:
        verbose_name = "Workflow"
        verbose_name_plural = "Workflows"
        search_fields = ['name']
        list_fields = ['name', ]

    def __unicode__(self):
        return '%s' % self.name


class WFInstance(Model):
    """

    Running workflow instance

    """
    wf = BPMNWorkflow()
    role = RoleModel()
    diagram_version = field.DateTime()
    wf_object = field.String("Subject ID")
    start_date = field.DateTime("Start time")
    last_activation = field.DateTime("Last activation")
    finish_date = field.DateTime("Finish time")
    state = field.String("WF State")

    class Meta:
        verbose_name = "Workflow Instance"
        verbose_name_plural = "Workflows Instances"
        search_fields = ['name']
        list_fields = ['name', ]

    class Pool(ListNode):
        order = field.Integer("Lane order")
        role = RoleModel()

    def __unicode__(self):
        return '%s instance (%s)' % (self.wf.name, self.key)


JOB_REPEATING_PERIODS = (
    (0, 'No repeat'),
    (5, 'Hourly'),
    (10, 'Daily'),
    (15, 'Weekly'),
    (20, 'Monthly'),
    (25, 'Yearly'),
)

JOB_NOTIFICATION_DENSITY = (
    (0, 'None'),
    (5, '15 day before, once in 3 days'),
    (10, '1 week before, daily'),
    (15, 'Day before start time'),
)

JOB_TYPES = (
    (0, 'Model'),
    (5, 'Abstract Role'),
    (10, 'Role'),
    (15, 'Unit'),
)


class WFTask(Model):
    """

    Task definition for workflows

    """
    wf = BPMNWorkflow()
    name = field.String("Name of task")
    abstract_role = AbstractRoleModel(null=True)
    role = RoleModel(null=True)
    root_unit = UnitModel(null=True)
    role_query_code = field.String("Role query method", null=True)
    object_query_code = field.String("Role query method", null=True)
    object_key = field.String("Subject ID", null=True)
    start_date = field.DateTime("Start time")
    finish_date = field.DateTime("Finish time")
    repeat = field.Integer("Repeating period", default=0, choices=JOB_REPEATING_PERIODS)
    task_type = field.Integer("Task Type", choices=JOB_TYPES)
    notification_density = field.Integer("Notification density", choices=JOB_NOTIFICATION_DENSITY)

    class Meta:
        verbose_name = "Workflow Task"
        verbose_name_plural = "Workflows Tasks"
        search_fields = ['name']
        list_fields = ['name', ]

    def __unicode__(self):
        return '%s' % self.name
