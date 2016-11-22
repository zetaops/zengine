# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

class WFValues(object):
    def assign_wf_initial_values(self,current):
        current.task_data['wf_initial_values'] = {}