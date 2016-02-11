# -*-  coding: utf-8 -*-
"""
Builting signals for various events.
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


from zengine.dispatch.dispatcher import Signal


#: Emitted when lane changed to another user on a multi-lane workflow
#:
#: Doesn't trigger if both lanes are owned by the same user
lane_user_change = Signal(providing_args=["current", "old_lane", "possible_owners"])


#: After saving of an object with CrudView based view.
crud_post_save = Signal(providing_args=["current", "object"])

#: Before saving of an object with CrudView based view.
crud_pre_save = Signal(providing_args=["current", "object"])

#: Before deletion of an object with CrudView based view.
crud_pre_delete = Signal(providing_args=["current", "object"])

#: After deletion of an object with CrudView based view.
crud_post_delete = Signal(providing_args=["current", "object_data"])
