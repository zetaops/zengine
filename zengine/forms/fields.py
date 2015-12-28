# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pyoko.fields import *


class Button(BaseField):
    def __init__(self, *args, **kwargs):
        # self.cmd = kwargs.pop('cmd', None)
        # self.position = kwargs.pop('position', 'bottom')
        # self.validation = kwargs.pop('validation', True)
        # self.flow = kwargs.pop('flow', None)
        self.kwargs = kwargs
        super(Button, self).__init__(*args, **kwargs)

    solr_type = 'button'
