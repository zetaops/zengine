# -*-  coding: utf-8 -*-
"""Base view classes"""
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import datetime
import falcon
from falcon import HTTPNotFound
import six
from pyoko import form
from pyoko.conf import settings
from pyoko.model import Model, model_registry
from zengine.auth.permissions import NO_PERM_TASKS_TYPES
from zengine.lib.forms import JsonForm
from zengine.log import log
from zengine.views.base import BaseView


# GENERIC_COMMANDS = ['edit', 'add', 'update', 'list', 'delete', 'do', 'show', 'save']


class CRUDRegistry(type):
    registry = {}
    _meta = None

    def __new__(mcs, name, bases, attrs):
        if name == 'CrudView':
            CRUDRegistry._meta = attrs['Meta']
        else:
            CRUDRegistry.registry[mcs.__name__] = mcs
            if 'Meta' not in attrs:
                attrs['Meta'] = type('Meta', (object,), CRUDRegistry._meta.__dict__)
            else:
                for k, v in CRUDRegistry._meta.__dict__.items():
                    if k not in attrs['Meta'].__dict__:
                        setattr(attrs['Meta'], k, v)
        new_class = super(CRUDRegistry, mcs).__new__(mcs, name, bases, attrs)
        return new_class

    @classmethod
    def get_permissions(cls):
        perms = []
        for kls_name, kls in cls.registry.items():
            for method_name in cls.__dict__.keys():
                if method_name.endswith('_view'):
                    perms.append("%s.%s" % (kls_name, method_name))
        return perms


def obj_filter(func):
    func.filter_method = True
    return func


def view_method(func):
    func.view_method = True
    return func


def list_query(func):
    func.query_method = True
    return func

@six.add_metaclass(CRUDRegistry)
class CrudView(BaseView):
    """
    A base class for "Create List Show Update Delete" type of views.
    """

    FILTER_METHODS = []
    VIEW_METHODS = {}
    QUERY_METHODS = []

    def __init__(self, current=None):
        super(CrudView, self).__init__(current)
        for name, func in self.__class__.__dict__.items():
            if hasattr(func, 'view_method'):
                self.VIEW_METHODS[name] = func
            elif hasattr(func, 'filter_method'):
                self.FILTER_METHODS.append(func)
            elif hasattr(func, 'query_method'):
                self.QUERY_METHODS.append(func)
        pass

    class Meta:
        model = None
        init_view = 'list'
        allow_filters = True
        allow_edit = True
        allow_add = True
        objects_per_page = 20
        title = None
        dispatch = True
        object_actions = []

    class CrudForm(JsonForm):
        save_list = form.Button("Kaydet ve Listele", cmd="save::list")
        save_edit = form.Button("Kaydet ve Devam Et", cmd="save::edit")

    def _init(self, current):
        """
        prepare
        :param current:
        """
        self.set_current(current)
        self.create_initial_object()
        self.create_form()

    def __call__(self, current):
        current.log.info("CRUD CALL")
        self._init(current)
        if not self.cmd:
            self.cmd = self.Meta.init_view
            current.task_data['cmd'] = self.cmd
        self.check_for_permission()
        current.log.info('Calling %s_view of %s' % ((self.cmd or 'list'),
                                                    self.object.__class__.__name__))
        self.client_cmd = set()
        self.output['meta'] = {
            'allow_filters': self.Meta.allow_filters,
            'allow_edit': self.Meta.allow_edit,
            'allow_add': self.Meta.allow_add
        }
        if self.Meta.dispatch:
            # getattr(self, '%s_view' % self.cmd)()
            self.VIEW_METHODS[self.cmd](self)
        if self.next_cmd:
            self.current.task_data['cmd'] = self.next_cmd

    def set_client_cmd(self, cmd):
        self.client_cmd.add(cmd)
        self.output['client_cmd'] = list(self.client_cmd)

    def check_for_permission(self):
        permission = "%s.%s" % (self.object.__class__.__name__, self.cmd)
        log.debug("CHECK CRUD PERM: %s" % permission)
        if (self.current.task_type in NO_PERM_TASKS_TYPES or
                    permission in settings.ANONYMOUS_WORKFLOWS):
            return
        if not self.current.has_permission(permission):
            raise falcon.HTTPForbidden("Permission denied",
                                       "You don't have required model permission: %s" % permission)

    def create_form(self):
        self.object_form = self.CrudForm(self.object, current=self.current)

    def get_model_class(self):
        model = self.Meta.model if self.Meta.model else self.current.input['model']
        if isinstance(model, Model):
            return model
        else:
            return model_registry.get_model(model)

    def create_initial_object(self):
        model_class = self.get_model_class()
        object_id = self.input.get('object_id')
        if not object_id and 'form' in self.input:
            object_id = self.input['form'].get('object_key')
        if object_id:
            try:
                self.object = model_class(self.current).objects.get(object_id)
                if self.object.deleted:
                    raise HTTPNotFound()
            except:
                raise HTTPNotFound()
        else:
            self.object = model_class(self.current)

    def _make_list_header(self):
        if not self.brief:  # add list headers
            list_headers = []
            for f in self.object.Meta.list_fields:
                if callable(getattr(self.object, f)):
                    list_headers.append(getattr(self.object, f).title)
                else:
                    list_headers.append(self.object._fields[f].title)
            self.output['objects'].append(list_headers)
        else:
            self.output['objects'].append('-1')

    @list_query
    def _process_list_filters(self, query):
        if self.Meta.allow_filters:
            if self.current.request.params:
                query = query.filter(**self.current.request.params)
            if 'filters' in self.input:
                query = query.filter(**self.input['filters'])
        return query

    @list_query
    def _process_list_search(self, query):
        if 'query' in self.input:
            query_string = self.input['query']
            search_string = ' OR '.join(
                ['%s:*%s*' % (f, query_string) for f in self.object.Meta.list_fields])
            return query.raw(search_string)
        return query

    @view_method
    def form(self):
        self.output['forms'] = self.object_form.serialize()
        self.set_client_cmd('form')

    @view_method
    def save(self):
        self.object = self.object_form.deserialize(self.current.input['form'])
        obj_is_new = self.object.is_in_db()
        self.object.save()
        if self.next_cmd and obj_is_new:
            self.current.task_data['added_obj'] = self.object.key

    @view_method
    def delete(self):
        # TODO: add confirmation dialog
        if self.next_cmd:  # to overcome 1s riak-solr delay
            self.current.task_data['deleted_obj'] = self.object.key
        self.object.delete()
        del self.current.input['object_id']
        # del self.current.task_data['object_id']

    @obj_filter
    def _get_list_obj(self, obj, result):
        if self.brief:
            result['fields'].append(unicode(obj) if six.PY2 else obj)
            return obj, result
        else:
            for f in self.object.Meta.list_fields:
                field = getattr(obj, f)
                if callable(field):
                    result['fields'].append(field())
                elif isinstance(field, (datetime.date, datetime.datetime)):
                    result['fields'].append(obj._fields[f].clean_value(field))
                else:
                    result['fields'].append(field)
            return obj, result

    def _parse_object_actions(self, obj):
        result = {'key': obj.key, 'fields': [], 'do_list': True}
        for f in self.FILTER_METHODS:
            obj, result = f(self, obj, result)
            if not result:
                return obj, False
        return obj, result

    def _apply_list_queries(self, query):
        for f in self.QUERY_METHODS:
            query = f(self, query)
        return query

    @obj_filter
    def remove_just_deleted_object(self, obj, result):
        """
        to compensate riak~solr sync delay, remove just deleted
        object from from object list (if exists)
        """
        if ('deleted_obj' in self.current.task_data and
                    self.current.task_data['deleted_obj'] == obj.key):
            del self.current.task_data['deleted_obj']
            result['do_list'] = False

        return obj, result

    def _add_just_created_object(self, objects):
        """
        to compensate riak~solr sync delay, add just created
        object to the object list
        :param objects:
        """
        if 'added_obj' in self.current.task_data:
            key = self.current.task_data['added_obj']
            if not any([o[0] == key for o in objects]):
                obj = self.object.objects.get(key)
                self.output['objects'].insert(1, self._get_list_obj(obj))
                del self.current.task_data['added_obj']

    @view_method
    def list(self):
        # TODO: add pagination
        self.set_client_cmd('list')
        self.brief = 'brief' in self.input or not self.object.Meta.list_fields
        query = self._apply_list_queries(self.object.objects.filter())
        self.output['objects'] = []
        self._make_list_header()
        for obj in query:
            obj, list_obj = self._parse_object_actions(obj)
            if list_obj['do_list']:
                self.output['objects'].append(list_obj)
        self._add_just_created_object(self.output['objects'])

    @view_method
    def show(self):
        self.set_client_cmd('show')
        self.output['object'] = self.object_form.serialize()['model']
        self.output['object']['key'] = self.object.key

    @view_method
    def list_form(self):
        self.form()
        self.list()
