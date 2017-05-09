# -*-  coding: utf-8 -*-
"""
This module holds Current and WFCurrent classes.
Current is carrier object between client request and view methods.
 WFCurrent extends Current and adds properties specific to workflows tasks.
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from __future__ import division
from __future__ import print_function, absolute_import, division

from uuid import uuid4

import lazy_object_proxy
from SpiffWorkflow.specs import WorkflowSpec

from pyoko.lib.utils import get_object_from_path, lazy_property
from zengine import signals
from zengine.client_queue import ClientQueue
from zengine.config import settings
from zengine.lib.utils import merge_truthy
from zengine.lib import translation
from zengine.lib.cache import Session
from zengine.log import log
from zengine.models import WFCache
from zengine.models import WFInstance

DEFAULT_LANE_CHANGE_MSG = {
    'title': settings.MESSAGES['lane_change_message_title'],
    'body': settings.MESSAGES['lane_change_message_body'],
}




class Current(object):
    """
    This object holds the whole state of the app for passing to view methods (views/tasks)

    :type spec: WorkflowSpec | None
    :type session: Session | None
    """

    def __init__(self, **kwargs):

        self.task_data = {'cmd': None}
        self.session = Session()
        self.headers = {}
        self.input = {}  # when we want to use engine functions independently,
        self.output = {}  # we need to create a fake current object
        try:
            self.session = kwargs['session']
            self.input = kwargs['input']
        except KeyError:
            self.request = kwargs.pop('request', {})
            self.response = kwargs.pop('response', {})
            if 'env' in self.request:
                self.session = self.request.env['session']
                self.input = self.request.context['data']
                self.output = self.request.context['result']

        self.remote_addr = None
        self.user_id = self.session.get('user_id')
        self.role_id = self.session.get('role_id')

        self.log = log
        self.pool = {}
        AuthBackend = get_object_from_path(settings.AUTH_BACKEND)
        self.auth = lazy_object_proxy.Proxy(lambda: AuthBackend(self))
        self.user = lazy_object_proxy.Proxy(lambda: self.auth.get_user())
        self.role = lazy_object_proxy.Proxy(lambda: self.auth.get_role())
        log.debug("\n\nINPUT DATA: %s" % self.input)
        self.permissions = []

    @lazy_property
    def client_queue(self):
        """
        A lazy proxy for ClientQueue object.

        Returns: ClientQueue
        """
        return ClientQueue(self.user_id, self.session.key)

    @lazy_property
    def locale(self):
        locale_types = translation.DEFAULT_PREFS.keys()
        # Check the session for preference.
        locale_prefs = {ltype: self.session.get(ltype) for ltype in locale_types}
        # If preference in session is missing, read it from user model
        if not all(locale_prefs.values()):
            user = self.auth.get_user()
            # Read the preferences from user model
            locale_prefs = merge_truthy(locale_prefs, {ltype: getattr(user, ltype) for ltype in locale_types})
            # If preference in user model is missing too (or anonymous user), use the default
            if not all(locale_prefs.values()):
                locale_prefs = merge_truthy(locale_prefs, translation.DEFAULT_PREFS)
            # Save the preferences that are used to the session
            for k, v in locale_prefs.items():
                self.session[k] = v
        return locale_prefs

    def write_output(self, msg, json_msg=None):
        """
        Write to client without waiting to return of the view method

        Args:
            msg: Any JSON serializable object
            json_msg: JSON string
        """
        return self.client_queue.send_to_queue(msg, json_msg)

    def set_message(self, title, msg, typ, url=None):
        """
        Sets user notification message.

        Args:
            title: Msg. title
            msg:  Msg. text
            typ: Msg. type
            url: Additional URL (if exists)

        Returns:
            Message ID.
        """
        return self.user.send_notification(title=title,
                                           message=msg,
                                           typ=typ,
                                           url=url)

    @lazy_property
    def is_auth(self):
        """
        A property that indicates if current user is logged in or not.

        Returns:
            Boolean.
        """
        if self.user_id is None:
            self.user_id = self.session.get('user_id')
        return bool(self.user_id)

    def has_permission(self, perm):
        """
        Checks if current user (or role) has the given permission.

        Args:
            perm: Permmission code or object.
             Depends on the :attr:`~zengine.auth.auth_backend.AuthBackend` implementation.

        Returns:
            Boolean.
        """
        return self.user.superuser or self.auth.has_permission(perm)

    def get_permissions(self):
        """
        Returns permission objects.

        Returns:
            Permission objects or codes.
            Depends on the :attr:`~zengine.auth.auth_backend.AuthBackend` implementation.
        """
        return self.auth.get_permissions()

    def msg_box(self, msg, title=None, typ='info'):
        """
        Create a message box

        :param str msg:
        :param str title:
        :param str typ: 'info', 'error', 'warning'
        """
        self.output['msgbox'] = {'type': typ, "title": title or msg[:20], "msg": msg}


class WFCurrent(Current):
    """
    Workflow specific version of Current object
    """

    def __init__(self, **kwargs):
        super(WFCurrent, self).__init__(**kwargs)
        self.workflow_name = kwargs.pop('workflow_name', '')
        self.spec = None
        self.workflow = None
        self.task_type = ''
        self.task = None
        self.pool = {}
        self.flow_enabled = True
        self.task_name = ''
        self.activity = ''
        self.lane_permission = ''
        self.lane_relations = ''
        self.old_lane = ''
        self.lane_owners = None
        self.lane_name = ''
        self.lane_id = ''

        if 'token' in self.input:
            self.token = self.input['token']
            # log.info("TOKEN iNCOMiNG: %s " % self.token)
            self.new_token = False
        else:
            self.token = uuid4().hex
            self.new_token = True
            # log.info("TOKEN NEW: %s " % self.token)

        self.wf_cache = WFCache(self)
        self.set_client_cmds()

    def get_wf_link(self):
        """
        Create an "in app" anchor for accessing this workflow instance.

        Returns: String. Anchor link.

        """
        return "#cwf/%s/%s" % (self.workflow_name, self.token)

    def sendoff_current_user(self):
        """
        Tell current user that s/he finished it's job for now.
        We'll notify if workflow arrives again to his/her WF Lane.
        """
        msgs = self.task_data.get('LANE_CHANGE_MSG', DEFAULT_LANE_CHANGE_MSG)
        self.msg_box(title=msgs['title'], msg=msgs['body'])

    def invite_other_parties(self, possible_owners):
        """
        Invites the next lane's (possible) owner(s) to participate
        """
        signals.lane_user_change.send(sender=self.user,
                                      current=self,
                                      old_lane=self.old_lane,
                                      possible_owners=possible_owners
                                      )

    def _set_lane_data(self):
        # TODO: Cache lane_data in process
        if 'lane_data' in self.spec.data:
            lane_data = self.spec.data['lane_data']
            self.lane_name = lane_data['name']
            self.lane_id = self.spec.lane_id or ''
            # If there is a lane, create the permission for it
            if self.spec.lane_id:
                self.lane_permission = '{}.{}'.format(self.workflow_name, self.spec.lane_id)
            if 'relations' in lane_data:
                self.lane_relations = lane_data['relations']
            if 'owners' in lane_data:
                self.lane_owners = lane_data['owners']
            self.lane_auto_sendoff = 'False' not in lane_data.get('auto_sendoff', '')
            self.lane_auto_invite = 'False' not in lane_data.get('auto_invite', '')

    def _update_task(self, task):
        """
        Assigns current task step to self.task
        then updates the task's data with self.task_data

        Args:
            task: Task object.
        """
        self.task = task
        self.task.data.update(self.task_data)
        self.task_type = task.task_spec.__class__.__name__
        self.spec = task.task_spec
        self.task_name = task.get_name()
        self.activity = getattr(self.spec, 'service_class', '')
        self._set_lane_data()

    def set_client_cmds(self):
        """
        This is method automatically called on each request and
        updates "object_id", "cmd" and "flow"  client variables
        from current.input.

        "flow" and "object_id" variables will always exists in the
        task_data so app developers can safely check for their
        values in workflows.
        Their values will be reset to None if they not exists
        in the current input data set.

        On the other side, if there isn't a "cmd" in the current.input
        cmd will be removed from task_data.

        """
        self.task_data['cmd'] = self.input.get('cmd')

        self.task_data['flow'] = self.input.get('flow')

        filters = self.input.get('filters', {})

        try:
            if isinstance(filters, dict):
                # this is the new form, others will be removed when ui be ready
                self.task_data['object_id'] = filters.get('object_id')['values'][0]
            elif filters[0]['field'] == 'object_id':
                self.task_data['object_id'] = filters[0]['values'][0]
        except:
            if 'object_id' in self.input:
                self.task_data['object_id'] = self.input.get('object_id')
