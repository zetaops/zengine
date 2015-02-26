# -*-  coding: utf-8 -*-
"""
zengine test views

all test views should use current.jsonin and current.jsonout for data input output purposes.

"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
__author__ = 'Evren Esat Ozkan'

TEST_USER = {'username': 'user', 'password': 'pass', 'id': 1}


def do_login(current):
    login_data = current.jsonin['login_data']
    loged_in = login_data['username'] == TEST_USER['username'] and login_data['password'] == TEST_USER['password']
    current.task.data['is_login_successful'] = loged_in
    current.jsonout = {'success': loged_in}


def show_login(current):
    current.jsonout = {'form': 'login_form'}


def show_dashboard(current):
    current.jsonout = {'screen': 'dashboard'}
