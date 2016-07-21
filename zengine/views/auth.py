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
from zengine.messaging import Notify
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

    def _user_is_online(self):
        self.current.user.is_online(True)

    def _do_upgrade(self):
        """ open websocket connection """
        self.current.output['cmd'] = 'upgrade'
        self.current.output['user_id'] = self.current.user_id
        self.current.user.is_online(True)
        self.current.user.bind_channels_to_session_queue(self.current.session.sess_id)
        UserSessionID(self.current.user_id).set(self.current.session.sess_id)

    def do_view(self):
        """
        Authenticate user with given credentials.
        Connects user's queue and exchange
        """
        self.current.output['login_process'] = True
        self.current.task_data['login_successful'] = False
        if self.current.is_auth:
            self._do_upgrade()
        else:
            try:
                auth_result = self.current.auth.authenticate(
                    self.current.input['username'],
                    self.current.input['password'])
                self.current.task_data['login_successful'] = auth_result
                if auth_result:
                    self._do_upgrade()
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
        self.current.output['login_process'] = True
        if self.current.is_auth:
            self._do_upgrade()
        else:
            self.current.output['forms'] = LoginForm(current=self.current).serialize()
