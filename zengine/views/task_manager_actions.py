
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.views.crud import CrudView
from zengine import forms
from zengine.forms import fields
from zengine.models import TaskInvitation
from pyoko.lib.utils import get_object_from_path
from pyoko.conf import settings

RoleModel = get_object_from_path(settings.ROLE_MODEL)


class TaskManagerActionsView(CrudView):

    def message(self, title, msg, typ='info'):
        self.output['msgbox'] = {
            'type': typ, "title": title,
            "msg": msg
        }

    # - Assign Yourself -
    def assign_yourself(self):
        task_invitation_key = self.input['task_key']
        task_invitation = TaskInvitation.objects.get(task_invitation_key)
        wfi = task_invitation.instance

        if not wfi.current_actor.exist:
            wfi.current_actor = self.current.role
            wfi.save()
            [inv.delete() for inv in TaskInvitation.objects.filter(instance=wfi) if not inv == task_invitation]
            title = "Successful",
            msg = ""
        else:
            title = "Unsuccessful",
            msg = ""

        self.message(title=title, msg=msg)
    # - Assign Yourself -

    # - Assign to same abstract role and unit -
    def select_role(self):
        roles = RoleModel.objects.filter(abstract_role=self.current.role.abstract_role, unit=self.current.role.unit)
        self.current.task_data['task_inv_key'] = self.input['task_key']
        if roles:
            _form = forms.JsonForm(title='Assign to workflow')
            _form.select_role = fields.Integer("Chose Role", choices=roles)
            _form.explain_text = fields.String("Explain Text", required=False)
            _form.send_button = fields.Button("Send")
            self.form_out(_form)
        else:
            title = "Unsuccessful",
            msg = ""
            self.message(title=title, msg=msg)

    def send_workflow(self):
        task_invitation = TaskInvitation.objects.get(self.current.task_data['task_inv_key'])
        wfi = task_invitation.instance
        if not wfi.current_actor.exist:
            wfi.current_actor = self.input['form']['select_role']
            wfi.save()
            [inv.delete() for inv in TaskInvitation.objects.filter(instance=wfi) if not inv == task_invitation]
            title = "Successful",
            msg = ""
        else:
            title = "Unsuccessful",
            msg = ""
        self.message(title=title, msg=msg)

    # - Assign to same abstract role and unit -

    # - Postponed workflow -
    def select_postponed_date(self):
        _form = forms.JsonForm(title="Suspend Workflow")
        _form.start_date = fields.DateTime("Start Date")
        _form.finish_date = fields.DateTime("Finish Date")
        _form.save_button = fields.Button("Save")
        self.form_out(_form)

    def save_date(self):
        task_invitation_key = self.input['task_key']
        task_invitation = TaskInvitation.objects.get(task_invitation_key)
        wfi = task_invitation.instance

        task_invitation.start_date = self.input['form']['start_date']
        task_invitation.finish_date = self.input['form']['finish_date']
        task_invitation.save()

        wfi.start_date = self.input['form']['start_date']
        wfi.finish_date = self.input['form']['finish_date']
        wfi.save()

        title = "Successful",
        msg = ""
        self.message(title=title, msg=msg)
    # - Postponed workflow -

    # - Suspend workflow -
    def suspend(self):
        task_invitation_key = self.input['task_key']
        task_invitation = TaskInvitation.objects.get(task_invitation_key)
        wfi = task_invitation.instance

        if wfi.current_actor.exist:
            wfi.current_actor = None
            wfi.save()
            title = "Successful",
            msg = ""
        else:
            title = "Unsuccessful",
            msg = ""

        self.message(title=title, msg=msg)
    # - Suspend workflow -
