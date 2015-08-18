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

__author__ = "Evren Esat Ozkan"


class BaseView(object):
    """
    this class constitute a base for all view classes.
    """

    def __init__(self, current=None):
        if current:
            self.set_current(current)

    def set_current(self, current):
        self.current = current
        self.input = current.input
        self.output = current.output
        self.cmd = current.input.get('cmd')
        self.subcmd = current.input.get('subcmd')
        self.do = self.subcmd == 'do'


class SimpleView(BaseView):
    """
    simple form based views can be build  up on this class.
    we call self._do() method if client sends a 'do' command,
    otherwise show the form by calling self._show() method.

    """

    def __init__(self, current):
        super(SimpleView, self).__init__(current)
        self.__class__.__dict__["%s_view" % (self.cmd or 'show')](self)


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

    def show_view(self):
        self.output['object'] = self.object.clean_value()

    def list_view(self):
        # TODO: add pagination
        # TODO: investigate and if neccessary add sequrity/sanity checks for search params
        query = self.object.objects.filter()
        if 'filters' in self.input:
            query = query.filter(**self.input['filters'])
        self.output['objects'] = []
        for obj in query:
            data = obj.clean_value()
            self.output['objects'].append({"data": data, "key": obj.key})
        self.output

    def edit_view(self):
        if self.do:
            self._save_object()
        else:
            self.output['forms'] = JsonForm(self.object).serialize()

    def add_view(self):
        if self.do:
            self._save_object()
        else:
            self.output['forms'] = JsonForm(self.model_class()).serialize()

    def _save_object(self, data=None):
        self.object._load_data(data or self.current.input['form'])
        self.object.save()
        self.current.task_data['IS'].opertation_successful = True

    def delete_view(self):
        # TODO: add confirmation dialog
        self.object.delete()
        self.current.task_data['IS'].opertation_successful = True


crud_view = CrudView()
