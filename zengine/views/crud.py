# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
"""
This module holds CrudView and related classes that helps building
CRUDS (Create Read Update Delete Search) type of views.
"""
from collections import OrderedDict
from operator import attrgetter

import six

from pyoko.conf import settings
from pyoko.exceptions import ObjectDoesNotExist
from pyoko.model import Model, model_registry
from zengine import signals
from zengine.auth.permissions import PERM_REQ_TASK_TYPES
from zengine.dispatch.dispatcher import receiver
from zengine import forms
from zengine.forms import fields
from zengine.lib.cache import Cache
from zengine.lib.exceptions import HTTPError
from zengine.lib.utils import date_to_solr, gettext_lazy as _
from zengine.log import log
from zengine.signals import crud_post_save
from zengine.views.base import BaseView


class ListForm(forms.JsonForm):
    """
    Holds list view form elements.

    Used by CrudMeta metaclass to create distinct
    copies for each subclass of CrudView.
    """
    add = fields.Button(_("Add"), cmd="add_edit_form")


class ObjectForm(forms.JsonForm):
    """
    Holds object add / edit form elements.

    Used by CrudMeta metaclass to create distinct
    copies for each subclass of CrudView.
    """
    save_edit = fields.Button(_(u"Save"), cmd="save::add_edit_form")
    save_list = fields.Button(_(u"Save and List"), cmd="save::list")
    save_as_new_edit = fields.Button(_(u"Save as New"),
                                     cmd="save_as_new::add_edit_form")
    save_as_new_list = fields.Button(_(u"Save as New and List"),
                                     cmd="save_as_new::list")


class DeletionConfirmForm(forms.JsonForm):
    """
    """
    cancel = fields.Button(_(u"Cancel"), cmd="list")
    confirm = fields.Button(_(u"Confirm"), cmd="delete")


class CrudMeta(type):
    """
    Meta class that prepares CrudView's subclasses.

    Handles passing of default "Meta" class attributes and
    List/Object forms into subclasses.
    """
    registry = {}
    _meta = None

    def __new__(mcs, name, bases, attrs):
        # for key, prop in attrs.items():
        #     if hasattr(prop, 'view_method'):
        attrs['ListForm'] = type('ListForm', (ListForm,), dict(ListForm.__dict__))
        attrs['ObjectForm'] = type('ObjectForm', (ObjectForm,), dict(ObjectForm.__dict__))
        if name == 'CrudView':
            CrudMeta._meta = attrs['Meta']
        else:
            CrudMeta.registry[mcs.__name__] = mcs
            if 'Meta' not in attrs:
                attrs['Meta'] = type('Meta', (object,), dict(CrudMeta._meta.__dict__))
            else:
                for k, v in CrudMeta._meta.__dict__.items():
                    if k not in attrs['Meta'].__dict__:
                        setattr(attrs['Meta'], k, v)

        new_class = super(CrudMeta, mcs).__new__(mcs, name, bases, attrs)
        return new_class

    @classmethod
    def get_permissions(cls):
        """
        Generates permissions for all CrudView based class methods.

        Returns:
            List of Permission objects.
        """
        perms = []
        for kls_name, kls in cls.registry.items():
            for method_name in cls.__dict__.keys():
                if method_name.endswith('_view'):
                    perms.append("%s.%s" % (kls_name, method_name))
        return perms


def obj_filter(func):
    """
    Decorator for marking a method to work as a builder method for the object listings.

    Args:
        func (function): a filter method that takes object instance and
    result dictionary and modifies that result dict in place.

    .. code-block:: python

        @obj_filter
        def foo(self, obj, result):
            if obj.status < self.CONFIRMED:
                result['actions'].append(
                        {'name': 'Confirm', 'cmd': 'confrim', 'show_as': 'button'})
    """
    func.filter_method = True
    return func


def view_method(func):
    """
    Decorator for marking view methods to be used with dynamic
    dispatcher :py:attr:`~zengine.views.crud.CrudView.call`.

    Note:
        Dynamic dispaching mainly used for auto-generated model
        based CRUD views. In this mode, methods called according
        to current "cmd".

    Args:
        func (function): A view method that will be called by
         :py:attr:`~zengine.views.crud.CrudView.call`
         dispatcher method.
    """
    func.view_method = True
    return func


def list_query(func):
    """
    To manipulate list querysets

    Args:
        func (function): Query method to be chained. Takes and returns a queryset.

    .. code-block:: python

        @list_query
        def foo(self, queryset):
            queryset = queryset.filter(**{'%s__in' % field:
                                        self.input['filter']['values']})
            return queryset
    """

    func.query_method = True
    return func


class SelectBoxCache(Cache):
    """
    Cache object for queries that will be made to fill auto-complete
    select boxes of relations.
    """
    PREFIX = 'MDLST'

    def __init__(self, model_name, query=''):
        super(SelectBoxCache, self).__init__(model_name, query)


@receiver(crud_post_save)
def clear_model_list_cache(sender, *args, **kwargs):
    """
    Invalidate permission cache on crud updates on Role and AbstractRole models
    """
    SelectBoxCache.flush(sender.model_class.__name__)


@six.add_metaclass(CrudMeta)
class CrudView(BaseView):
    """
    A base class for "Create List Show Update Delete" type of
    views that works primarily on one model.

    While it's possible to get model's name from client input
    (`self.current.input['model']`) usually subclasses of
    CrudView explicitly define the name of their primary model's
    name in :class:`~zengine.views.crud.CrudView.Meta.model` Meta class variable.
    """

    class Meta:
        """
        Attributes of this class defines the client side and backend
        behaviour of CrudView instances.

        Attributes:

            model (str): Name of the model to work on.
             self.current.input['model'] will be used if not defined.
            object_actions ({}): A dict that will be passed to client
             for each list item.

                .. code-block:: python

                    object_actions = {'code_name_of_action':
                        {'name': '', 'cmd': '', 'mode': '', 'show_as': ''},
                    }
                    '''
                    name: Visible name of action, useless when "show_as" set to "link".

                    cmd: Command to be run. Should not be used in conjunction with "wf".

                    wf: Workflow to be run. Should not be used in conjunction with "cmd".

                    object_key: Defaults to "object_id". To bypass automatic object fetching,
                    override this with any value.

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
                    '''
            init_view (str): Default view for dispatcher (call) mode.
            allow_search (bool): Enables or disables search feature.
            allow_filters (bool): Enables or disables filters.
            allow_selection (bool): Enables or disables selection of items on object list.
            objects_per_page (int): Number of items per object list page.


        """
        allow_search = True
        model = None
        init_view = 'list'
        allow_filters = True
        allow_selection = False
        objects_per_page = 10
        object_actions = {
            'delete': {'name': _(u'Delete'), 'cmd': 'confirm_deletion', 'mode': 'normal',
                       'show_as': 'button'},
            'add_edit_form': {'name': _(u'Edit'), 'cmd': 'add_edit_form', 'mode': 'normal',
                              'show_as': 'button'},
            'show': {'fields': [0, ], 'cmd': 'show', 'mode': 'normal', 'show_as': 'link'},
        }

    class ObjectForm(forms.JsonForm):
        """
        Default ObjectForm for CrudViews. Can be overridden.
        """
        save_edit = fields.Button(_(u"Save"), cmd="save::add_edit_form")
        save_list = fields.Button(_(u"Save and List"), cmd="save::list")
        if settings.DEBUG:
            save_as_new_edit = fields.Button(_(u"Save as New"),
                                             cmd="save_as_new::add_edit_form")
            save_as_new_list = fields.Button(_(u"Save as New and List"),
                                             cmd="save_as_new::list")

    def __init__(self, current=None):
        self.FILTER_METHODS = []
        self.QUERY_METHODS = []
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
                'allow_search': self.Meta.allow_search and bool(self.object.Meta.search_fields),
            }

    def _prepare_decorated_methods(self):
        """
        Collects decorated methods into their related lists.
        """
        # TODO: Move this to CrudMeta for decrease the overhead of init.
        items = list(self.__class__.__dict__.items())
        for base in self.__class__.__bases__:
            items.extend(list(base.__dict__.items()))
        for name, func in items:
            if hasattr(func, 'view_method'):
                self.VIEW_METHODS[name] = func
            elif hasattr(func, 'filter_method'):
                self.FILTER_METHODS.append(func)
            elif hasattr(func, 'query_method'):
                self.QUERY_METHODS.append(func)

    def call(self):
        """
        This method act as a method dispatcher for non-WF
        based flow handling. Mainly used for auto-generated
        CRUD views.
        """
        self.check_for_permission()
        self.VIEW_METHODS[self.cmd](self)
        self.current.task_data['cmd'] = self.next_cmd

    def check_for_permission(self):
        """
        Checks permissions of auto-generated CRUD views.

        Required permissions calculated according to
        ``ModelName . self.cmd`` scheme.

        """
        permission = "%s.%s" % (self.object.__class__.__name__, self.cmd)
        log.debug("CHECK CRUD PERM: %s" % permission)
        if (self.current.task_type not in PERM_REQ_TASK_TYPES or
                    permission in settings.ANONYMOUS_WORKFLOWS):
            return
        if not self.current.has_permission(permission):
            raise HTTPError(403, "You don't have required CRUD permission: %s" % permission)

    def create_object_form(self):
        """
        Creates an instance of :attr:`ObjectForm` and
        assigns it to ``self.object_form``.

        Can be overridden to easily replace the default
        ObjectForm.
        """
        self.object_form = self.ObjectForm(self.object, current=self.current)

    def get_model_class(self):
        """
        Looks for the default model of this view from
        :py:attr:`Meta.model`. If it's not set, tries to get
        model name from ``current.input['model']``.

        Can be overridden to implement different model
        selection mechanism.

        Returns:
            :py:attr:`~pyoko.models.Model` class.
        """
        try:
            model = self.Meta.model if self.Meta.model else self.current.input['model']
            if isinstance(model, Model):
                return model
            else:
                return model_registry.get_model(model)
        except:
            log.debug('No "model" given for CrudView')
            return None

    def create_initial_object(self):
        """
        Creates an instance of default (or selected) model.

        If an existing objects key found in

        ``current.input['object_id']``

        or

        ``current.task_data['object_id']``

        or

        ``current.input['form']['object_key']``


        then it will be retrieved from DB and assigned to ``self.object``.
        """
        self.model_class = self.get_model_class()
        if self.model_class:
            object_id = self.current.task_data.get('object_id')
            if not object_id and 'form' in self.input:
                object_id = self.input['form'].get('object_key', None)
                if object_id:
                    form_model_type = self.input['form'].get('model_type', None)
                    if form_model_type != self.model_class.__name__:
                        object_id = None
            if object_id:
                try:
                    self.object = self.model_class(self.current).objects.get(object_id)
                except ObjectDoesNotExist:
                    raise HTTPError(404, "Possibly you are trying to retrieve a just deleted "
                                         "object or object key (%s) does not belong to current model:"
                                         " %s" % (object_id, self.model_class.__name__))
                except:
                    raise
            # elif 'added_obj' in self.current.task_data:
            #     self.object = self.model_class(self.current).objects.get(
            #             self.current.task_data['added_obj'])
            else:
                self.object = self.model_class(self.current)
        else:
            self.object = type('FakeModel', (Model,), {})()

    def get_selected_objects(self):
        """
        An iterator for object instances of selected list items.

        Yields:
            :class:`Model<pyoko:pyoko.model.Model>` instance.
        """
        return {self.model_class(self.current).get(itm_key)
                for itm_key in self.input['selected_items']}

    def make_list_header(self, **kwargs):
        """
        Sets header row of object list.

        First item of ``output['objects']`` list used as header.
        If it's not defined to which fields to be used in object
        listing, then no header is set and first item set to ``-1``.
        """
        list_fields = kwargs.get('list_fields', self.object.Meta.list_fields)
        if list_fields:
            list_headers = []
            for f in list_fields:
                if callable(getattr(self.object, f, None)):
                    list_headers.append(getattr(self.object, f).title)
                elif "." in f:
                    def attribute_name(obj, lst):
                        i = 0
                        cls = obj.get_link(field=lst[i])['mdl']
                        if not hasattr(attrgetter(lst[i + 1])(cls), "get_link"):
                            list_headers.append(cls.get_field(lst[i + 1]).title)
                        else:
                            try:
                                return attribute_name(cls, lst=lst[i + 1:])
                            except IndexError:
                                cls = attrgetter(lst[i + 1])(cls).__class__
                                list_headers.append(cls.Meta.verbose_name_plural)

                    attribute_name(self.object, f.split("."))

                else:
                    list_headers.append(self.object.get_field(f).title)
            self.output['objects'].append(list_headers)
        else:
            self.output['objects'].append('-1')

    @list_query
    def _apply_list_filters(self, queryset):
        """
        Applies client filters to object listing queryset.

        Args:
            queryset (:class:`QuerySet<pyoko:pyoko.db.queryset.QuerySet>`):
                Object listing queryset.

        Returns:
            queryset (:class:`QuerySet<pyoko:pyoko.db.queryset.QuerySet>`):
                Object listing queryset.
        Example:

        .. code-block:: javascript

            filters: {
                ulke: {values: ["1", "2"], type: "check"},
                kurum_disi_gorev_baslama_tarihi: {
                    values: ["20.01.2016", null], type: "date"
                    }
                ulke: {values: ["1", "2"], type: "check"}
                }

        """
        filters = self.input.get('filters') if self.Meta.allow_filters else {}
        if filters:
            for field, filter in filters.items():
                if filter.get('type') == 'date':
                    start = date_to_solr(filter['values'][0])
                    end = date_to_solr(filter['values'][1])
                    queryset = queryset.filter(**{'%s__range' % field: (start, end)})
                else:
                    queryset = queryset.filter(**{'%s__in' % field: filter['values']})
        return queryset

    @list_query
    def _apply_list_search(self, query):
        """
        Applies search queries to object listing queryset.

        Args:
            query (:class:`QuerySet<pyoko:pyoko.db.queryset.QuerySet>`):
             Object listing queryset.

        Returns:
            queryset (:class:`QuerySet<pyoko:pyoko.db.queryset.QuerySet>`):
                Object listing queryset.
        """
        q = (self.object.Meta.search_fields and self.Meta.allow_search and self.input.get('query'))
        if q:
            return query.search_on(*self.object.Meta.search_fields, contains=q)
        return query

    @obj_filter
    def _get_list_obj(self, obj, result, **kwargs):
        fields = kwargs.get('list_fields', self.object.Meta.list_fields)

        if fields:
            for f in fields:
                field = getattr(obj, f, None)
                field_str = ''
                if isinstance(field, Model):
                    field_str = six.text_type(field)
                elif callable(field):
                    field_str = field()
                elif '.' in f:
                    field_str = six.text_type(attrgetter(f)(obj))
                else:
                    field_str = six.text_type(obj.get_humane_value(f))
                result['fields'].append(field_str)
        else:
            result['fields'] = [six.text_type(obj)]

    def _parse_object_actions(self, obj, **kwargs):
        """
        Applies registered (with ``@obj_filter`` decorator)
        object filter methods

        Args:
            obj (:class:`Model<pyoko:pyoko.model.Model>`): Model instance

        Returns:
            Result dict that transforms into a row of object
            listing.

            .. code-block:: python

                {
                      "fields": [ # cell contents
                        "Title of the obj",
                        "Description of obj",
                        "06.01.2016"
                      ],
                      "actions": [ # per row actions
                        {
                          "fields": [
                            0 # cell indexes to be shown as link
                          ],
                          "cmd": "show",
                          "mode": "normal",
                          "show_as": "link"
                        },
                        {
                          "cmd": "add_edit_form",
                          "name": "Edit",
                          "show_as": "button",
                          "mode": "normal"
                        },
                        {
                          "cmd": "delete",
                          "name": "Delete",
                          "show_as": "button",
                          "mode": "normal"
                        }
                      ],
                      "key": "LbFDElbgINMaYA4meOHgMhkOFQc"
                    }

        """

        actions = []
        # If override actions for the model is defined, then only show those actions
        override_actions = getattr(self.object.Meta, 'crud_override_actions', None)
        if override_actions is not None:
            actions = override_actions
        else:
            # If override actions is not defined, show the actions defined on the view
            if self.Meta.object_actions:
                for perm, action in self.Meta.object_actions.items():
                    permission = "%s.%s" % (self.object.__class__.__name__, perm)
                    if self.current.has_permission(permission):
                        actions.append(action)
        # If there are extra actions for the model, add them
        extra_actions = getattr(self.object.Meta, 'crud_extra_actions', [])
        actions.extend(extra_actions)
        result = {'key': obj.key, 'fields': [], 'actions': actions}.copy()
        for method in self.FILTER_METHODS:
            method(self, obj, result, **kwargs)
        return result

    def _apply_list_queries(self, queryset):
        """
        Applies registered (with ``@list_query`` decorator)
        list query methods.

        Args:
            queryset (:class:`QuerySet<pyoko:pyoko.db.queryset.QuerySet>`):
             Object listing queryset
        """
        for f in self.QUERY_METHODS:
            queryset = f(self, queryset)
        return queryset

    @list_query
    def _handle_list_pagination(self, query):
        """
        Handles pagination of object listings.

        Args:
            query (:class:`QuerySet<pyoko:pyoko.db.queryset.QuerySet>`):
                Object listing queryset.

        Returns:

        """
        current_page = int(self.current.input.get('page', 1))
        per_page = self.Meta.objects_per_page
        total_objects = query.count()
        total_pages = int(total_objects / per_page or 1)
        # add orphans to last page
        current_per_page = per_page + (
            total_objects % per_page if current_page == total_pages else 0)
        self.output["pagination"] = dict(page=current_page,
                                         total_pages=total_pages,
                                         total_objects=total_objects,
                                         per_page=current_per_page)
        query = query.set_params(rows=current_per_page, start=(current_page - 1) * per_page)
        return query

    def display_list_filters(self):
        """
        Calculates and renders list filters according to
        :attr:`model.Meta.list_filters<pyoko:pyoko.model.Model.Meta.list_filters>`.

            .. code-block:: python

                class Foo(Model):
                    class Meta:
                        list_filters = ['field_name', 'another_field_name']
        """
        model_class = self.object.__class__
        if not (self.Meta.allow_filters and model_class.Meta.list_filters):
            return
        self.output['meta']['allow_filters'] = True

        filters = self.input.get('filters', {}) if self.Meta.allow_filters else {}

        flt = []
        for field_name in model_class.Meta.list_filters:
            chosen_filters = filters.get(field_name, {}).get('values', [])

            field = self.object._fields[field_name]
            f = {'field': field_name,
                 'verbose_name': field.title,
                 # 'type': 'button'
                 }
            if isinstance(field, (fields.Date, fields.DateTime)):
                f['type'] = 'date'
                f['values'] = chosen_filters or chosen_filters.extend((None, None))

            elif isinstance(field, fields.Boolean):
                f['values'] = [{'name': k, "value": k,
                                'selected': True if k in chosen_filters else False} for k in
                               ("true", "false")]

            elif field.choices:
                f['values'] = [
                    {'name': k,
                     'value': v,
                     'selected': True if unicode(v) in chosen_filters else False} for v, k in
                               self.object.get_choices_for(field_name)]

            else:
                f['values'] = [{'name': k, 'value': k} for k, v in
                               model_class.objects.distinct_values_of(field_name).items()]

            flt.append(f)
        self.output['list_filters'] = flt

    @view_method
    def object_search(self):
        """
        Simple object search.
        """
        q = (self.object.Meta.search_fields and self.Meta.allow_search and self.input.get('query'))
        if q:
            self.output['objects'] = [
                (o.key, o.__unicode__())
                for o in self.object.objects.search_on(*self.object.Meta.search_fields, contains=q)
                ]

    @view_method
    def list(self, custom_form=None, **kwargs):
        """
        Creates object listings for the model.
        """
        query = self._apply_list_queries(self.object.objects.all().order_by())
        self.output['objects'] = []
        self.make_list_header(**kwargs)
        self.display_list_filters()
        for obj in query:
            list_obj = self._parse_object_actions(obj, **kwargs)
            list_obj['actions'] = sorted(list_obj['actions'], key=lambda x: x.get('name', ''))
            if not ('exclude' in list_obj or obj.deleted):
                self.output['objects'].append(list_obj)
        title = getattr(self.object.Meta, 'verbose_name_plural', self.object.__class__.__name__)
        self.form_out(custom_form or self.ListForm(current=self.current, title=title))

    @view_method
    def reload(self):
        """
        Tells the client to reload it's current view.
        """
        self.set_client_cmd('reload')

    @view_method
    def reset(self):
        """
        Tells the client to reset (restart) it's current workflow.
        """
        self.set_client_cmd('reset')

    @view_method
    def select_list(self):
        """
        Creates a simple object list for auto-complete dropdown
        boxes.

        By default it tries to return all items. But if number of
        items is more than
        :attr:`~zengine.settings.MAX_NUM_DROPDOWN_LINKED_MODELS`
        then, it returns back ``[-1]`` which means "Too many
        items, please filter".

        If queryset doesn't return any items, it returns back
        ``[0]`` value.

        Note:
            Output of this method will be cached with
            :class:`SelectBoxCache` object.

        """
        query = self.object.objects.all()
        query = self._apply_list_search(query)
        num_of_rec = query.count()
        searched = 'query' in self.input
        if not searched and num_of_rec > settings.MAX_NUM_DROPDOWN_LINKED_MODELS:
            self.output['objects'] = [-1]
        elif not num_of_rec:
            self.output['objects'] = [0]
        else:
            search_str = self.input.get('query', '')
            cache = SelectBoxCache(self.model_class.__name__, search_str)
            self.output['objects'] = cache.get() or cache.set(
                [{'key': obj.key, 'value': six.text_type(obj)}
                 for obj in query])

    @view_method
    def object_name(self):
        """
        Writes current objects (``self.object``) text
        representation to ``output['object_name']``.
        """
        self.output['object_name'] = self.object.__unicode__()

    @view_method
    def show(self):
        """
        Returns details of the selected object.
        """
        self.set_client_cmd('show')
        obj_form = forms.JsonForm(self.object, current=self.current, models=False,
                                  list_nodes=False)._serialize(readable=True)
        obj_data = OrderedDict()
        for d in obj_form:
            val = d['value']
            # Python doesn't allow custom JSON encoders for keys of dictionaries.
            # If the title is a lazy translation, we must force the translation here.
            key = six.text_type(d['title'])
            if d['type'] in ('button',) or d['title'] in ('Password', 'key'):
                continue
            if d['type'] == 'file' and d['value'] and d['value'][-3:] in ('jpg', 'png'):
                continue  # passing for now, needs client support

            if not d['kwargs'].get('hidden', False):
                obj_data[key] = six.text_type(val) if val is not None else val
        self.output['object_title'] = "%s : %s" % (self.model_class.Meta.verbose_name, self.object)
        self.output['object_key'] = self.object.key
        self.output['object'] = obj_data

    @view_method
    def add_edit_form(self):
        """
        Add edit form
        """
        self.form_out()

    def set_form_data_to_object(self):
        """
        Handles the deserialization of incoming form data
        into object instance.
        """
        self.object = self.object_form.deserialize(self.current.input['form'])

    @view_method
    def save_as_new(self):
        """
        Saves an existing record as a new one.
        """
        self.set_form_data_to_object()
        self.object.key = None
        self.save_object()
        self.current.task_data['object_id'] = self.object.key

    def save_object(self):
        """
        Saves object into DB.

        Triggers pre_save and post_save signals.

        Sets task_data['``added_obj``'] if object is new.
        """
        signals.crud_pre_save.send(self, current=self.current, object=self.object)
        obj_is_new = not self.object.exist
        self.object.blocking_save()
        signals.crud_post_save.send(self, current=self.current, object=self.object)

    @view_method
    def save(self):
        """
        Object save view. Actual work done at other methods.
        Can be overridden.
        """
        self.set_form_data_to_object()
        self.save_object()
        self.current.task_data['object_id'] = self.object.key

    @view_method
    def delete(self):
        """
        Object delete view.
        Triggers pre_delete and post_delete signals.
        """
        # TODO: add confirmation dialog
        signals.crud_pre_delete.send(self, current=self.current, object=self.object)
        if 'object_id' in self.current.task_data:
            del self.current.task_data['object_id']
        object_data = self.object._data
        self.object.blocking_delete()
        signals.crud_post_delete.send(self, current=self.current, object_data=object_data)
        self.set_client_cmd('reload')

    @view_method
    def confirm_deletion(self):
        """
        :return:
        """
        form = DeletionConfirmForm(title=_(u"Deletion Confirmation"))
        form.help_text = _(u"Do you confirm the deletion of %s ?" % self.object)
        self.form_out(form)
