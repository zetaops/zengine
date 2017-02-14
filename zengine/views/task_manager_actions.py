# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.views.base import BaseView
from zengine import forms
from zengine.forms import fields
from zengine.models import TaskInvitation
from pyoko.lib.utils import get_object_from_path
from pyoko.conf import settings
from datetime import datetime
from zengine.lib.utils import gettext as _

RoleModel = get_object_from_path(settings.ROLE_MODEL)


class TaskManagerActionsView(BaseView):
    def __init__(self, current=None):
        super(TaskManagerActionsView, self).__init__(current)

        if 'task_inv_key' not in self.current.task_data:
            self.current.task_data['task_inv_key'] = self.input['filters']['task_inv_id']['values'][
                0]

        self.task_invitation_key = self.current.task_data['task_inv_key']

    # - Assign Yourself -
    def assign_yourself(self):
        """
            Assigning the workflow to itself.
            The selected job is checked to see if there is an assigned role.
            If it does not have a role assigned to it, it takes the job to itself
            and displays a message that the process is successful.
            If there is a role assigned to it, it does not do any operation
            and the message is displayed on the screen.

             .. code-block:: python

                #  request:
                   {
                   'task_inv_key': string,
                   }

        """
        task_invitation = TaskInvitation.objects.get(self.task_invitation_key)
        wfi = task_invitation.instance

        if not wfi.current_actor.exist:
            wfi.current_actor = self.current.role
            wfi.save()
            [inv.delete() for inv in TaskInvitation.objects.filter(instance=wfi) if
             not inv == task_invitation]
            title = _(u"Successful")
            msg = _(u"You have successfully assigned the job to yourself.")
        else:
            title = _(u"Unsuccessful")
            msg = _(u"Unfortunately, this job is already taken by someone else.")

        self.current.msg_box(title=title, msg=msg)

    # - Assign Yourself -

    # - Assign to same abstract role and unit -
    def select_role(self):
        """
        The workflow method to be assigned to the person with the same role and unit as the user.
            .. code-block:: python

                #  request:
                   {
                   'task_inv_key': string,
                   }

        """

        roles = [(m.key, m.__unicode__()) for m in RoleModel.objects.filter(
            abstract_role=self.current.role.abstract_role,
            unit=self.current.role.unit) if m != self.current.role]

        if roles:
            _form = forms.JsonForm(title=_(u'Assign to workflow'))
            _form.select_role = fields.Integer(_(u"Chose Role"), choices=roles)
            _form.explain_text = fields.String(_(u"Explain Text"), required=False)
            _form.send_button = fields.Button(_(u"Send"))
            self.form_out(_form)
        else:
            title = _(u"Unsuccessful")
            msg = _(u"Assign role not found")
            self.current.msg_box(title=title, msg=msg)

    def send_workflow(self):
        """
        With the workflow instance and the task invitation is assigned a role.
        """
        task_invitation = TaskInvitation.objects.get(self.task_invitation_key)
        wfi = task_invitation.instance
        select_role = self.input['form']['select_role']
        if wfi.current_actor == self.current.role:
            task_invitation.role = RoleModel.objects.get(select_role)
            wfi.current_actor = RoleModel.objects.get(select_role)
            wfi.save()
            task_invitation.save()
            [inv.delete() for inv in TaskInvitation.objects.filter(instance=wfi) if
             not inv == task_invitation]
            title = _(u"Successful")
            msg = _(u"The workflow was assigned to someone else with success.")
        else:
            title = _(u"Unsuccessful")
            msg = _(u"This workflow does not belong to you, you cannot assign it to someone else.")

        self.current.msg_box(title=title, msg=msg)

    # - Assign to same abstract role and unit -

    # - Postponed workflow -
    def select_postponed_date(self):
        """
            The time intervals at which the workflow is to be extended are determined.
            .. code-block:: python

                #  request:
                   {
                   'task_inv_key': string,
                   }

        """

        _form = forms.JsonForm(title="Postponed Workflow")
        _form.start_date = fields.DateTime("Start Date")
        _form.finish_date = fields.DateTime("Finish Date")
        _form.save_button = fields.Button("Save")
        self.form_out(_form)

    def save_date(self):
        """
            Invitations with the same workflow status are deleted.
            Workflow instance and invitation roles change.

        """
        task_invitation = TaskInvitation.objects.get(self.task_invitation_key)
        wfi = task_invitation.instance
        if wfi.current_actor.exist and wfi.current_actor == self.current.role:

            dt_start = datetime.strptime(self.input['form']['start_date'], "%d.%m.%Y")
            dt_finish = datetime.strptime(self.input['form']['finish_date'], "%d.%m.%Y")

            task_invitation.start_date = dt_start
            task_invitation.finish_date = dt_finish
            task_invitation.save()

            wfi.start_date = dt_start
            wfi.finish_date = dt_finish
            wfi.save()

            title = _(u"Successful")
            msg = _(u"You've extended the workflow time.")
        else:
            title = _(u"Unsuccessful")
            msg = _(u"This workflow does not belong to you.")

        self.current.msg_box(title=title, msg=msg)

    # - Postponed workflow -

    # - Suspend workflow -
    def suspend(self):
        """
        If there is a role assigned to the workflow and
        it is the same as the user, it can drop the workflow.
        If it does not exist, it can not do anything.

            .. code-block:: python

                #  request:
                   {
                   'task_inv_key': string,
                   }

        """
        task_invitation = TaskInvitation.objects.get(self.task_invitation_key)
        wfi = task_invitation.instance

        if wfi.current_actor.exist and wfi.current_actor == self.current.role:
            for m in RoleModel.objects.filter(abstract_role=self.current.role.abstract_role,
                                              unit=self.current.role.unit):
                if m != self.current.role:
                    task_invitation.key = ''
                    task_invitation.role = m
                    task_invitation.save()

            wfi.current_actor = RoleModel()
            wfi.save()
            title = _(u"Successful")
            msg = _(u"You left the workflow.")
        else:
            title = _(u"Unsuccessful")
            msg = _(u"Unfortunately, this workflow does not belong to you or is already idle.")

        self.current.msg_box(title=title, msg=msg)
        # - Suspend workflow -
