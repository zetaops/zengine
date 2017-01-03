# -*-  coding: utf-8 -*-
"""Authentication views"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from time import sleep

import falcon

from pyoko import fields
from pyoko.exceptions import ObjectDoesNotExist
from zengine.forms.json_form import JsonForm
from zengine.lib.cache import UserSessionID, KeepAlive, Session
from zengine.lib import translation
from zengine.log import log
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
    Simply deletes the session object.
    For showing logout message:
        'show_logout_message' field should be True in current.task_data,
        Message should be sent in current.task_data with 'logout_message' field.
        Message title should be sent in current.task_data with 'logout_title' field.

        current.task_data['show_logout_message'] = True
        current.task_data['logout_title'] = 'Message Title'
        current.task_data['logout_message'] = 'Message'

    Args:
        current: :attr:`~zengine.engine.WFCurrent` object.
    """
    current.user.is_online(False)
    current.session.delete()
    current.output['cmd'] = 'logout'
    if current.task_data.get('show_logout_message', False):
        current.output['title'] = current.task_data.get('logout_title', None)
        current.output['msg'] = current.task_data.get('logout_message', None)


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

    # def _user_is_online(self):
    #     self.current.user.is_online(True)

    def _do_upgrade(self):
        """ open websocket connection """
        self.current.output['cmd'] = 'upgrade'
        self.current.output['user_id'] = self.current.user_id
        self.terminate_existing_login()
        self.current.user.bind_private_channel(self.current.session.sess_id)
        user_sess = UserSessionID(self.current.user_id)
        user_sess.set(self.current.session.sess_id)
        self.current.user.is_online(True)
        # Clean up the locale from session to allow it to be re-read from the user preferences after login
        for k in translation.DEFAULT_PREFS.keys():
            self.current.session[k] = ''

    def terminate_existing_login(self):
        existing_sess_id = UserSessionID(self.current.user_id).get()
        if existing_sess_id and self.current.session.sess_id != existing_sess_id:
            if Session(existing_sess_id).delete():
                log.info("EXISTING LOGIN DEDECTED, WE SHOULD LOGUT IT FIRST")
                self.current.user.send_client_cmd({
                    "cmd": "error", "error": "Login required", "code": 401},
                                                  via_queue=existing_sess_id)
                self.current.user.unbind_private_channel(existing_sess_id)

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
            except ObjectDoesNotExist:
                self.current.log.exception("Wrong username or another error occurred")
                pass
            except:
                raise
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
