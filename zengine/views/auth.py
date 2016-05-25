# -*-  coding: utf-8 -*-
"""Authentication views"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import falcon

from pyoko import fields
from zengine.forms.json_form import JsonForm
from zengine.lib.cache import UserSessionID, KeepAlive
from zengine.notifications import Notify
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
    user_id = current.session.get('user_id')
    if user_id:
        KeepAlive(user_id).delete()
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
        self.current.task_data['login_successful'] = False
        if self.current.is_auth:
            self.current.output['cmd'] = 'upgrade'
        else:
            try:
                auth_result = self.current.auth.authenticate(
                    self.current.input['username'],
                    self.current.input['password'])
                self.current.task_data['login_successful'] = auth_result
                if auth_result:
                    user_sess = UserSessionID(self.current.user_id)
                    old_sess_id = user_sess.get()
                    user_sess.set(self.current.session.sess_id)
                    notify = Notify(self.current.user_id)
                    notify.cache_to_queue()
                    if old_sess_id:
                        notify.old_to_new_queue(old_sess_id)
                    self.current.output['cmd'] = 'upgrade'
            except:
                raise
                self.current.log.exception("Wrong username or another error occurred")
            if self.current.output.get('cmd') != 'upgrade':
                self.current.output['status_code'] = 403
            else:
                KeepAlive(self.current.user_id).reset()

    def show_view(self):
        """
        Show :attr:`LoginForm` form.
        """
        if self.current.is_auth:
            self.current.output['cmd'] = 'upgrade'
        else:
            self.current.output['forms'] = LoginForm(current=self.current).serialize()
