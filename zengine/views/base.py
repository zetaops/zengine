# -*-  coding: utf-8 -*-
"""Base view classes"""

# -
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import six
from pyoko.conf import settings
from zengine.lib.decorators import VIEW_METHODS
from zengine.lib.exceptions import ConfigurationError

NEXT_CMD_SPLITTER = '::'


class BaseView(object):
    """
    Base view class.
    """

    def __init__(self, current=None):
        self.object_form = None
        self.client_cmd = set()
        if current:
            self.set_current(current)

        if hasattr(current, 'spec') and current.spec.__class__.__name__ == 'UserTask':
            self.output['wf_meta'] = {
                'name': current.workflow_name,
                'current_lane': current.spec.lane,
                'current_step': current.task_name
            }

    def set_current(self, current):
        """
        Creates some aliases for attributes of ``current``.

        Args:
            current: :attr:`~zengine.engine.WFCurrent` object.
        """
        self.current = current
        self.input = current.input
        # self.req = current.request
        # self.resp = current.response
        self.output = current.output
        self.cmd = current.task_data['cmd']

        if self.cmd and NEXT_CMD_SPLITTER in self.cmd:
            self.cmd, self.next_cmd = self.cmd.split(NEXT_CMD_SPLITTER)
        else:
            self.next_cmd = None

    def _patch_form(self, serialized_form):
        """
        This method will be called by self.form_out() method
        with serialized form data.

        Args:
            serialized_form (dict): JSON serializable representation
             of form data.

        Note:
            This is a workaround till we decide and implement a
            better method for fine grained form customizations.
        """
        # since we dont have a method to modify properties of form that generated from models
        # I'm using an ugly workaround for now
        try:
            serialized_form['schema']['properties']['Permissions']['widget'] = 'filter_interface'
        except KeyError:
            pass
        try:
            serialized_form['schema']['properties']['RestrictedPermissions'][
                'widget'] = 'filter_interface'
        except KeyError:
            pass

    def _add_meta_props(self, _form):
        if hasattr(_form, 'META_TO_FORM_META'):
            self.output['meta'] = self.output.get('meta', {})
            for itm in _form.META_TO_FORM_META:
                if itm in _form.Meta.__dict__:
                    self.output['meta'][itm] = _form.Meta.__dict__[itm]

    def form_out(self, _form=None):
        """
        Renders form. Applies form modifiers, then writes
        result to response payload. If supplied, given form
        object instance will be used instead of view's
        default ObjectForm.

        Args:
             _form (:py:attr:`~zengine.forms.json_form.JsonForm`):
              Form object to override `self.object_form`
        """
        _form = _form or self.object_form
        self.output['forms'] = _form.serialize()
        self._add_meta_props(_form)
        self.output['forms']['grouping'] = _form.Meta.grouping
        self.output['forms']['constraints'] = _form.Meta.constraints
        self._patch_form(self.output['forms'])
        self.set_client_cmd('form')

    def reload(self):
        """
        Generic view for reloading client
        """
        self.set_client_cmd('reload')

    def reset(self):
        """
        Generic view for resetting current WF.
        """
        self.set_client_cmd('reset')

    def set_client_cmd(self, *args):
        """
        Adds given cmd(s) to ``self.output['client_cmd']``

        Args:
            *args: Client commands.
        """
        self.client_cmd.update(args)
        self.output['client_cmd'] = list(self.client_cmd)


class SimpleView(BaseView):
    """
    Simple form based views can be build  up on this class.

    We call self.%s_view() method with %s substituted with
    ``self.input['cmd']`` if given or with
    :attr:`DEFAULT_VIEW` which has ``show`` as
    default value.
    """
    DEFAULT_VIEW = 'show'

    def __init__(self, current):
        super(SimpleView, self).__init__(current)
        view = "%s_view" % (self.cmd or self.DEFAULT_VIEW)
        if view in self.__class__.__dict__:
            self.__class__.__dict__[view](self)

class ViewMeta(type):
    """
    Meta class that prepares CrudView's subclasses.

    Handles passing of default "Meta" class attributes and
    List/Object forms into subclasses.
    """
    registry = {}
    _meta = None

    def __new__(mcs, name, bases, attrs):
        new_class = super(ViewMeta, mcs).__new__(mcs, name, bases, attrs)
        if new_class.PATH:
            if new_class.ENABLED:
                VIEW_METHODS[new_class.PATH or new_class.__name__] = new_class
        else:
            if new_class.__name__ not in ['SysView', 'DevelView'] and new_class.PATH is not None:
                raise ConfigurationError("\"%s\" does not have a PATH property."
                                         " Class based system views should have a PATH" % new_class.__name__)

        return new_class

@six.add_metaclass(ViewMeta)
class SysView(BaseView):
    """
    base class for non-wf system views
    """
    PATH = ''
    ENABLED = True
    pass

class DevelView(SysView):
    """
    base class for non-wf system views
    """
    PATH = ''
    ENABLED = settings.DEBUG
    pass
