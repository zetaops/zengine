# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from pprint import pprint

from pyoko import ListNode
from zengine import forms
from zengine.forms import fields


class TestForm1(forms.JsonForm):
    code = fields.String("Code Field")
    main_hid = fields.String('Main RHidden Field', hidden=True)
    class Foos(ListNode):
        foo = fields.String('Foo Field')
        hid = fields.String('Hidden Field', hidden=True)

def test_form_with_lisnode():
    tf = TestForm1()
    # this should not be needed but for now...
    tf._prepare_fields()
    tf.code = 'kod'
    tf.main_hid = 'MAIN_HID'
    tf.Foos(foo='foo', hid="HID")
    tf.Foos(foo='foo2')
    srlzd = tf._serialize()
    assert srlzd[0]['value'] == 'kod'
    assert srlzd[2]['value'][0]['foo'] == 'foo'
