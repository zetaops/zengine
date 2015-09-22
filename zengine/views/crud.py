# -*-  coding: utf-8 -*-
"""Base view classes"""
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import datetime
from falcon import HTTPNotFound

from pyoko.model import Model, model_registry
from zengine.lib.forms import JsonForm
from zengine.log import log
from zengine.views.base import BaseView


class CrudView(BaseView):
    """
    A base class for "Create List Show Update Delete" type of views.



    :type object: Model | None
    """
    #
    # def __init__(self):
    #     super(CrudView, self).__init__()

    def __call__(self, current):
        current.log.info("CRUD CALL")
        self.set_current(current)
        if 'model' not in current.input:
            self.list_models()
        else:
            self.model_class = model_registry.get_model(current.input['model'])

            self.object_id = self.input.get('object_id')
            if self.object_id:
                try:
                    self.object = self.model_class(current).objects.get(self.object_id)
                    if self.object.deleted:
                        raise HTTPNotFound()
                except:
                    raise HTTPNotFound()

            else:
                self.object = self.model_class(current)
            current.log.info('Calling %s_view of %s' % (
                (self.cmd or 'list'), self.model_class.__name__))
            self.form = JsonForm(self.object, all=True)
            self.__class__.__dict__['%s_view' % (self.cmd or 'list')](self)

    def list_models(self):
        self.output["models"] = [(m.Meta.verbose_name_plural, m.__name__)
                                 for m in model_registry.get_base_models()]

        self.output["app_models"] = [(app, [(m.Meta.verbose_name_plural, m.__name__)
                                            for m in models])
                                 for app, models  in model_registry.get_models_by_apps()]

    def show_view(self):
        self.output['object'] = self.form.serialize()['model']
        self.output['client_cmd'] = 'show_object'

    def get_list_obj(self, mdl, brief):
        if brief:
            return [mdl.key, unicode(mdl)]
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

    def list_view(self):
        # TODO: add pagination
        # TODO: investigate and if neccessary add sequrity/sanity checks for search params
        brief = 'brief' in self.input
        query = self.object.objects.filter()
        if 'filters' in self.input:
            query = query.filter(**self.input['filters'])
        self.output['client_cmd'] = 'list_objects'
        self.output['nobjects'] = []
        self.output['objects'] = []
        if self.object.Meta.list_fields and not brief:  # add list headers
            list_headers = []
            for f in self.object.Meta.list_fields:
                if callable(getattr(self.object, f)):
                    list_headers.append(getattr(self.object, f).title)
                else:
                    list_headers.append(self.object._fields[f].title)
            self.output['nobjects'].append(list_headers)
        make_it_brief = brief or not self.object.Meta.list_fields
        if make_it_brief:
            self.output['nobjects'].append('-1')
        for obj in query:
            if ('deleted_obj' in self.current.task_data and self.current.task_data[
                'deleted_obj'] == obj.key):
                del self.current.task_data['deleted_obj']
                continue
            self.output['nobjects'].append(self.get_list_obj(obj, make_it_brief))
            self.output['objects'].append({"data": obj.clean_field_values(), "key": obj.key})
        if 'added_obj' in self.current.task_data:
            try:
                    new_obj = self.object.objects.get(self.current.task_data['added_obj'])
                    self.output['nobjects'].insert(1, self.get_list_obj(new_obj, make_it_brief))
                    self.output['objects'].insert(0, {"data": new_obj.clean_field_values(), "key": new_obj.key})
            except:
                log.exception("ERROR while adding newly created object to object listing")
            del self.current.task_data['added_obj']
        self.output

    def edit_view(self):
        if self.do:
            self._save_object()
            self.go_next_task()
        else:
            self.output['forms'] = self.form.serialize()
            self.output['client_cmd'] = 'edit_object'


    def add_view(self):
        if self.do:
            self._save_object()
            self.go_next_task()
            if self.next_task == 'list':  # to overcome 1s riak-solr delay
                self.current.task_data['added_obj'] = self.object.key
        else:
            self.output['forms'] = self.form.serialize()
            self.output['client_cmd'] = 'add_object'

    def _save_object(self, data=None):
        self.object = self.form.deserialize(data or self.current.input['form'])
        self.object.save()


    def delete_view(self):
        # TODO: add confirmation dialog
        if self.next_task == 'list':  # to overcome 1s riak-solr delay
            self.current.task_data['deleted_obj'] = self.object.key
        self.object.delete()
        del self.current.input['object_id']
        self.go_next_task()


crud_view = CrudView()
