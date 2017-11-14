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
import six
from pika.exceptions import ChannelClosed
from pika.exceptions import ConnectionClosed
from pyoko import Model, field, ListNode
from pyoko.conf import settings
from pyoko.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from pyoko.fields import DATE_TIME_FORMAT
from pyoko.lib.utils import get_object_from_path
from SpiffWorkflow.bpmn.parser.util import BPMN_MODEL_NS, ATTRIBUTE_NS
from pyoko.modelmeta import model_registry
from zengine.client_queue import get_mq_connection
from zengine.lib.cache import Cache
from zengine.lib.translation import gettext_lazy as __
import xml.etree.ElementTree as ET

from zengine.lib.decorators import ROLE_GETTER_CHOICES, bg_job, ROLE_GETTER_METHODS

UnitModel = get_object_from_path(settings.UNIT_MODEL)
RoleModel = get_object_from_path(settings.ROLE_MODEL)
AbstractRoleModel = get_object_from_path(settings.ABSTRACT_ROLE_MODEL)


class DiagramXML(Model):
    """
    Diagram XML versions
    """
    body = field.String(__(u"XML content"), index=False)
    name = field.String(__(u"Name"))

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
                    from StringIO import StringIO
                except ImportError:  # Python 3
                    from io import StringIO
                self.root = ET.parse(StringIO(xml_content))
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
                name = tag.get('name')
                if name:
                    return name

    def get_wf_extensions(self):
        paths = [
            'bpmn:collaboration/bpmn:participant/bpmn:extensionElements/camunda:properties/camunda:property',
            'bpmn:collaboration/bpmn:extensionElements/camunda:properties/camunda:property',
            'bpmn:process/bpmn:extensionElements/camunda:properties/camunda:property'
        ]
        elements = []
        for path in paths:
            elements.extend(self.root.findall(path, NS))
        return [(el.get('name'), el.get('value')) for el in elements]


class BPMNWorkflow(Model):
    """

    BPMNWorkflow model holds the XML content of BPMN diagram.
    It's also can hold any WF specific setting and configuration.

    """
    xml = DiagramXML()
    name = field.String(__(u"File name"))
    title = field.String(__(u"Workflow Title"))
    description = field.String(__(u"Description"))
    show_in_menu = field.Boolean(default=False)
    requires_object = field.Boolean(default=False)
    object_field_name = field.String(__(u"Object field name"))
    menu_category = field.String(__(u"Menu Category"))

    # field programmable is for task manager
    # to specify wf instances can be triggered automatically
    # by setting a schedule or not
    programmable = field.Boolean(default=False)

    # field task_type is for task manager
    # to determine how wf instances will be created and delivered.
    # A, B, C or D which are detailed in Task model's task_type property
    task_type = field.String()

    class Pool(ListNode):
        order = field.Integer(__(u"Lane order"))
        actor_name = field.String(__(u"Actor name"))
        wf_name = field.String(__(u"Actor specific name of WF"))
        relations = field.String(__(u"Lane relations"))
        possible_owners = field.String(__(u"Possible owners"))
        permissions = field.String(__(u"Permissions"))

    class Meta:
        verbose_name = "Workflow"
        verbose_name_plural = "Workflows"
        search_fields = ['name']
        list_fields = ['name', ]

    def __unicode__(self):
        return self.title or self.name

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
            extensions = dict(parser.get_wf_extensions())
            self.programmable = extensions.get('programmable', False)
            self.task_type = extensions.get('task_type', None)
            self.menu_category = extensions.get('menu_category', settings.DEFAULT_WF_CATEGORY_NAME)
            self.save()


JOB_REPEATING_PERIODS = (
    (0, __(u'No repeat')),
    (5, __(u'Hourly')),
    (10, __(u'Daily')),
    (15, __(u'Weekly')),
    (20, __(u'Monthly')),
    (25, __(u'Yearly')),
)

JOB_NOTIFICATION_DENSITY = (
    (0, __(u'None')),
    (5, __(u'15 day before, once in 3 days')),
    (10, __(u'1 week before, daily')),
    (15, __(u'Day before start time')),
)

ROLE_SEARCH_DEPTH = (
    (1, __(u'Selected unit')),
    (2, __(u'Selected unit and all sub-units of it'))
)


def get_progress(start, finish):
    """
    Args:
        start (DateTime): start date
        finish (DateTime): finish date
    Returns:

    """
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
    run = field.Boolean(__(u"Create tasks now!"), default=False)
    wf = BPMNWorkflow()
    name = field.String(__(u"Name of task"))
    abstract_role = AbstractRoleModel(__(u"Abstract Role"), null=True)
    role = RoleModel(null=True)
    unit = UnitModel(null=True)
    get_roles_from = field.String(__(u"Get roles from"), choices=ROLE_GETTER_CHOICES)
    role_query_code = field.String(__(u"Role query dict"), null=True)
    object_query_code = field.String(__(u"Object query dict"), null=True)
    object_key = field.String(__(u"Subject ID"), null=True)
    object_type = field.String(__(u"Object type"), null=True, choices=get_model_choices)
    start_date = field.DateTime(__(u"Start time"), format="%d.%m.%Y")
    finish_date = field.DateTime(__(u"Finish time"), format="%d.%m.%Y")
    repeat = field.Integer(__(u"Repeating period"), default=0, choices=JOB_REPEATING_PERIODS)
    notification_density = field.Integer(__(u"Notification density"),
                                         choices=JOB_NOTIFICATION_DENSITY)
    recursive_units = field.Boolean(__(u"Get roles from all sub-units"))

    class Meta:
        verbose_name = "Workflow Task"
        verbose_name_plural = "Workflows Tasks"
        search_fields = ['name']
        list_fields = ['name', ]

    def create_wf_instances(self, roles=None):
        """
        Creates wf instances.
        Args:
            roles (list): role list

        Returns:
            (list): wf instances
        """

        # if roles specified then create an instance for each role
        # else create only one instance

        if roles:
            wf_instances = [
                WFInstance(
                    wf=self.wf,
                    current_actor=role,
                    task=self,
                    name=self.wf.name
                ) for role in roles
                ]
        else:
            wf_instances = [
                WFInstance(
                    wf=self.wf,
                    task=self,
                    name=self.wf.name
                )
            ]

        # if task type is not related with objects save instances immediately.
        if self.task_type in ["C", "D"]:
            return [wfi.save() for wfi in wf_instances]

        # if task type is related with its objects, save populate instances per object
        else:
            wf_obj_instances = []
            for wfi in wf_instances:
                role = wfi.current_actor if self.task_type == "A" else None
                keys = self.get_object_keys(role)
                wf_obj_instances.extend(
                    [WFInstance(
                        wf=self.wf,
                        current_actor=role,
                        task=self,
                        name=self.wf.name,
                        wf_object=key,
                        wf_object_type=self.object_type
                    ).save() for key in keys]
                )

            return wf_obj_instances

    def create_task_invitation(self, instances, roles=None):
        for wfi in instances:
            current_roles = roles or [wfi.current_actor]
            for role in current_roles:
                inv = TaskInvitation(
                    instance=wfi,
                    role=role,
                    wf_name=self.wf.name,
                    progress=get_progress(start=self.start_date, finish=self.finish_date),
                    start_date=self.start_date, finish_date=self.finish_date
                )
                inv.title = self.name
                inv.save()

    def create_tasks(self):
        """
        will create a WFInstance per object
        and per TaskInvitation for each role and WFInstance
        """
        roles = self.get_roles()

        if self.task_type in ["A", "D"]:
            instances = self.create_wf_instances(roles=roles)
            self.create_task_invitation(instances)

        elif self.task_type in ["C", "B"]:
            instances = self.create_wf_instances()
            self.create_task_invitation(instances, roles)

    def get_object_query_dict(self):
        """returns objects keys according to self.object_query_code
        which can be json encoded queryset filter dict or key=value set
         in the following format: ```"key=val, key2 = val2 , key3= value with spaces"```

        Returns:
             (dict): Queryset filtering dicqt
        """
        if isinstance(self.object_query_code, dict):
            # _DATE_ _DATETIME_
            return self.object_query_code
        else:
            # comma separated, key=value pairs. wrapping spaces will be ignored
            # eg: "key=val, key2 = val2 , key3= value with spaces"
            return dict(pair.split('=') for pair in self.object_query_code.split(','))

    def get_object_keys(self, wfi_role=None):
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
            return [m.key for m in
                    self.get_model_objects(model, wfi_role, **self.get_object_query_dict())]

    @staticmethod
    def get_model_objects(model, wfi_role=None, **kwargs):
        """
        Fetches model objects by filtering with kwargs

        If wfi_role is specified, then we expect kwargs contains a
        filter value starting with role,

        e.g. {'user': 'role.program.user'}

        We replace this `role` key with role instance parameter `wfi_role` and try to get
        object that filter value 'role.program.user' points by iterating `getattribute`. At
        the end filter argument becomes {'user': user}.

        Args:
            model (Model): Model class
            wfi_role (Role): role instance of wf instance
            **kwargs: filter arguments

        Returns:
            (list): list of model object instances
        """
        query_dict = {}
        for k, v in kwargs.items():
            if isinstance(v, list):
                query_dict[k] = [str(x) for x in v]
            else:
                parse = str(v).split('.')
                if parse[0] == 'role' and wfi_role:
                    query_dict[k] = wfi_role
                    for i in range(1, len(parse)):
                        query_dict[k] = query_dict[k].__getattribute__(parse[i])
                else:
                    query_dict[k] = parse[0]

        return model.objects.all(**query_dict)

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
                    roles = (RoleModel.objects.get(k) for k in
                             UnitModel.get_role_keys(self.unit.key))
                else:
                    roles = RoleModel.objects.filter(unit=self.unit)
            elif self.get_roles_from:
                # get roles from selected predefined "get_roles_from" method
                return ROLE_GETTER_METHODS[self.get_roles_from](RoleModel)

        if self.abstract_role.exist and roles:
            # apply abstract_role filtering on roles we got
            if isinstance(roles, (list, types.GeneratorType)):
                roles = [a for a in roles if a.abstract_role.key == self.abstract_role.key]
            else:
                roles = roles.filter(abstract_role=self.abstract_role)
        else:
            roles = RoleModel.objects.filter(abstract_role=self.abstract_role)

        return roles

    @property
    def task_type(self):
        """
        Returns:
            (string) a task type defined as below

        "Type A":
                Roles are gathered from intersection of `get_roles_from`, `abstract_role` and
                `unit` recursively.

                Objects are filtered by `object_type` and `object_query_code`. And relation between
                objects and roles specified in object_query_code by `role` key.

                    ```
                    unit="A faculty",
                    abstract_role="Lecturer",
                    object_type="Class"
                    object_query_code="lecturer_id='role.key'" # role means lecturer's current role.

                    ```

                "fields": ["unit", "abstract_role", "get_roles_from", "object_type",
                           "object_query_code", "recursive"]
        "Type B":
                Roles are gathered from intersection of `get_roles_from`, `abstract_role` and
                `unit` recursively.

                Objects are filtered by `object_type` and `object_query_code`.

                     ```
                     unit="A faculty",
                     abstract_role="Managers",
                     object_type="Class"
                     object_query_code="capacity>50"

                     ```
                "fields": ["unit", "abstract_role", "get_roles_from", "object_type",
                           "object_query_code", "recursive"]

        "Type C":
                Roles are gathered from `get_roles_from` or `abstract_role` or intersection of both.

                No objects are specified. This type of task is for wfs which are not dependent on
                any object or unit, etc. e.g, periodic system management wf.

                     ```
                     abstract_role="Managers",

                     ```
                "fields": ["abstract_role", "get_roles_from"]

        "Type D":
                Roles are gathered from intersection of `get_roles_from`, `abstract_role` and
                `unit` recursively.

                No objects are specified. This type of task is for wfs which are not dependent on
                any object, but unit. e.g, change timetable schedule, choose advisers
                for department.

                     ```
                     unit="A faculty"
                     abstract_role="Chief of Department",

                     ```
                "fields": ["unit", "abstract_role", "get_roles_from", "recursive"]
        """

        if self.object_type:
            return "A" if self.is_role_in_object_query_code() else "B"
        else:
            return "C" if not self.unit.exist else "D"

    def is_role_in_object_query_code(self):
        query_code = self.get_object_query_dict()
        for k, v in query_code.items():
            parse = str(v).split('.')
            if parse[0] == 'role':
                return True
        return False

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
    name = field.String(__(u"WF Name"))
    subject = field.String(__(u"Subject ID"))
    current_actor = RoleModel(__(u"Current Actor"))
    wf_object = field.String(__(u"Subject ID"))
    wf_object_type = field.String(__(u"Object type"), null=True, choices=get_model_choices)
    last_activation = field.DateTime(__(u"Last activation"))
    finished = field.Boolean(default=False)
    started = field.Boolean(default=False)
    in_external = field.Boolean(default=False)
    start_date = field.DateTime(__(u"Start time"))
    finish_date = field.DateTime(__(u"Finish time"))
    step = field.String(__(u"Last executed WF Step"))
    data = field.String(__(u"Task Data"))
    pool = field.String(__(u"Pool Data"))

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
    (10, __(u'Unclaimed')),  # waiting in job pool
    (20, __(u'Claimed')),  # claimed by user
    (30, __(u'Assigned')),  # assigned to user
    (40, __(u'Transferred')),  # transferred from another user
)
PROGRESS_STATES = (
    (10, __(u'Future')),  # work will be done in the future
    (20, __(u'Waiting')),  # (Active) waiting for owner to start to work on it
    (30, __(u'In Progress')),  # (Active) work in progress
    (40, __(u'Finished')),  # task completed
    (90, __(u'Expired')),  # task does not finished before it's due date
)


class TaskInvitation(Model):
    """
    User facing part of task management system

    """
    instance = WFInstance()
    role = RoleModel()
    ownership = field.Integer(default=10, choices=OWNERSHIP_STATES)
    progress = field.Integer(default=10, choices=PROGRESS_STATES)
    wf_name = field.String(__(u"WF Name"))
    title = field.String(__(u"Task Name"))
    search_data = field.String(__(u"Combined full-text search data"))
    start_date = field.DateTime(__(u"Start time"))
    finish_date = field.DateTime(__(u"Finish time"))

    def get_object_name(self):
        return six.text_type(self.instance.get_object())

    def pre_save(self):
        self.title = self.title or self.instance.name

        self.search_data = '\n'.join([self.wf_name,
                                      self.title]
                                     )

        self.progress = get_progress(
            start=self.start_date,
            finish=self.finish_date) if self.start_date and self.finish_date else 30

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
        try:
            wfi = WFInstance.objects.get(self.db_key)
        except ObjectDoesNotExist:
            wfi = WFInstance()
            wfi.key = self.db_key

        data_from_cache = super(WFCache, self).get()
        if data_from_cache:
            wfi._load_data(data_from_cache, from_db=True)

        return wfi

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
    wf_state = wf_cache.get()  # unicode serialized json to dict, all values are unicode
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
                inv.progress = 20
                inv.save()
            except ObjectDoesNotExist:
                current.log.exception("Invitation not found: %s" % wf_state)
            except MultipleObjectsReturned:
                current.log.exception("Multiple invitations found: %s" % wf_state)
        wfi.step = wf_state['step']
        wfi.name = wf_state['name']
        wfi.pool = wf_state['pool']
        wfi.current_actor_id = str(wf_state['role_id'])  # keys must be str not unicode
        wfi.data = wf_state['data']
        if wf_state['finished']:
            wfi.finished = True
            wfi.finish_date = wf_state['finish_date']
            wf_cache.delete()
        wfi.save()

    else:
        # if cache already cleared, we have nothing to sync
        pass
