# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import six
from pyoko.exceptions import ObjectDoesNotExist
from zengine.models import WFCache
from zengine.models import WFInstance


def sessid_to_userid(current):
    current.output['user_id'] = current.user_id.lower()
    current.output['sess_id'] = current.session.sess_id
    current.user.bind_private_channel(current.session.sess_id)
    current.output['sessid_to_userid'] = True

def mark_offline_user(current):
    current.user.is_online(False)


def sync_wf_cache(current):
    wf_cache = WFCache(current)
    wf_state = wf_cache.get()
    if 'role_id' in wf_state:
        try:
            wfi = WFInstance.objects.get(key=current.input['token'])
        except ObjectDoesNotExist:
            # just for backwards compatibility
            wfi = WFInstance(key=current.input['token'])
        wfi.step = wf_state['step']
        wfi.name = wf_state['name']
        wfi.pool = wf_state['pool']
        wfi.current_actor_id = wf_state['role_id']
        wfi.data = wf_state['data']
        if wf_state['finished']:
            wfi.finished = True
            wfi.finish_date = wf_state['finish_date']
            wf_cache.delete()
        wfi.save()
    else:
        pass
        # if cache already cleared, we have nothing to sync
    # -1 means do not return anything to client
    current.output = -1


