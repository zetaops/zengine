# -*-  coding: utf-8 -*-
"""Base view classes"""
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from falcon import HTTPNotFound
from pyoko.model import Model
from zengine.lib.forms import JsonForm

__author__ = "Evren Esat Ozkan"


class BaseView(object):
    """
    this class constitute a base for all view classes.
    """
    def __init__(self, current):
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
        if current.request.context['data'].get('cmd', '') == 'do':
            self._do()
        else:
            self._show()

    def _do(self):
        """
        You should override this method in your class
        """
        raise NotImplementedError

    def _show(self):
        """
        You should override this method in your class
        """
        raise NotImplementedError


class CrudView(BaseView):
    """
    A base class for "Create List Show Update Delete" type of views.

    :type object: Model | None
    """



    def __init__(self, current, model_class):
        self.model_class = model_class
        super(CrudView, self).__init__(current)
        self.object_id = self.input.get('object_id')
        if self.object_id:
            try:
                self.object = self.model_class.objects.get(self.object_id)
                if self.object.deleted:
                    raise
            except:
                raise HTTPNotFound()

        else:
            self.object = None
        {
            'list': self.list,
            'show': self.show,
            'add': self.add,
            'edit': self.edit,
            'delete': self.delete,
            'save': self.save,
        }[current.input['cmd']]()


    def show(self):
        self.output['object'] = self.object.clean_value()




    def list(self):
        """
        You should override this method in your class
        """
        # TODO: add pagination
        # TODO: use models
        for obj in self.MODEL.objects.filter():
            data = obj.data
            self.output['objects'].append({"data": data, "key": obj.key})

    def edit(self):
        """
        You should override this method in your class
        """
        if self.do:
            serialized_form = JsonForm(self.object).serialize()
            self.output['forms'] = serialized_form
        else:
            if not self.object:
                self.object = self.model_class()
            self.object._load_data(self.current.input['form'])
            self.object.save()
            self.current.task_data['IS'].opertation_successful = True



    def add(self):
        """
        You should override this method in your class
        """
        if self.do:
            pass
        else:
            serialized_form = JsonForm(self.model_class()).serialize()

    def save(self):
        """
        You should override this method in your class
        """
        raise NotImplementedError

    def delete(self):
        """
        You should override this method in your class
        """
        raise NotImplementedError
