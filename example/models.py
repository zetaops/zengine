# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.models import *


class Lecturer(Model):
    name = field.String("Adı", index=True)


class Lecture(Model):
    name = field.String("Ders adı", index=True)


class Student(Model):
    name = field.String("Adı", index=True)
    advisor = Lecturer()

    class Lectures(ListNode):
        lecture = Lecture()
        confirmed = field.Boolean("Onaylandı", default=False)
