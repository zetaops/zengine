# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from celery import Celery
from celery.signals import *
# from zengine.config import settings

signal = Celery()

# signal = Celery(broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@signal.task
def lane_change(data):
    return data

@signal.task
def lane_change2(data):
    return data

@task_success.connect
def foo(sender, *args, **kwargs):
    if sender.name == 'signals.lane_change':
        print("FOOOOOOOOOOOOOOOOOOOOO")
        print(args)
        print(kwargs)


@task_success.connect
def fosso(*args, **kwargs):
    print("AAAAAAAAAARRRRRGGG")
    print("AAAAAAARGS", args)
    print("KWAAAAARGS", kwargs)


