# -*-  coding: utf-8 -*-
# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from json_form import JsonForm
from zengine.settings import DATE_DEFAULT_FORMAT
from datetime import datetime


class FillableForm(JsonForm):

    def __init__(self, *args, **kwargs):
        # If True, form will always be generated blank
        self.always_blank = kwargs.pop('always_blank', False)
        self.current = kwargs.pop('current', None)
        super(FillableForm, self).__init__(*args, **kwargs)

    def serialize(self):
        result = super(FillableForm, self).serialize()
        if not self.always_blank:
            data = None
            if self.current:
                if self.__class__.__name__ in self.current.task_data:
                    data = self.current.task_data[self.__class__.__name__]
                if data:
                    for k, v in result['model'].items():
                        try:
                            if result['schema']['properties'][k]['type'] == 'date':
                                date_field = datetime.strptime(data[k], DATE_DEFAULT_FORMAT)
                                data[k] = date_field.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                            result['model'][k] = data[k]
                        except KeyError:
                            pass
        return result
