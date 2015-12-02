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
from zengine import signals

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
        # for key, prop in attrs.items():
        #     if hasattr(prop, 'view_method'):
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


def form_modifier(func):
    """
    To mark a method to work as a modifier for the form output.

    @form_modifier

    :param func: a filter method that takes

    """

    func.form_modifier = True
    return func


def obj_filter(func):
    """
    To mark a method to work as a builder method for the object listings.

    :param func: a filter method that takes object instance and
    result dictionary and modifiec this dict in place
    """
    func.filter_method = True
    return func


def view_method(func):
    """
    marks view methods to use with dynamic dispatching

    :param func: view method
    :return:
    """
    func.view_method = True
    return func


def list_query(func):
    """
    last first only
    query extend
    :param function query_method: query method to be chained. Takes and returns a queryset.
    :return: query_method
    """

    func.query_method = True
    return func


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
            new: new browser window

        """
        allow_search = True
        model = None
        init_view = 'list'
        allow_filters = True
        allow_selection = True
        allow_edit = True
        allow_add = True
        objects_per_page = 8
        title = None
        attributes = {}
        object_actions = [
            {'name': 'Sil', 'cmd': 'delete', 'mode': 'normal', 'show_as': 'button'},
            {'name': 'Düzenle', 'cmd': 'add_edit_form', 'mode': 'normal', 'show_as': 'button'},
            {'fields': [0, ], 'cmd': 'show', 'mode': 'normal', 'show_as': 'link'},
        ]

    class ObjectForm(JsonForm):
        save_edit = form.Button("Kaydet", cmd="save::add_edit_form")
        save_list = form.Button("Kaydet ve Listele", cmd="save::list")
        save_as_new_edit = form.Button("Yeni Olarak Kaydet",
                                       cmd="save_as_new::add_edit_form")
        save_as_new_list = form.Button("Yeni Olarak Kaydet ve Listele",
                                       cmd="save_as_new::list")

    class ListForm(JsonForm):
        add = form.Button("Add", cmd="add_edit_form")

    def __init__(self, current=None):
        self.FILTER_METHODS = []
        self.QUERY_METHODS = []
        self.FORM_MODIFIERS = []
        self.VIEW_METHODS = {}
        super(CrudView, self).__init__(current)

        self.cmd = getattr(self, 'cmd', None) or self.Meta.init_view
        self._prepare_decorated_methods()
        if current:
            current.task_data['cmd'] = self.cmd
            self.create_initial_object()
            self.create_object_form()
            current.log.info('Calling %s.%s(%s)' % (self.__class__.__name__,
                                                    self.cmd, self.object))

            self.output['reload_cmd'] = self.cmd

            self.output['meta'] = {
                'allow_selection': self.Meta.allow_selection,
                'allow_filters': self.Meta.allow_filters,
                'allow_search': self.Meta.allow_search,
                'attributes': self.Meta.attributes,
            }

    def _apply_form_modifiers(self, serialized_form):
        """
        This method will be called by self.form_out() method
        with serialized form data.

        :param dict serialized_form:
        :return:
        """
        for field, prop in serialized_form['schema']['properties'].items():
            # this adds default directives for building
            # add and list views of linked models
            if prop['type'] == 'model':
                prop.update({
                    'add_cmd': 'add_edit_form',
                    'list_cmd': 'select_list',
                    'wf': 'crud',
                })
            # overriding widget type of Permissions ListNode
            if field == 'Permissions':
                prop['widget'] = 'filter_interface'

        for method in self.FORM_MODIFIERS:
            method.filter_func(self, serialized_form)

    def form_out(self, _form=None):
        """
        renders form. applies modifier method then outputs the result

        :param JsonForm _form: JsonForm object
        """
        _form = _form or self.object_form
        self.output['forms'] = _form.serialize()
        self._apply_form_modifiers(self.output['forms'])
        self.set_client_cmd('form')

    def _prepare_decorated_methods(self):
        """
        collects various methods in to their related lists
        TODO: To decrease the overhead, this will be moved to metaclass of CrudView (CRUDRegistry)
        :return:
        """
        items = list(self.__class__.__dict__.items())
        for base in self.__class__.__bases__:
            items.extend(list(base.__dict__.items()))
        for name, func in items:
            if hasattr(func, 'view_method'):
                self.VIEW_METHODS[name] = func
            elif hasattr(func, 'form_modifier'):
                self.FORM_MODIFIERS.append(func)
            elif hasattr(func, 'filter_method'):
                self.FILTER_METHODS.append(func)
            elif hasattr(func, 'query_method'):
                self.QUERY_METHODS.append(func)

    def call(self):
        """
        this method act as a method dispatcher
        for non-wf based flow handling
        """
        self.check_for_permission()
        self.VIEW_METHODS[self.cmd](self)
        self.current.task_data['cmd'] = self.next_cmd

    def check_for_permission(self):
        """
        since wf task has their own perm. checker,
        this method called only by "call()" dispatcher
        """
        permission = "%s.%s" % (self.object.__class__.__name__, self.cmd)
        log.debug("CHECK CRUD PERM: %s" % permission)
        if (self.current.task_type in NO_PERM_TASKS_TYPES or
                    permission in settings.ANONYMOUS_WORKFLOWS):
            return
        if not self.current.has_permission(permission):
            raise falcon.HTTPForbidden("Permission denied",
                                       "You don't have required CRUD permission: %s" % permission)

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
        elif 'added_obj' in self.current.task_data:
            self.object = self.model_class(self.current).objects.get(
                    self.current.task_data['added_obj'])
        else:
            self.object = self.model_class(self.current)

    def get_selected_objects(self):
        return {self.model_class(self.current).get(itm_key)
                for itm_key in self.input['selected_items']}

    def _make_list_header(self):
        if self.object.Meta.list_fields:
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
        filters = self.Meta.allow_filters and self.input.get('filters') or self.req.params
        if filters:
            return query.filter(**filters)
        else:
            return query

    @list_query
    def _process_list_search(self, query):
        q = self.Meta.allow_search and (self.input.get('query') or self.req.params.get('query'))
        return query.raw(' OR '.join(
                ['%s:*%s*' % (f, q) for f in self.object.Meta.list_fields])) if q else query

    @obj_filter
    def _get_list_obj(self, obj, result):

        fields = self.object.Meta.list_fields
        if fields:
            for f in self.object.Meta.list_fields:
                field = getattr(obj, f)
                if callable(field):
                    result['fields'].append(field())
                else:
                    result['fields'].append(obj.get_humane_value(f))
        else:
            result['fields'] = [six.text_type(obj)]

    def _parse_object_actions(self, obj):
        """
        applies registered object filter methods
        :param obj: pyoko model instance
        :return: (obj, result) model instance
        """
        result = {'key': obj.key, 'fields': [], 'do_list': True,
                  'actions': self.Meta.object_actions[:]}
        for method in self.FILTER_METHODS:
            method(self, obj, result)
        return result

    def _apply_list_queries(self, query):
        """
        applies registered query methods
        :param query: queryset
        """
        for f in self.QUERY_METHODS:
                query = f(self, query)
        return query

    @obj_filter
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

    @list_query
    def _handle_list_pagination(self, query):
        current_page = int(self.current.input.get('page', 1))
        per_page = self.Meta.objects_per_page
        total_objects = query.count()
        total_pages = total_objects / per_page or 1
        # add orphans to last page
        current_per_page = per_page + (
        total_objects % per_page if current_page == total_pages else 0)
        self.output["pagination"] = dict(page=current_page,
                                         total_pages=total_pages,
                                         total_objects=total_objects,
                                         per_page=current_per_page)
        query = query.set_params(rows=current_per_page, start=(current_page - 1) * per_page)
        return query

    @view_method
    def list(self):

        query = self._apply_list_queries(self.object.objects.filter())

        self.output['objects'] = []
        self._make_list_header()
        new_added_key = self.current.task_data.get('added_obj')
        new_added_listed = False
        for obj in query:
            new_added_listed = obj.key == new_added_key
            list_obj = self._parse_object_actions(obj)
            list_obj['actions'] = sorted(list_obj['actions'], key=lambda x: x.get('name', 0))
            if list_obj['do_list']:
                self.output['objects'].append(list_obj)
        self._add_just_created_object(new_added_key, new_added_listed)
        title = getattr(self.object.Meta, 'verbose_name_plural', self.object.__class__.__name__)
        self.form_out(self.ListForm(current=self.current, title=title))

    @view_method
    def select_list(self):
        """
        creates a brief object list to fill the select boxes
        :return: [object_name_1 ...]
        """
        query = self.object.objects.filter()
        self.output['objects'] = [{'key': obj.key, 'value': six.text_type(obj)}
                                  for obj in self.object.objects.filter()]

    @view_method
    def show(self):
        self.set_client_cmd('show')
        self.output['object'] = self.object_form.serialize(readable=True)['model']
        self.output['object']['key'] = self.object.key

    @view_method
    def list_form(self):
        self.list()
        self.form()

    @view_method
    def add_edit_form(self):
        self.form_out()
        # self.output['forms'] = self.object_form.serialize()
        # self.set_client_cmd('form')

    def set_form_data_to_object(self):
        self.object = self.object_form.deserialize(self.current.input['form'])

    @view_method
    def save_as_new(self):
        self.set_form_data_to_object()
        self.object.key = None
        self.object.save()
        self.current.task_data['object_id'] = self.object.key

    @view_method
    def save(self):
        signals.crud_pre_save.send(self, current=self.current, object=self.object)
        self.set_form_data_to_object()
        obj_is_new = not self.object.is_in_db()
        self.object.save()
        signals.crud_post_save.send(self, current=self.current, object=self.object)
        if self.next_cmd and obj_is_new:
            self.current.task_data['added_obj'] = self.object.key

    @view_method
    def delete(self):
        # TODO: add confirmation dialog
        # to overcome 1s riak-solr delay
        signals.crud_pre_delete.send(self, current=self.current, object=self.object)
        self.current.task_data['deleted_obj'] = self.object.key
        if 'object_id' in self.current.task_data:
            del self.current.task_data['object_id']
        object_data = self.object._data
        self.object.delete()
        signals.crud_post_delete.send(self, current=self.current, object_data=object_data)
        self.set_client_cmd('reload')
