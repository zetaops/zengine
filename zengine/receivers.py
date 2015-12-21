# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.notifications import Notify

from pyoko.lib.utils import get_object_from_path

from pyoko.conf import settings
from zengine.dispatch.dispatcher import receiver
from zengine.signals import lane_user_change, crud_post_save
from zengine.lib.catalog_data import gettxt as _

DEFAULT_LANE_CHANGE_INVITE_MSG = {
    'title': settings.MESSAGES['lane_change_invite_title'],
    'body': settings.MESSAGES['lane_change_invite_body'],
}
UserModel = get_object_from_path(settings.USER_MODEL)


@receiver(lane_user_change)
def send_message_for_lane_change(sender, *args, **kwargs):
    current = kwargs['current']
    old_lane = kwargs['old_lane']
    owners = kwargs['possible_owners']
    if 'lane_change_invite' in current.task_data:
        msg_context = current.task_data.pop('lane_change_invite')
    else:
        msg_context = DEFAULT_LANE_CHANGE_INVITE_MSG
    for recipient in owners:
        if not isinstance(recipient, UserModel):
            recipient = recipient.get_user()
        Notify(recipient.key).set_message(title=_(msg_context['title']),
                                          body=_(msg_context['body']),
                                          type=Notify.TaskInfo,
                                          url=current.get_wf_url()
                                          )

# encrypting password on save
@receiver(crud_post_save)
def set_password(sender, *args, **kwargs):
    if sender.model_class.__name__ == 'User':
        usr = kwargs['object']
        if not usr.password.startswith('$pbkdf2'):
            usr.set_password(usr.password)
            usr.save()
