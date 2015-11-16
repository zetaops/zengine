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
from zengine.views.base import BaseView, NEXT_CMD_SPLITTER


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


@six.add_metaclass(CRUDRegistry)
class CrudView(BaseView):
    """
    A base class for "Create List Show Update Delete" type of views.



    :type object: Model | None
    """

    # def __init__(self, current=None):
    #     super(CrudView, self).__init__(current)
    #     if current:
    #         self.__call__(current)

    class Meta:
        model = None
        init_view = 'list'
        default_filter = {}
        allow_filters = True
        allow_edit = True
        allow_add = True
        objects_per_page = 20
        title = None
        dispatch = True
        object_workflows = []

    class CrudForm(JsonForm):
        save_list = form.Button("Kaydet ve Listele", cmd="save::list")
        save_edit = form.Button("Kaydet ve Devam Et", cmd="save::edit")

    def __call__(self, current):
        current.log.info("CRUD CALL")
        self.current = current
        self.set_current(current)
        self.create_initial_object()
        self.create_form()
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
        getattr(self, '%s_view' % self.cmd)()
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
        self.form = self.CrudForm(self.object, current=self.current)

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

    def _get_list_obj(self, mdl):
        if self.brief:
            return [mdl.key, unicode(mdl) if six.PY2 else mdl]
        else:
            result = [mdl.key]
            for f in self.object.Meta.list_fields:
                field = getattr(mdl, f)
                if callable(field):
                    result.append(field())
                elif isinstance(field, (datetime.date, datetime.datetime)):
                    result.append(mdl._fields[f].clean_value(field))
                else:
                    result.append(field)
            return result

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

    def _process_list_filters(self, query):
        if self.Meta.default_filter:
            query = query.filter(**self.Meta.default_filter)
        if self.Meta.allow_filters:
            if self.current.request.params:
                query = query.filter(**self.current.request.params)
            if 'filters' in self.input:
                query = query.filter(**self.input['filters'])
        return query

    def _process_list_search(self, query):
        if 'query' in self.input:
            query_string = self.input['query']
            search_string = ' OR '.join(
                ['%s:*%s*' % (f, query_string) for f in self.object.Meta.list_fields])
            return query.raw(search_string)
        return query

    def _is_just_deleted_object(self, obj):
        """
        to compensate riak~solr sync delay, remove just deleted
        object from from object list (if exists)
        """
        if ('deleted_obj' in self.current.task_data and
                    self.current.task_data['deleted_obj'] == obj.key):
            del self.current.task_data['deleted_obj']
            return True

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

    def form_view(self):
        self.output['forms'] = self.form.serialize()
        self.set_client_cmd('form')

    def save_view(self):
        self.object = self.form.deserialize(self.current.input['form'])
        obj_is_new = self.object.is_in_db()
        self.object.save()
        if self.next_cmd and obj_is_new:
            self.current.task_data['added_obj'] = self.object.key

    def delete_view(self):
        # TODO: add confirmation dialog
        if self.next_cmd:  # to overcome 1s riak-solr delay
            self.current.task_data['deleted_obj'] = self.object.key
        self.object.delete()
        del self.current.input['object_id']
        # del self.current.task_data['object_id']

    def object_actions(self, obj):
        pass

    def list_view(self):
        # TODO: add pagination
        self.set_client_cmd('list')
        self.brief = 'brief' in self.input or not self.object.Meta.list_fields
        query = self.object.objects.filter()
        query = self._process_list_filters(query)
        query = self._process_list_search(query)

        self.output['objects'] = []
        self._make_list_header()
        for obj in query:
            if self._is_just_deleted_object(obj):
                continue
            self.output['objects'].append(self._get_list_obj(obj))
        self._add_just_created_object(self.output['objects'])

    def show_view(self):
        self.set_client_cmd('show')
        self.output['object'] = self.form.serialize()['model']
        self.output['object']['key'] = self.object.key

    def list_form_view(self):
        self.form_view()
        self.list_view()
