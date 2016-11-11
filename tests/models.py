# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.models import *
from zengine.lib.decorators import role_getter


class Project(Model):
    manager = Role('Project Manager')

    class Employee(ListNode):
        employee = Role('Employee')

        def get_user(self):
            return self.employee

    @property
    def assigned_employees(self):
        return map(Project.Employee.get_user, self.Employee)


class Teacher(Model):
    class Meta:
        search_fields = ['name', 'surname']

    name = field.String('Alan')
    surname = field.String("Turing")

    def __unicode__(self):
        return "%s %s" % (self.name, self.surname)


class Exam(Model):
    class Meta:
        search_fields = ['teacher', 'exam_type', 'date']
    teacher = Teacher()
    exam_type = field.Integer(default=1)
    date = field.DateTime()

    def __unicode__(self):
        return "%s %s" % (self.teacher.name, self.teacher.surname)


class Program(Model):
    class Meta:
        search_fields = ['role']

    name = field.String()
    role = Role()
    typ = field.Integer()

    def __unicode__(self):
        return "%s" % self.name

    @classmethod
    @role_getter("Test Roles")
    def get_test_role(cls):
        """
            getting roles with same abstract role
        :return: roles
        """
        abstract_role = AbstractRole.objects.get(name='Test AbstractRole')
        return cls.objects.filter(abstract_role=abstract_role)
