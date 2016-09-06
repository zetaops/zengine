# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from zengine.lib.decorators import view, bg_job
from zengine.models import TaskInvitation


# def sessid_to_userid(current):
#     current.output['user_id'] = current.user_id.lower()
#     current.output['sess_id'] = current.session.sess_id
#     current.user.bind_private_channel(current.session.sess_id)
#     current.output['sessid_to_userid'] = True

@view()
def mark_offline_user(current):
    current.user.is_online(False)

@view()
def get_tasks(current):
    """
        List task invitations of current user


        .. code-block:: python

            #  request:
                {
                'view': '_zops_get_tasks',
                'query': string, # optional. for searching on user's tasks
                'wf_type': string, # optional. only show tasks of selected wf_type
                'start_date': datetime, # optional. only show tasks starts after this date
                'finish_date': datetime, # optional. only show tasks should end before this date
                '
                }

            #  response:
                {
                'task_list': [
                    {'token': string, # wf token (key of WFInstance)
                     'title': string,  # name of workflow
                     'wf_type': string,  # unread message count
                     'title': string,  # task title
                     'state': int,  # state of invitation
                                    # zengine.models.workflow_manager.TASK_STATES
                     'start_date': datetime,  # start date
                     'finish_date': datetime,  # end date

                     },]
                }
        """
    # TODO: Also return invitations for user's other roles
    # TODO: Handle automatic role switching
    queryset = TaskInvitation.objects.filter(role_id=current.role_id)
    if current.input['query']:
        queryset = queryset.filter(search_data__contains=current.input['query'].lower())
    if current.input['wf_type']:
        queryset = queryset.filter(wf_name=current.input['wf_type'])
    if current.input['start_date']:
        queryset = queryset.filter(start_date__gte=current.input['start_date'])
    if current.input['finish_date']:
        queryset = queryset.filter(finish_date__lte=current.input['finish_date'])
    current.output['task_list'] = [
        {
            'token': inv.instance.key,
            'title': inv.title,
            'wf_type': inv.wf_name,
            'state': inv.state,
            'start_date': inv.task.start_date,
            'finish_date': inv.task.finish_date}
        for inv in queryset
        ]

