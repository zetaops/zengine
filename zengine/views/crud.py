# -*-  coding: utf-8 -*-
"""Base view classes"""
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from falcon import HTTPNotFound

from pyoko.model import Model, model_registry
from zengine.lib.forms import JsonForm
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
                    self.object = self.model_class.objects.get(self.object_id)
                    if self.object.deleted:
                        raise HTTPNotFound()
                except:
                    raise HTTPNotFound()

            else:
                self.object = self.model_class(current)
            current.log.info('Calling %s_view of %s' % (
                (self.cmd or 'list'), self.model_class.__name__))
            self.__class__.__dict__['%s_view' % (self.cmd or 'list')](self)

    def list_models(self):
        self.output["models"] = [m.__name__ for m in
                                 model_registry.get_base_models()]

    def show_view(self):
        self.output['object'] = self.object.clean_value()
        self.output['client_cmd'] = 'show_object'

    def list_view(self):
        # TODO: add pagination
        # TODO: investigate and if neccessary add sequrity/sanity checks for search params
        query = self.object.objects.filter()
        if 'filters' in self.input:
            query = query.filter(**self.input['filters'])
        self.output['client_cmd'] = 'list_objects'
        self.output['objects'] = []
        for obj in query:
            if ('just_deleted_object_key' in self.current.task_data and
                        self.current.task_data['just_deleted_object_key'] == obj.key):
                del self.current.task_data['just_deleted_object_key']
                continue

            data = obj.clean_value()
            self.output['objects'].append({"data": data, "key": obj.key})

        if 'just_added_object' in self.current.task_data:
            self.output['objects'].append(self.current.task_data['just_added_object'].copy())
            del self.current.task_data['just_added_object']
        self.output

    def edit_view(self):
        if self.do:
            self._save_object()
            self.go_next_task()
        else:
            self.output['forms'] = JsonForm(self.object).serialize()
            self.output['client_cmd'] = 'add_object'

    def add_view(self):
        if self.do:
            self._save_object()
            self.go_next_task()
        else:
            self.output['forms'] = JsonForm(self.model_class()).serialize()
            self.output['client_cmd'] = 'add_object'

    def _save_object(self, data=None):
        self.object.set_data(data or self.current.input['form'])
        self.object.save()
        if self.next_task == 'list':  # to overcome 1s riak-solr delay
            self.current.task_data['just_added_object'] = {
                'key': self.object.key,
                'data': self.object.clean_value()}

    def delete_view(self):
        # TODO: add confirmation dialog
        if self.next_task == 'list':  # to overcome 1s riak-solr delay
            self.current.task_data['just_deleted_object_key'] = self.object.key
        self.object.delete()
        del self.current.input['object_id']
        self.go_next_task()


crud_view = CrudView()
