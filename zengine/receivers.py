# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.models import TaskInvitation, WFCache
from pyoko.conf import settings
from zengine.dispatch.dispatcher import receiver
from zengine.signals import lane_user_change, crud_post_save
from datetime import datetime
from datetime import timedelta


__all__ = [
    'send_message_for_lane_change',
    'set_password',
]

DEFAULT_LANE_CHANGE_INVITE_MSG = {
    'title': settings.MESSAGES['lane_change_invite_title'],
    'body': settings.MESSAGES['lane_change_invite_body'],
}


@receiver(lane_user_change)
def send_message_for_lane_change(sender, **kwargs):
    """
    Sends a message to possible owners of the current workflows
     next lane.

    Args:
        **kwargs: ``current`` and ``possible_owners`` are required.
        sender (User): User object
    """
    current = kwargs['current']
    owners = kwargs['possible_owners']
    if 'lane_change_invite' in current.task_data:
        msg_context = current.task_data.pop('lane_change_invite')
    else:
        msg_context = DEFAULT_LANE_CHANGE_INVITE_MSG

    wfi = WFCache(current).get_instance()

    # Deletion of used passive task invitation which belongs to previous lane.
    TaskInvitation.objects.filter(instance=wfi, role=current.role, wf_name=wfi.wf.name).delete()

    for recipient in owners:
        recipient.send_notification(title=msg_context['title'],
                                    message="%s %s" % (wfi.wf.title, msg_context['body']),
                                    typ=1,  # info
                                    url='',
                                    sender=sender
                                    )
        today = datetime.today()

        inv = TaskInvitation(
            instance=wfi,
            role=recipient,
            wf_name=wfi.wf.name,
            progress=30,
            start_date=today,
            finish_date=today + timedelta(15)
        )
        inv.title = current.task_data.get('INVITATION_TITLE') or wfi.wf.title
        inv.save()


# encrypting password on save
@receiver(crud_post_save)
def set_password(sender, **kwargs):
    """
    Encrypts password of the user.
    """
    if sender.model_class.__name__ == 'User':
        usr = kwargs['object']
        if not usr.password.startswith('$pbkdf2'):
            usr.set_password(usr.password)
            usr.save()
