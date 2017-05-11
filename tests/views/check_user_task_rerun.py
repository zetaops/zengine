# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

def user_task_a(current):
    current.output['task_name'] = 'user_task_a'


def user_task_b(current):
    current.output['task_name'] = 'user_task_b'


def service_task_a(current):
    current.output['task_name'] = 'service_task_a'
