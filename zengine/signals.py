# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


from zengine.dispatch.dispatcher import Signal


# emitted when lane changed to another user on a multi-lane workflow
# doesn't trigger if both lanes are owned by the same user
lane_user_change = Signal(providing_args=["current", "old_lane", "possible_owners"])



crud_post_save = Signal(providing_args=["current", "object"])
crud_pre_save = Signal(providing_args=["current", "object"])
crud_pre_delete = Signal(providing_args=["current", "object"])
crud_post_delete = Signal(providing_args=["current", "object_data"])
new_perm_added = Signal(providing_args=[])
