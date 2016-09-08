# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.models import *


class Project(Model):
    manager = Role('Project Manager')

    class Employee(ListNode):
        employee = Role('Employee')

        def get_user(self):
            return self.employee

    @property
    def assigned_employees(self):
        return map(Project.Employee.get_user, self.Employee)
