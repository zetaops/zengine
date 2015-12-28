# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pyoko.fields import BaseField
from .fields import Button

from .model_form import ModelForm


class Form(ModelForm):
    """
    A base class for a custom form with pyoko.fields.
    Has some fake properties to simulate model object
    """

    def __init__(self, *args, **kwargs):
        self.context = kwargs.get('current')
        self._nodes = {}
        self._fields = {}
        self._field_values = {}
        self.key = None
        self._data = {}
        self._ordered_fields = []
        self.processed_nodes = []
        super(Form, self).__init__(*args, **kwargs)
        self._prepare_nodes()

    def get_links(self, **kw):
        """
        to imitate real model

        :return: empty list
        """
        return []

    def _get_bucket_name(self):
        """
        to imitate real model

        :return: empty string
        """
        return ''

    def get_unpermitted_fields(self):
        """
        to imitate real model

        :return: empty list
        """
        return []

    def _prepare_fields(self):
        _items = list(self.__class__.__dict__.items()) + list(self.__dict__.items())
        for key, val in _items:
            if isinstance(val, BaseField):
                val.name = key
                self._fields[key] = val
            if isinstance(val, (Button,)):
                self.non_data_fields.append(key)
        for v in sorted(self._fields.items(), key=lambda x: x[1]._order):
            self._ordered_fields.append((v[0], v[1]))

    def _prepare_nodes(self):
        _items = list(self.__class__.__dict__.items()) + list(self.__dict__.items())
        for key, val in _items:
            if getattr(val, '_TYPE', '') in ['Node', 'ListNode']:
                self._nodes[key] = val(root=self)
                setattr(self, key, val(root=self))

    def get_humane_value(self, name):
        return name

    def is_in_db(self):
        """
        to imitate real model

        :return: False
        """
        return False

    def set_data(self, data):
        """
        fills form with data
        :param dict data:
        :return: self
        """
        for name in self._fields:
            setattr(self, name, data.get(name))
        return self
