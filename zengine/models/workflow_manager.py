# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
import types

from datetime import datetime
from time import sleep
from traceback import format_exc

import functools

import six
from pika.exceptions import ChannelClosed
from pika.exceptions import ConnectionClosed
from pyoko import Model, field, ListNode, LinkProxy
from pyoko.conf import settings
from pyoko.exceptions import ObjectDoesNotExist
from pyoko.fields import DATE_TIME_FORMAT
from pyoko.lib.utils import get_object_from_path, lazy_property
from SpiffWorkflow.bpmn.parser.util import full_attr, BPMN_MODEL_NS, ATTRIBUTE_NS
from pyoko.modelmeta import model_registry
from zengine.client_queue import get_mq_connection
from zengine.lib.cache import Cache
from zengine.lib.translation import gettext_lazy as _
import xml.etree.ElementTree as ET

from zengine.lib.decorators import ROLE_GETTER_CHOICES, bg_job, ROLE_GETTER_METHODS

UnitModel = get_object_from_path(settings.UNIT_MODEL)
RoleModel = get_object_from_path(settings.ROLE_MODEL)
AbstractRoleModel = get_object_from_path(settings.ABSTRACT_ROLE_MODEL)


class DiagramXML(Model):
    """
    Diagram XML versions
    """
    body = field.String("XML content", index=False)
    name = field.String("Name")

    @classmethod
    def get_or_create_by_content(cls, name, content):
        """
        if xml content updated, create a new entry for given wf name
        Args:
            name: name of wf
            content: xml content

        Returns (DiagramXML(), bool): A tuple with two members.
        (DiagramXML instance and True if it's new or False it's already exists
        """
        new = False
        diagrams = cls.objects.filter(name=name)
        if diagrams:
            diagram = diagrams[0]
            if diagram.body != content:
                new = True
        else:
            new = True
        if new:
            diagram = cls(name=name, body=content).save()
        return diagram, new

    def __unicode__(self):
        return "%s [%s]" % (self.name, self.get_humane_value('timestamp'))


class RunningInstancesExist(Exception):
    pass


NS = {'bpmn': BPMN_MODEL_NS,
      'camunda': ATTRIBUTE_NS}


class BPMNParser(object):
    """
    Custom BPMN diagram parser
    """

    def __init__(self, xml_content=None, xml_file=None):
        try:
            if xml_content:
                try:
                    import StringIO
                except ImportError:  # Python 3
                    from io import StringIO
                self.root = ET.parse(StringIO.StringIO(xml_content))
            else:
                self.root = ET.parse(xml_file)
        except ET.ParseError:
            print(xml_content or xml_file)
            raise

    def get_description(self):
        """
        Tries to get WF description from 'collabration' or 'process' or 'pariticipant'

        Returns str: WF description

        """
        paths = ['bpmn:collaboration/bpmn:participant/bpmn:documentation',
                 'bpmn:collaboration/bpmn:documentation',
                 'bpmn:process/bpmn:documentation']
        for path in paths:
            elm = self.root.find(path, NS)
            if elm is not None and elm.text:
                return elm.text

    def get_name(self):
        """
        Tries to get WF name from 'process' or 'collobration' or 'pariticipant'

        Returns:
            str. WF name.
        """
        paths = ['bpmn:process',
                 'bpmn:collaboration/bpmn:participant/',
                 'bpmn:collaboration',
                 ]
        for path in paths:
            tag = self.root.find(path, NS)
            if tag is not None and len(tag):
                name = tag[0].get('name')
                if name:
                    return name


class BPMNWorkflow(Model):
    """

    BPMNWorkflow model holds the XML content of BPMN diagram.
    It's also can hold any WF specific setting and configuration.

    """
    xml = DiagramXML()
    name = field.String("File name")
    title = field.String("Workflow Title")
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
        return self.name

    def set_xml(self, diagram, force=False):
        """
        updates xml link if there aren't any running instances of this wf
        Args:
            diagram: XMLDiagram object
        """
        no_of_running = WFInstance.objects.filter(wf=self, finished=False, started=True).count()
        if no_of_running and not force:
            raise RunningInstancesExist(
                "Can't update WF diagram! Running %s WF instances exists for %s" % (
                    no_of_running, self.name
                ))
        else:
            self.xml = diagram
            parser = BPMNParser(diagram.body)
            self.description = parser.get_description()
            self.title = parser.get_name() or self.name.replace('_', ' ').title()
            self.save()


JOB_REPEATING_PERIODS = (
    (0, 'No repeat'),
    (5, 'Hourly'),
    (10, 'Daily'),
    (15, 'Weekly'),
    (20, 'Monthly'),
    (25, 'Yearly'),
)

JOB_NOTIFICATION_DENSITY = (
    (0, _('None')),
    (5, _('15 day before, once in 3 days')),
    (10, _('1 week before, daily')),
    (15, _('Day before start time')),
)

ROLE_SEARCH_DEPTH = (
    (1, _('Selected unit')),
    (2, _('Selected unit and all sub-units of it'))
)


def get_progress(start, finish):
    now = datetime.now()
    dif_time_start = start - now
    dif_time_finish = finish - now

    if dif_time_start.days < 0 and dif_time_finish.days < 0:
        return PROGRESS_STATES[3][0]
    elif dif_time_start.days < 0 and dif_time_finish.days >= 1:
        return PROGRESS_STATES[2][0]
    elif dif_time_start.days >= 1 and dif_time_finish.days >= 1:
        return PROGRESS_STATES[0][0]
    else:
        return PROGRESS_STATES[2][0]


def get_model_choices():
    return [{'name': k, 'value': v.Meta.verbose_name} for k, v in model_registry.registry.items()]


class Task(Model):
    """

    Task definition for workflows

    """
    run = field.Boolean("Create tasks now!", default=False)
    wf = BPMNWorkflow()
    name = field.String(_("Name of task"))
    abstract_role = AbstractRoleModel("Abstract Role", null=True)
    role = RoleModel(null=True)
    unit = UnitModel(null=True)
    get_roles_from = field.Integer(_("Get roles from"), choices=ROLE_GETTER_CHOICES)
    role_query_code = field.String(_("Role query dict"), null=True)
    object_query_code = field.String(_("Object query dict"), null=True)
    object_key = field.String(_("Subject ID"), null=True)
    object_type = field.String(_("Object type"), null=True, choices=get_model_choices)
    start_date = field.DateTime(_("Start time"))
    finish_date = field.DateTime(_("Finish time"))
    repeat = field.Integer(_("Repeating period"), default=0, choices=JOB_REPEATING_PERIODS)
    notification_density = field.Integer(_("Notification density"),
                                         choices=JOB_NOTIFICATION_DENSITY)
    recursive_units = field.Boolean("Get roles from all sub-units")

    class Meta:
        verbose_name = "Workflow Task"
        verbose_name_plural = "Workflows Tasks"
        search_fields = ['name']
        list_fields = ['name', ]

    def create_tasks(self):
        """
        will create a WFInstance per object
        and per TaskInvitation for each role and WFInstance
        """
        roles = self.get_roles()
        wf_instances = self.create_wf_instances()
        self.create_invitations(roles, wf_instances)

    def create_invitations(self, roles, wf_instances):
        """creates a TaskInvitation for each role for each WFInstnace"""
        for wfi in wf_instances:
            for role in roles:
                TaskInvitation(instance=wfi, role=role, wf_name=self.wf.name,
                               progress=get_progress(start=self.start_date,
                                                     finish=self.finish_date),
                               start_date=self.start_date, finish_date=self.finish_date).save()

    def create_wf_instances(self):
        """ creates a WFInstnace for each object"""
        obj_keys = self.get_object_keys()
        if not obj_keys:
            return [WFInstance(wf=self.wf,
                               task=self,
                               name=self.wf.name,
                               wf_object_type=self.object_type).save()]
        else:
            return [WFInstance(wf=self.wf,
                               task=self,
                               wf_object=obj_key,
                               name=self.wf.name,
                               wf_object_type=self.object_type).save()
                    for obj_key in obj_keys]

    def get_object_query_dict(self):
        """returns objects keys according to self.object_query_code
        which can be json encoded queryset filter dict or key=value set
         in the following format: ```"key=val, key2 = val2 , key3= value with spaces"```

        Returns:
             dict. Queryset filtering dict
        """
        if isinstance(self.object_query_code, dict):
            # _DATE_ _DATETIME_
            return self.object_query_code
        else:
            # comma separated, key=value pairs. wrapping spaces will be ignored
            # eg: "key=val, key2 = val2 , key3= value with spaces"
            return dict([map(str.strip, pair.split('='))
                         for pair in self.object_query_code.split(',')])

    def get_object_keys(self):
        """returns object keys according to task definition
        which can be explicitly selected one object (self.object_key) or
        result of a queryset filter.

        Returns:
            list of object keys
        """
        if self.object_key:
            return [self.object_key]
        if self.object_query_code:
            model = model_registry.get_model(self.object_type)
            return [key for data, key in
                    model.objects.filter(**self.get_object_query_dict()).data()]

    def get_roles(self):
        """
        Returns:
            Role instances according to task definition.
        """
        if self.role.exist:
            # return explicitly selected role
            return [self.role]
        else:
            roles = []
            if self.role_query_code:
                #  use given "role_query_code"
                roles = RoleModel.objects.filter(**self.role_query_code)
            elif self.unit.exist:
                # get roles from selected unit or sub-units of it
                if self.recursive_units:
                    # this returns a list, we're converting it to a Role generator!
                    roles = (RoleModel.objects.get(k) for k in UnitModel.get_role_keys(self.unit.key))
                else:
                    roles = RoleModel.objects.filter(unit=self.unit)
            elif self.get_roles_from:
                # get roles from selected predefined "get_roles_from" method
                roles = ROLE_GETTER_METHODS[self.get_roles_from]()

        if self.abstract_role.exist and roles:
            # apply abstract_role filtering on roles we got
            if isinstance(roles, (list, types.GeneratorType)):
                roles = [a for a in roles if a.abstract_role == self.abstract_role]
            else:
                roles = roles.filter(abstract_role=self.abstract_role)
        else:
            roles = RoleModel.objects.filter(abstract_role=self.abstract_role)

        return roles

    def post_save(self):
        """can be removed when a proper task manager admin interface implemented"""
        if self.run:
            self.run = False
            self.create_tasks()
            self.save()

    def __unicode__(self):
        return '%s' % self.name


class WFInstance(Model):
    """

    Running workflow instance

    """
    wf = BPMNWorkflow()
    task = Task()
    name = field.String("WF Name")
    subject = field.String(_("Subject ID"))
    current_actor = RoleModel("Current Actor")
    wf_object = field.String("Subject ID")
    wf_object_type = field.String(_("Object type"), null=True, choices=get_model_choices)
    last_activation = field.DateTime("Last activation")
    finished = field.Boolean(default=False)
    started = field.Boolean(default=False)
    in_external = field.Boolean(default=False)
    start_date = field.DateTime("Start time")
    finish_date = field.DateTime("Finish time")
    step = field.String("Last executed WF Step")
    data = field.String("Task Data")
    pool = field.String("Pool Data")

    class Meta:
        verbose_name = "Workflow Instance"
        verbose_name_plural = "Workflows Instances"
        search_fields = ['name']
        list_fields = ['name', 'current_actor']

    def get_object(self):
        if self.wf_object_type:
            model = model_registry.get_model(self.wf_object_type)
            return model.objects.get(self.wf_object)
        else:
            return ''

    def actor(self):
        return self.current_actor.user.full_name if self.current_actor.exist else '-'

    actor.title = 'Current Actor'

    # class Pool(ListNode):
    #     order = field.Integer("Lane order")
    #     role = RoleModel()

    def pre_save(self):
        if not self.wf and self.name:
            self.wf = BPMNWorkflow.objects.get(name=self.name)

    def __unicode__(self):
        return '%s instance (%s)' % (self.wf.name, self.key)


OWNERSHIP_STATES = (
    (10, 'Unclaimed'),  # waiting in job pool
    (20, 'Claimed'),  # claimed by user
    (30, 'Assigned'),  # assigned to user
    (40, 'Transferred'),  # transferred from another user
)
PROGRESS_STATES = (
    (10, 'Future'),  # work will be done in the future
    (20, 'Waiting'),  # (Active) waiting for owner to start to work on it
    (30, 'In Progress'),  # (Active) work in progress
    (40, 'Finished'),  # task completed
    (90, 'Expired'),  # task does not finished before it's due date
)


class TaskInvitation(Model):
    """
    User facing part of task management system

    """
    instance = WFInstance()
    role = RoleModel()
    ownership = field.Integer(default=10, choices=OWNERSHIP_STATES)
    progress = field.Integer(default=10, choices=PROGRESS_STATES)
    wf_name = field.String("WF Name")
    title = field.String("Task Name")
    search_data = field.String("Combined full-text search data")
    start_date = field.DateTime("Start time")
    finish_date = field.DateTime("Finish time")

    def get_object_name(self):
        return six.text_type(self.instance.get_object())

    def pre_save(self):
        self.title = "%s" % self.wf_name
        self.search_data = '\n'.join([self.wf_name,
                                      self.title]
                                     )

    def __unicode__(self):
        return "%s invitation for %s" % (self.wf_name, self.role)

    def delete_other_invitations(self):
        """
        When one person use an invitation, we should delete other invitations
        """
        # TODO: Signal logged-in users to remove the task from their task list
        self.objects.filter(instance=self.instance).exclude(key=self.key).delete()


class WFCache(Cache):
    """
    Cache object for workflow instances.

    Args:
        wf_token: Token of the workflow instance.
    """
    PREFIX = 'WF'
    mq_channel = None
    mq_connection = None

    def __init__(self, current):
        try:
            self.db_key = current.token
        except AttributeError:
            self.db_key = current.input['token']
        self.sess_id = current.session.sess_id
        self.current = current
        self.wf_state = {}
        super(WFCache, self).__init__(self.db_key)

    @classmethod
    def _connect_mq(cls):
        if cls.mq_connection is None or cls.mq_connection.is_closed:
            cls.mq_connection, cls.mq_channel = get_mq_connection()
        return cls.mq_channel

    def publish(self, **data):
        _data = {'exchange': 'input_exc',
                 # 'routing_key': self.sess_id,
                 'routing_key': '',
                 'body': json.dumps({
                     'data': data,
                     '_zops_source': 'Internal',
                     '_zops_remote_ip': ''})}
        try:
            self.mq_channel.basic_publish(**_data)
        except (AttributeError, ConnectionClosed, ChannelClosed):
            self._connect_mq().basic_publish(**_data)

    def get_from_db(self):
        try:
            data, key = WFInstance.objects.data().get(self.db_key)
            return data
        except ObjectDoesNotExist:
            return None

    def get(self, default=None):
        self.wf_state = super(WFCache, self).get() or self.get_from_db() or default
        if 'finish_date' in self.wf_state:
            try:
                dt = datetime.strptime(self.wf_state['finish_date'], DATE_TIME_FORMAT)
                self.wf_state['finish_date'] = dt.strftime(settings.DATETIME_DEFAULT_FORMAT)
            except ValueError:
                # FIXME: we should properly handle wfengine > db > wfengine DATE format conversion
                pass
        return self.wf_state

    def get_instance(self):
        data_from_cache = super(WFCache, self).get()
        if data_from_cache:
            wfi = WFInstance()
            wfi._load_data(data_from_cache, from_db=True)
            wfi.key = self.db_key
            return wfi
        else:
            return WFInstance.objects.get(self.db_key)

    def save(self, wf_state):
        """
        write wf state to DB through MQ >> Worker >> _zops_sync_wf_cache

        Args:
            wf_state dict: wf state
        """
        self.wf_state = wf_state
        self.wf_state['role_id'] = self.current.role_id
        self.set(self.wf_state)
        if self.wf_state['name'] not in settings.EPHEMERAL_WORKFLOWS:
            self.publish(job='_zops_sync_wf_cache',
                         token=self.db_key)


@bg_job("_zops_sync_wf_cache")
def sync_wf_cache(current):
    """
    BG Job for storing wf state to DB
    """
    wf_cache = WFCache(current)
    wf_state = wf_cache.get()
    if 'role_id' in wf_state:
        # role_id inserted by engine, so it's a sign that we get it from cache not db
        try:
            wfi = WFInstance.objects.get(key=current.input['token'])
        except ObjectDoesNotExist:
            # wf's that not started from a task invitation
            wfi = WFInstance(key=current.input['token'])
            wfi.wf = BPMNWorkflow.objects.get(name=wf_state['name'])
        if not wfi.current_actor.exist:
            # we just started the wf
            try:
                inv = TaskInvitation.objects.get(instance=wfi, role_id=wf_state['role_id'])
                inv.delete_other_invitations()
                inv.state = 20
                inv.save()
            except ObjectDoesNotExist:
                current.log.exception("Invitation not found: %s" % wf_state)
        wfi.step = wf_state['step']
        wfi.name = wf_state['name']
        wfi.pool = wf_state['pool']
        wfi.current_actor_id = wf_state['role_id']
        wfi.data = wf_state['data']
        if wf_state['finished']:
            wfi.finished = True
            wfi.finish_date = wf_state['finish_date']
            wf_cache.delete()
        wfi.save()
    else:
        # if cache already cleared, we have nothing to sync
        pass
