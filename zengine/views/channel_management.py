# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.forms import JsonForm
from zengine.views.crud import CrudView
from zengine.forms import fields
from zengine.messaging.model import Channel, Subscriber, Message
from pyoko import ListNode
from zengine.lib.utils import gettext as _, gettext_lazy as __
from pyoko.db.adapter.db_riak import BlockDelete, BlockSave
from pyoko.conf import settings
from pyoko.lib.utils import get_object_from_path

User = get_object_from_path(settings.USER_MODEL)


class NewChannelForm(JsonForm):
    class Meta:
        exclude = ['typ', 'code_name']


class SubscriberListForm(JsonForm):
    class Meta:
        inline_edit = ['choice']

    class SubscriberList(ListNode):
        choice = fields.Boolean(__(u"Choice"), type="checkbox")
        name = fields.String(__(u'Subscriber Name'))
        key = fields.String(hidden=True)


class ChannelListForm(JsonForm):
    class Meta:
        inline_edit = ['choice']

    class ChannelList(ListNode):
        choice = fields.Boolean(__(u"Choice"), type="checkbox")
        name = fields.String(__(u'Channel Name'))
        owner = fields.String(__(u'Channel Owner'))
        key = fields.String(hidden=True)


CHANNEL_CHOICE_TEXT = _(u"""Please choose channel or channels you want to do operation.
You should choose at least one channel for merging operation and
you should choose just one channel to split.""")


class ChannelManagement(CrudView):
    """
    It provides channel management which consists of editing,
    splitting, merging and moving operations of channel.
    """

    def channel_list(self):
        """
        Main screen for channel management.
        Channels listed and operations can be chosen on the screen.
        If there is an error message like non-choice,
        it is shown here.

        """

        if self.current.task_data.get('msg', False):
            if self.current.task_data.get('target_channel_key', False):
                self.current.output['msgbox'] = {'type': 'info',
                                                 "title": _(u"Successful Operation"),
                                                 "msg": self.current.task_data['msg']}
                del self.current.task_data['msg']
            else:
                self.show_warning_messages()

        self.current.task_data['new_channel'] = False
        _form = ChannelListForm(title=_(u'Public Channel List'), help_text=CHANNEL_CHOICE_TEXT)

        for channel in Channel.objects.filter(typ=15):
            owner_name = channel.owner.username
            _form.ChannelList(choice=False, name=channel.name, owner=owner_name, key=channel.key)

        _form.new_channel = fields.Button(_(u"Merge At New Channel"), cmd="create_new_channel")
        _form.existing_channel = fields.Button(_(u"Merge With An Existing Channel"),
                                               cmd="choose_existing_channel")
        _form.find_chosen_channel = fields.Button(_(u"Split Channel"), cmd="find_chosen_channel")
        self.form_out(_form)

    def channel_choice_control(self):
        """
        It controls errors. If there is an error,
        returns channel list screen with error message.
        """
        self.current.task_data['control'], self.current.task_data['msg'] \
            = self.selection_error_control(self.input['form'])
        if self.current.task_data['control']:
            self.current.task_data['option'] = self.input['cmd']
            self.current.task_data['split_operation'] = False
            keys, names = self.return_selected_form_items(self.input['form']['ChannelList'])
            self.current.task_data['chosen_channels'] = keys
            self.current.task_data['chosen_channels_names'] = names

    def create_new_channel(self):
        """
        Features of new channel are specified like channel's name, owner etc.
        """

        self.current.task_data['new_channel'] = True
        _form = NewChannelForm(Channel(), current=self.current)
        _form.title = _(u"Specify Features of New Channel to Create")
        _form.forward = fields.Button(_(u"Create"), flow="find_target_channel")
        self.form_out(_form)

    def save_new_channel(self):
        """
        It saves new channel according to specified channel features.

        """
        form_info = self.input['form']
        channel = Channel(typ=15, name=form_info['name'],
                          description=form_info['description'],
                          owner_id=form_info['owner_id'])
        channel.blocking_save()
        self.current.task_data['target_channel_key'] = channel.key

    def choose_existing_channel(self):
        """
        It is a channel choice list and chosen channels
        at previous step shouldn't be on the screen.
        """

        if self.current.task_data.get('msg', False):
            self.show_warning_messages()

        _form = ChannelListForm()
        _form.title = _(u"Choose a Channel Which Will Be Merged With Chosen Channels")

        for channel in Channel.objects.filter(typ=15).exclude(
                key__in=self.current.task_data['chosen_channels']):
            owner_name = channel.owner.username
            _form.ChannelList(choice=False, name=channel.name, owner=owner_name,
                              key=channel.key)

        _form.choose = fields.Button(_(u"Choose"))
        self.form_out(_form)

    def existing_choice_control(self):
        """
        It controls errors. It generates an error message
        if zero or more than one channels are selected.
        """
        self.current.task_data['existing'] = False
        self.current.task_data['msg'] = _(u"You should choose just one channel to do operation.")
        keys, names = self.return_selected_form_items(self.input['form']['ChannelList'])
        if len(keys) == 1:
            self.current.task_data['existing'] = True
            self.current.task_data['target_channel_key'] = keys[0]

    def split_channel(self):
        """
        A channel can be splitted to new channel or other existing channel.
        It creates subscribers list as selectable to moved.
        """

        if self.current.task_data.get('msg', False):
            self.show_warning_messages()

        self.current.task_data['split_operation'] = True
        channel = Channel.objects.get(self.current.task_data['chosen_channels'][0])

        _form = SubscriberListForm(title=_(u'Choose Subscribers to Migrate'))

        for subscriber in Subscriber.objects.filter(channel=channel):
            subscriber_name = subscriber.user.username
            _form.SubscriberList(choice=False, name=subscriber_name, key=subscriber.key)

        _form.new_channel = fields.Button(_(u"Move to a New Channel"), cmd="create_new_channel")
        _form.existing_channel = fields.Button(_(u"Move to an Existing Channel"),
                                               cmd="choose_existing_channel")
        self.form_out(_form)

    def subscriber_choice_control(self):
        """
        It controls subscribers choice and generates
        error message if there is a non-choice.
        """
        self.current.task_data['option'] = None
        self.current.task_data['chosen_subscribers'], names = self.return_selected_form_items(
            self.input['form']['SubscriberList'])
        self.current.task_data[
            'msg'] = "You should choose at least one subscriber for migration operation."
        if self.current.task_data['chosen_subscribers']:
            self.current.task_data['option'] = self.input['cmd']
            del self.current.task_data['msg']

    def move_complete_channel(self):
        """
        Channels and theirs subscribers are moved
        completely to new channel or existing channel.
        """

        to_channel = Channel.objects.get(self.current.task_data['target_channel_key'])
        chosen_channels = self.current.task_data['chosen_channels']
        chosen_channels_names = self.current.task_data['chosen_channels_names']

        with BlockSave(Subscriber, query_dict={'channel_id': to_channel.key}):
            for s in Subscriber.objects.filter(channel_id__in=chosen_channels, typ=15):
                s.channel = to_channel
                s.save()

        with BlockDelete(Message):
            Message.objects.filter(channel_id__in=chosen_channels, typ=15).delete()

        with BlockDelete(Channel):
            Channel.objects.filter(key__in=chosen_channels).delete()

        self.current.task_data[
            'msg'] = _(u"Chosen channels(%s) have been merged to '%s' channel successfully.") % \
                     (', '.join(chosen_channels_names), to_channel.name)

    def move_chosen_subscribers(self):
        """
        After splitting operation, only chosen subscribers
        are moved to new channel or existing channel.
        """
        from_channel = Channel.objects.get(self.current.task_data['chosen_channels'][0])
        to_channel = Channel.objects.get(self.current.task_data['target_channel_key'])

        with BlockSave(Subscriber, query_dict={'channel_id': to_channel.key}):
            for subscriber in Subscriber.objects.filter(
                    key__in=self.current.task_data['chosen_subscribers']):
                subscriber.channel = to_channel
                subscriber.save()

        if self.current.task_data['new_channel']:
            self.copy_and_move_messages(from_channel, to_channel)

        self.current.task_data[
            'msg'] = _(u"Chosen subscribers and messages of them migrated from '%s' channel to "
                       u"'%s' channel successfully.") % (from_channel.name, to_channel.name)

    @staticmethod
    def copy_and_move_messages(from_channel, to_channel):
        """
         While splitting channel and moving chosen subscribers to new channel,
         old channel's messages are copied and moved to new channel.

         Args:
            from_channel (Channel object): move messages from channel
            to_channel (Channel object): move messages to channel
        """
        with BlockSave(Message, query_dict={'channel_id': to_channel.key}):
            for message in Message.objects.filter(channel=from_channel, typ=15):
                message.key = ''
                message.channel = to_channel
                message.save()

    def show_warning_messages(self, title=_(u"Incorrect Operation"), box_type='warning'):
        """
        It shows incorrect operations or successful operation messages.

        Args:
            title (string): title of message box
            box_type (string): type of message box (warning, info)
        """
        msg = self.current.task_data['msg']
        self.current.output['msgbox'] = {'type': box_type, "title": title, "msg": msg}
        del self.current.task_data['msg']

    @staticmethod
    def return_selected_form_items(form_info):
        """
        It returns chosen keys list from a given form.

        Args:
            form_info: serialized list of dict form data
        Returns:
            selected_keys(list): Chosen keys list
            selected_names(list): Chosen channels' or subscribers' names.
        """
        selected_keys = []
        selected_names = []
        for chosen in form_info:
            if chosen['choice']:
                selected_keys.append(chosen['key'])
                selected_names.append(chosen['name'])

        return selected_keys, selected_names

    def selection_error_control(self, form_info):
        """
        It controls the selection from the form according
        to the operations, and returns an error message
        if it does not comply with the rules.

        Args:
            form_info: Channel or subscriber form from the user

        Returns: True or False
                 error message

        """
        keys, names = self.return_selected_form_items(form_info['ChannelList'])
        chosen_channels_number = len(keys)

        if form_info['new_channel'] and chosen_channels_number < 2:
            return False, _(
                u"You should choose at least two channel to merge operation at a new channel.")
        elif form_info['existing_channel'] and chosen_channels_number == 0:
            return False, _(
                u"You should choose at least one channel to merge operation with existing channel.")
        elif form_info['find_chosen_channel'] and chosen_channels_number != 1:
            return False, _(u"You should choose one channel for split operation.")

        return True, None
