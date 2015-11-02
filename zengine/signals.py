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
