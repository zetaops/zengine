# -*-  coding: utf-8 -*-
"""Authentication views"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import falcon

from pyoko import fields
from zengine.forms.json_form import JsonForm
from zengine.views.base import SimpleView


class LoginForm(JsonForm):
    """
    Simple login form
    """
    username = fields.String("Username")
    password = fields.String("Password", type="password")


def logout(current):
    """
    Log out view.
    Simply deletes the session object

    Args:
        current: :attr:`~zengine.engine.WFCurrent` object.
    """
    current.session.delete()


def dashboard(current):
    """
    Dashboard view. Not implemented yet!!!

    Args:
        current: :attr:`~zengine.engine.WFCurrent` object.
    """
    current.output["msg"] = "Success"


class Login(SimpleView):
    """
    Class based login view.
    Displays login form at ``show`` stage,
    does the authentication at ``do`` stage.
    """
    def do_view(self):
        """
        Authenticate user with given credentials.
        """
        try:
            auth_result = self.current.auth.authenticate(
                self.current.input['username'],
                self.current.input['password'])
            self.current.task_data['login_successful'] = auth_result
        except:
            self.current.log.exception("Wrong username or another error occurred")
            self.current.task_data['login_successful'] = False
        if not self.current.task_data['login_successful']:
            self.current.output['status_code'] = 403

    def show_view(self):
        """
        Show :attr:`LoginForm` form.
        """
        self.current.output['forms'] = LoginForm(current=self.current).serialize()



