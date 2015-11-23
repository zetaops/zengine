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


def obj_filter(cond_func=None):
    """
    To mark a method to work as a builder method for the object listings.

    @obj_filter
    or
    @obj_filter(lambda o: o.status > 2)
    to only apply the decorated method if obj.status higher than 2


    :param func: a filter method that takes object instance and result dictionary and returns same
    (but probably modified) dictionary
    :param function cond_func: if defined, this should return True to run the *func*


    """

    def obj_filter_decorator(func):
        func.filter_method = True
        func.filter_func = cond_func
        return func

    return obj_filter_decorator


def view_method(func):
    """
    marks view methods to use with dynamic dispatching

    :param func: view method
    :return:
    """
    func.view_method = True
    return func


def list_query(cond_func=None):
    """
    last first only
    query extend
    :param function cond_func: if defined, this should return True to run the *func*
    :param function query_method: query method to be chained. Takes and returns a queryset.
    :return: query_method
    """

    def list_query_decorator(query_method):
        query_method.query_method = True
        query_method.filter_func = cond_func
        return query_method

    return list_query_decorator


@six.add_metaclass(CRUDRegistry)
class CrudView(BaseView):
    """
    A base class for "Create List Show Update Delete" type of views.
    """




    class Meta:
        """
        attributes
        ----------------
        To customize form fields
        attributes = {
           # field_name    attrib_name   value(s)
            'kadro_id': [('filters', {'durum': 1}), ]

        }



        object_actions
        ----------------

        List of dicts.
        {'name': '', 'cmd': '', 'mode': '', 'show_as': ''},

        name: Name of action, not used when "show_as" set to "link".

        cmd: Command to be run. Should not be used in conjunction with "wf".

        wf: Workflow to be run. Should not be used in conjunction with "cmd".

        show_as:
            "button",
            "context_menu" appends to context_menu of the row
            "group_action". appends to actions drop down menu
            "link" this option expects "fields" param with index numbers
            of fields to be shown  as links.

        mode:
            various values can be given to define how to run an activity
            normal: open in same window
            modal: open in modal window
            bg: run in bg (for wf's that doesn't contain user interaction)
            new: new browser window

        """
        allow_search = True
        model = None
        init_view = 'list'
        allow_filters = True
        allow_selection = True
        allow_edit = True
        allow_add = True
        objects_per_page = 20
        title = None
        attributes = {}
        object_actions = [
            {'name': 'Sil', 'cmd': 'delete', 'mode': 'bg', 'show_as': 'button'},
            {'name': 'Düzenle', 'cmd': 'add_edit_form', 'mode': 'normal', 'show_as': 'button'},
            {'fields': [0, ], 'cmd': 'show', 'mode': 'normal', 'show_as': 'link'},
        ]

    class ObjectForm(JsonForm):
        save_list = form.Button("Kaydet ve Listele", cmd="save::list")
save_edit = form.Button("Kaydet ve Devam Et", cmd="save::add_edit_form")

    class ListForm(JsonForm):
        add = form.Button("Add", cmd="form")

    def _prepare_decorated_method(self):
        self.FILTER_METHODS = []
        self.VIEW_METHODS = {}
        self.QUERY_METHODS = []
        for name, func in self.__class__.__dict__.items():
            if hasattr(func, 'view_method'):
                self.VIEW_METHODS[name] = func
            elif hasattr(func, 'filter_method'):
                self.FILTER_METHODS.append(func)
            elif hasattr(func, 'query_method'):
                self.QUERY_METHODS.append(func)

    def __init__(self, current=None):
        super(CrudView, self).__init__(current)
        self.cmd = self.cmd or self.Meta.init_view
        current.task_data['cmd'] = self.cmd
        self._prepare_decorated_method()
        self.create_initial_object()
        self.create_object_form()
        self.output['reload_cmd'] = self.cmd
        current.log.info('Calling %s.%s(%s)' % (self.__class__.__name__, self.cmd, self.object))
        self.client_cmd = set()
        self.output['meta'] = {
            'allow_selection': self.Meta.allow_selection,
            'allow_filters': self.Meta.allow_filters,
            'allow_search': self.Meta.allow_search,
            'attributes': self.Meta.attributes,
        }

    def __call__(self,):
        self.VIEW_METHODS[self.cmd](self)
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

    def create_object_form(self):
        self.object_form = self.ObjectForm(self.object, current=self.current)

    def get_model_class(self):
        model = self.Meta.model if self.Meta.model else self.current.input['model']
        if isinstance(model, Model):
            return model
        else:
            return model_registry.get_model(model)

    def create_initial_object(self):
        self.model_class = self.get_model_class()
        object_id = self.current.task_data.get('object_id')
        if not object_id and 'form' in self.input:
            object_id = self.input['form'].get('object_key')
        if object_id and object_id != self.current.task_data.get('deleted_obj'):
            try:
                self.object = self.model_class(self.current).objects.get(object_id)
                if self.object.deleted:
                    raise HTTPNotFound()
            except:
                raise HTTPNotFound()
        else:
            self.object = self.model_class(self.current)

    def get_selected_objects(self):
        return {self.model_class(self.current).get(itm_key)
                for itm_key in self.input['selected_items']}

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

    @list_query()
    def _process_list_filters(self, query):
        filters = self.Meta.allow_filters and self.input.get('filters') or self.req.params
        filters and query.filter(**filters)

    @list_query()
    def _process_list_search(self, query):
        q = self.Meta.allow_search and (self.input.get('query') or self.req.params.get('query'))
        q and query.raw(' OR '.join(['%s:*%s*' % (f, q) for f in self.object.Meta.list_fields]))

    @obj_filter()
    def _get_list_obj(self, obj, result):
        if self.brief:
            result['fields'].append(unicode(obj) if six.PY2 else obj)
        else:
            for f in self.object.Meta.list_fields:
                field = getattr(obj, f)
                if callable(field):
                    result['fields'].append(field())
                elif isinstance(field, (datetime.date, datetime.datetime)):
                    result['fields'].append(obj._fields[f].clean_value(field))
                else:
                    result['fields'].append(field)

    def _parse_object_actions(self, obj):
        """
        applies registered object filter methods
        :param obj: pyoko model instance
        :return: (obj, result) model instance
        """
        result = {'key': obj.key, 'fields': [], 'do_list': True,
                  'actions': self.Meta.object_actions[:]}
        for method in self.FILTER_METHODS:
            (not method.filter_func or method.filter_func()) and method(self, obj, result)
        return result

    def _apply_list_queries(self, query):
        """
        applies registered query methods
        :param query: queryset
        """
        for f in self.QUERY_METHODS:
            if not f.filter_func or f.filter_func():
                f(self, query)
        return query

    @obj_filter()
    def _remove_just_deleted_object(self, obj, result):
        """
        to compensate riak~solr sync delay, remove just deleted
        object from from object list (if exists)

        :param obj: pyoko Model instance
        :param dict result: {'key': obj.key, 'fields': [],
                          'do_list': True, 'actions': self.Meta.object_actions}

        :return: result
        """
        if ('deleted_obj' in self.current.task_data and
                    self.current.task_data['deleted_obj'] == obj.key):
            del self.current.task_data['deleted_obj']
            result['do_list'] = False

    def _add_just_created_object(self, new_added_key, new_added_listed):
        """
        to compensate riak~solr sync delay, add just created
        object to the object list
        :param objects:
        """
        if new_added_key and not new_added_listed:
            obj = self.object.objects.get(new_added_key)
            list_obj = self._parse_object_actions(obj)
            if list_obj['do_list']:
                self.output['objects'].append(list_obj)

    @view_method
    def list(self):
        # TODO: add pagination

        self.set_client_cmd('form')
        self.brief = 'brief' in self.input or not self.object.Meta.list_fields
        query = self._apply_list_queries(self.object.objects.filter())
        self.output['objects'] = []
        self._make_list_header()
        new_added_key = self.current.task_data.get('added_obj')
        new_added_listed = False
        for obj in query:
            new_added_listed = obj.key == new_added_key
            list_obj = self._parse_object_actions(obj)
            if list_obj['do_list']:
                self.output['objects'].append(list_obj)
        self._add_just_created_object(new_added_key, new_added_listed)
        self.output['forms'] = self.ListForm(current=self.current).serialize()

    @view_method
    def show(self):
        self.set_client_cmd('show')
        self.output['object'] = self.object_form.serialize()['model']
        self.output['object']['key'] = self.object.key

    @view_method
    def list_form(self):
        self.list()
        self.form()

    @view_method
    def add_edit_form(self):
        self.output['forms'] = self.object_form.serialize()
        self.set_client_cmd('form')

    def set_form_data_to_object(self):
        self.object = self.object_form.deserialize(self.current.input['form'])

    @view_method
    def save(self):
        self.set_form_data_to_object()
        obj_is_new = not self.object.is_in_db()
        self.object.save()
        if self.next_cmd and obj_is_new:
            self.current.task_data['added_obj'] = self.object.key

    @view_method
    def delete(self):
        # TODO: add confirmation dialog
        # to overcome 1s riak-solr delay
        self.current.task_data['deleted_obj'] = self.object.key
        if 'object_id' in self.current.task_data:
            del self.current.task_data['object_id']
        self.object.delete()
        self.set_client_cmd('reload')
