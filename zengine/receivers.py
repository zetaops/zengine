# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
__all__ = [
    'send_message_for_lane_change',
    'set_password',
]

from pyoko.conf import settings
from zengine.dispatch.dispatcher import receiver
from zengine.signals import lane_user_change, crud_post_save

DEFAULT_LANE_CHANGE_INVITE_MSG = {
    'title': settings.MESSAGES['lane_change_invite_title'],
    'body': settings.MESSAGES['lane_change_invite_body'],
}


@receiver(lane_user_change)
def send_message_for_lane_change(sender, *args, **kwargs):
    """
    Sends a message to possible owners of the current workflows
     next lane.

    Args:
        **kwargs: ``current`` and ``possible_owners`` are required.
    """
    from pyoko.lib.utils import get_object_from_path
    UserModel = get_object_from_path(settings.USER_MODEL)
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
        recipient.send_notification(title=msg_context['title'],
                                    message=msg_context['body'],
                                    typ=1, # info
                                    url=current.get_wf_link()
                                    )


# encrypting password on save
@receiver(crud_post_save)
def set_password(sender, *args, **kwargs):
    """
    Encrypts password of the user.
    """
    if sender.model_class.__name__ == 'User':
        usr = kwargs['object']
        if not usr.password.startswith('$pbkdf2'):
            usr.set_password(usr.password)
            usr.save()
