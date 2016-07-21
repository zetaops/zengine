# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


def sessid_to_userid(current):
    current.output['user_id'] = current.user_id.lower()
    current.output['sess_id'] = current.session.sess_id
    current.user.bind_private_channel(current.session.sess_id)
    current.output['sessid_to_userid'] = True

def mark_offline_user(current):
    current.user.is_online(False)
