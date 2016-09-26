# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.forms import JsonForm
from zengine.views.crud import CrudView
from ulakbus.models import User
from zengine.forms import fields
from zengine.messaging.model import Channel, Subscriber, Message
from pyoko import ListNode, exceptions
from zengine.lib.translation import gettext as _, gettext_lazy as __
import random
import time


class NewChannelForm(JsonForm):
    class Meta:
        exclude = ['typ', 'code_name']


class ChannelListForm(JsonForm):
    class Meta:
        inline_edit = ['choice']

    class ChannelList(ListNode):
        choice = fields.Boolean(__(u"Choice"), type="checkbox")
        name = fields.String(__(u'Channel Name'))
        owner = fields.String(__(u'Channel Owner'))
        key = fields.String(hidden=True)


class SubscriberListForm(JsonForm):
    class Meta:
        inline_edit = ['choice']

    class SubscriberList(ListNode):
        choice = fields.Boolean(__(u"Choice"), type="checkbox")
        name = fields.String(__(u'Subscriber Name'))
        key = fields.String(hidden=True)


class Channel_Management(CrudView):
    class Meta:
        model = "Channel"

    def channel_list(self):

        try:
            show_messages(self, self.current.task_data['title'], self.current.task_data['type'])
        except KeyError:
            pass

        _form = ChannelListForm(current=self.current, title=_(u'Public Channel List'))

        for channel in Channel.objects.filter(typ=15):
            owner_name = "%s %s" % (str(channel.owner.name), str(channel.owner.surname))
            _form.ChannelList(choice=False, name=channel.name, owner=owner_name, key=channel.key)

        _form.new_channel = fields.Button(_(u"Merge At New Channel"), cmd="create_new_channel")
        _form.existing_channel = fields.Button(_(u"Merge With An Existing Channel"), cmd="choose_existing_channel")
        _form.find_chosen_channel = fields.Button(_(u"Split Channel"), cmd="find_chosen_channel")
        self.form_out(_form)

    def channel_choice_control(self):
        self.current.task_data['msg'] = self.input['cmd']
        self.current.task_data['split_operation'] = False
        self.current.task_data['new_channel'] = False
        self.current.task_data['title'] = "Incorrect Operation"
        self.current.task_data['type'] = "warning"
        chosen_channels_number = len(return_chosen(self.input['form']['ChannelList']))

        if self.input['form']['new_channel'] == 1 and chosen_channels_number < 2:
            self.current.task_data[
                'msg'] = "You should choose at least two channel to merge operation at a new channel."
        elif self.input['form']['existing_channel'] == 1 and chosen_channels_number == 0:
            self.current.task_data[
                'msg'] = "You should choose at least one channel to merge operation with existing channel."
        elif self.input['form']['find_chosen_channel'] and chosen_channels_number != 1:
            self.current.task_data['msg'] = "You should choose one channel for split operation."

    def create_new_channel(self):

        self.current.task_data['new_channel'] = True
        if self.current.task_data['split_operation']:
            self.current.task_data['chosen_subscribers'] = return_chosen(self.input['form']['SubscriberList'])
        else:
            self.current.task_data['chosen_channels'] = return_chosen(self.input['form']['ChannelList'])

        _form = NewChannelForm(Channel(), current=self.current, title=_(u"Specify Features of New Channel to Create"))
        _form.forward = fields.Button(_(u"Create"), flow="find_target_channel")
        self.form_out(_form)

    def choose_existing_channel(self):

        if self.current.task_data['split_operation']:
            self.current.task_data['chosen_subscribers'] = return_chosen(self.input['form']['SubscriberList'])
        else:
            self.current.task_data['chosen_channels'] = return_chosen(self.input['form']['ChannelList'])

        _form = ChannelListForm(current=self.current)
        _form.title = _(u"Choose a Channel Which Will Be Merged With Chosen Channels")

        for channel in Channel.objects.filter(typ=15):
            if not channel.key in self.current.task_data['chosen_channels']:
                owner_name = "%s %s" % (str(channel.owner.name), str(channel.owner.surname))
                _form.ChannelList(choice=False, name=channel.name, owner=owner_name, key=channel.key)

        _form.choose = fields.Button(_(u"Choose"))
        self.form_out(_form)

    def find_chosen_channel(self):

        self.current.task_data['split_operation'] = True
        self.current.task_data['chosen_channels'] = return_chosen(self.input['form']['ChannelList'])
        self.current.task_data['msg'] = None

    def split_channel(self):

        if self.current.task_data['msg']:
            show_messages(self, 'Incorrect Operation', 'warning')

        channel = Channel.objects.get(self.current.task_data['chosen_channels'][0])

        _form = SubscriberListForm(current=self.current,
                                   title=_(u'Choose Subscribers to Migrate'))

        for subscriber in Subscriber.objects.filter(channel=channel):
            subscriber_name = "%s %s (%s)" % (subscriber.user.name, subscriber.user.surname, subscriber.user.username)
            _form.SubscriberList(secim=True, name=subscriber_name, key=subscriber.key)

        _form.new_channel = fields.Button(_(u"Move to a New Channel"), cmd="create_new_channel")
        _form.existing_channel = fields.Button(_(u"Move to an Existing Channel"), cmd="choose_existing_channel")
        self.form_out(_form)

    def subscriber_choice_control(self):
        self.current.task_data['msg'] = self.input['cmd']
        chosen_subscriber_number = len(return_chosen(self.input['form']['SubscriberList']))
        if chosen_subscriber_number == 0:
            self.current.task_data['msg'] = "You should choose at least one subscriber for migration operation."

    def find_target_channel(self):

        self.current.task_data['title'] = "Successful Operation"
        self.current.task_data['type'] = "info"

        try:
            chosen_channels = return_chosen(self.input['form']['ChannelList'])
            self.current.task_data['target_channel_key'] = chosen_channels[0]
        except:
            channel = save_new_channel(self.input['form'])
            self.current.task_data['target_channel_key'] = channel.key

    def move_complete_channel(self):

        to_channel = Channel.objects.get(self.current.task_data['target_channel_key'])
        chosen_channels = [Channel.objects.get(channel_key) for channel_key in
                           self.current.task_data['chosen_channels']]
        for from_channel in chosen_channels:
            for s in Subscriber.objects.filter(channel=from_channel, typ=15):
                s.channel = to_channel
                s.save()
            # for m in Message.objects.filter(channel = from_channel,typ = 15):
            #     m.blocking_delete()
            from_channel.blocking_delete()

            # for i in range(2):
            #     model = Subscriber if i == 0 else Message
            #     for moved in model.objects.filter(channel=from_channel, typ=15):
            #         moved.channel = to_channel
            #         moved.save()

        self.current.task_data['msg'] = "Chosen channels has been merged to '%s' channel successfully." % (
            to_channel.name)

    def move_chosen_subscribers(self):
        from_channel = Channel.objects.get(self.current.task_data['chosen_channels'][0])
        to_channel = Channel.objects.get(self.current.task_data['target_channel_key'])
        chosen_subscribers = [Subscriber.objects.get(subscriber_key) for subscriber_key in
                              self.current.task_data['chosen_subscribers']]
        for subscriber in chosen_subscribers:
            subscriber.channel = to_channel
            subscriber.save()

        if self.current.task_data['new_channel']:
            copy_and_move_messages(from_channel, to_channel)

        self.current.task_data[
            'msg'] = "Chosen subscribers and messages of them migrated from '%s' channel to '%s' channel successfully." % (
            from_channel.name, to_channel.name)


def save_new_channel(form_info):
    channel = Channel()
    channel.typ = 15
    channel.name = form_info['name']
    channel.description = form_info['description']
    try:
        user = User.objects.get(form_info['owner_id'])
        channel.owner = user
    except exceptions.MultipleObjectsReturned, exceptions.ObjectDoesNotExist:
        pass
    channel.save()
    return channel


def return_chosen(form_info):
    selected = []
    for chosen in form_info:
        if chosen['choice']:
            selected.append(chosen['key'])

    return selected


def copy_and_move_messages(from_channel, to_channel):
    for message in Message.objects.filter(channel=from_channel, typ=15):
        message.key = ''
        message.save()
        message = Message.objects.get(message.key)
        message.channel = to_channel
        message.save()


def show_messages(self, title, type):
    """
    Hatalı işlem, başarılı işlem gibi bir çok yerde kullanılan message kutularını
    her defasında tanımlamak yerine bu method yardımıyla kullanılmasını sağlar.

    Args:
        title (string): Mesaj kutusunun başlığı
        type (string): Mesaj kutusunun tipi (warning, info)

    """
    self.current.output['msgbox'] = {
        'type': type, "title": title,
        "msg": self.current.task_data['msg']}
