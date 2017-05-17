# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import time

from zengine.lib.test_utils import BaseTestCase
from zengine.models import User
from zengine.messaging.model import Channel, Subscriber, Message
from pyoko.db.adapter.db_riak import BlockDelete
import random


class TestCase(BaseTestCase):
    def test_channel_management(self):
        # with BlockDelete(Channel):
        #     for channel in Channel.objects.filter(typ=15):
        #         channel.delete()
        #         for s in Subscriber.objects.filter(channel=channel):
        #             s.delete()
        #         for m in Message.objects.filter(channel=channel):
        #             m.delete()

        ch, sb, msg = create_test_data()
        time.sleep(2)

        # INCORRECT_OPERATIONS_CONTROLS

        user = User.objects.get(username='super_user')

        self.prepare_client('channel_management', user=user)
        resp = self.client.post()
        channel_list = resp.json['forms']['model']["ChannelList"]
        assert 'wf_meta' in resp.json
        assert resp.json['wf_meta']['name'] == 'channel_management'
        assert resp.json['wf_meta']['current_step'] == 'ChannelList'

        assert resp.json['forms']['schema']["title"] == 'Public Channel List'
        assert len(channel_list) == Channel.objects.filter(typ=15).count()

        resp = self.client.post(cmd="create_new_channel", form={'new_channel': 1, })
        assert resp.json['msgbox']['title'] == 'Incorrect Operation'
        assert 'new channel' in resp.json['msgbox']['msg']

        resp = self.client.post(cmd="choose_existing_channel", form={'existing_channel': 1})
        assert resp.json['msgbox']['title'] == 'Incorrect Operation'
        assert 'existing channel' in resp.json['msgbox']['msg']

        resp = self.client.post(cmd="find_chosen_channel", form={'find_chosen_channel': 1})
        assert resp.json['msgbox']['title'] == 'Incorrect Operation'
        assert 'split operation' in resp.json['msgbox']['msg']

        channel_list = resp.json['forms']['model']["ChannelList"]
        channel_list[0]['choice'] = True
        channel_list[1]['choice'] = True

        resp = self.client.post(cmd="find_chosen_channel",
                                form={'ChannelList': channel_list, 'find_chosen_channel': 1})
        assert resp.json['msgbox']['title'] == 'Incorrect Operation'
        assert 'split operation' in resp.json['msgbox']['msg']

        # MERGE_AT_NEW_CHANNEL

        channel_list = resp.json['forms']['model']["ChannelList"]

        # Two channels are chosen.
        channel_list[0]['choice'] = True
        channel_list[1]['choice'] = True
        # Subscriber counts of channels are taken.
        subs_ch1 = Subscriber.objects.filter(channel_id=channel_list[0]['key']).count()
        subs_ch2 = Subscriber.objects.filter(channel_id=channel_list[1]['key']).count()

        resp = self.client.post(cmd="create_new_channel",
                                form={'ChannelList': channel_list, 'new_channel': 1})
        # 'Specify' word is expected at form title.
        assert 'Specify' in resp.json['forms']['schema']['title']

        # New's channel features are specified.
        resp = self.client.post(flow="find_target_channel",
                                form={'description': "New_Trial_Channel", 'forward': 1,
                                      'name': 'New_Channel',
                                      'owner_id': "HjgPuHelltHC9USbj8wqd286vbS"})

        # It is checked come back again to channel screen.
        assert resp.json['forms']['schema']["title"] == 'Public Channel List'
        # Successful Operation title is checked.
        assert resp.json['msgbox']['title'] == 'Successful Operation'
        assert channel_list[0]['name'] and channel_list[1]['name'] and 'New_Channel' in \
                                                                       resp.json['msgbox']['msg']
        # Channel names and new created channel key are taken.
        channel_name_list, new_channel_key = find_channel_name_list(
            resp.json['forms']['model']["ChannelList"], 'New_Channel')
        ch.append(new_channel_key)
        msg.extend([msg.key for msg in Message.objects.filter(channel_id=new_channel_key)])
        # It is checked that 'New Channel' is there and chosen channels aren't there.
        assert 'New_Channel' in channel_name_list
        # Channel's owner is controlled.
        assert "HjgPuHelltHC9USbj8wqd286vbS" == Channel.objects.get('new_channel').owner.key
        assert channel_list[0]['name'] and channel_list[1]['name'] not in channel_name_list
        # New channel's subscriber count should be as much as chosen two channels.
        assert Subscriber.objects.filter(channel_id=new_channel_key).count() == subs_ch1 + subs_ch2
        # Two chosen channels are deleted and new channel is created.
        # Channel count should be decrease one.
        assert len(resp.json['forms']['model']["ChannelList"]) == len(channel_list) - 1
        # The messages are tested for deletion.
        assert Message.objects.filter(typ=15, channel_id=channel_list[0]['key']).count() == 0
        assert Message.objects.filter(typ=15, channel_id=channel_list[1]['key']).count() == 0

        # MERGE_WITH_AN_EXISTING_CHANNEL
        channel_list = resp.json['forms']['model']["ChannelList"]
        # One channel is selected.
        channel_list[0]['choice'] = True
        # Subscriber count of channel is taken.
        chosen_channel_count = Subscriber.objects.filter(channel_id=channel_list[0]['key']).count()

        resp = self.client.post(cmd="choose_existing_channel",
                                form={'ChannelList': channel_list, 'existing_channel': 1})
        assert 'wf_meta' in resp.json
        assert resp.json['wf_meta']['name'] == 'channel_management'
        assert resp.json['wf_meta']['current_step'] == 'ChooseExistingChannel'
        # Channel choosing screen is expected.
        assert 'Choose a Channel' in resp.json['forms']['schema']['title']
        exist_channel_list = resp.json['forms']['model']["ChannelList"]
        # It is checked that it is not shown on the screen.
        assert len(exist_channel_list) == len(channel_list) - 1
        # Existing channel is selected.
        exist_channel_list[0]['choice'] = True
        # Existing channel's subscriber count is taken.
        exs_channel_first_count = Subscriber.objects.filter(
            channel_id=exist_channel_list[0]['key']).count()
        resp = self.client.post(form={'ChannelList': exist_channel_list, 'choose': 1})
        # It is checked come back again to channel screen.
        assert resp.json['forms']['schema']["title"] == 'Public Channel List'
        # Successful Operation title is checked.
        assert resp.json['msgbox']['title'] == 'Successful Operation'
        # It is checked that two channels name's at the message.
        assert channel_list[0]['name'] and exist_channel_list[0]['name'] in resp.json['msgbox'][
            'msg']

        channel_name_list, new_channel_key = find_channel_name_list(
            resp.json['forms']['model']["ChannelList"], '')

        # It is checked that chosen channel name is not in screen,
        # exist channel is still there.
        assert exist_channel_list[0]['name'] in channel_name_list
        assert channel_list[0]['name'] not in channel_name_list

        # Existing channel's updated subscriber count is taken.
        assert Subscriber.objects.filter(channel_id=exist_channel_list[0][
            'key']).count() == chosen_channel_count + exs_channel_first_count
        # One chosen channel should be deleted. Thus, channel count should be decrease one.
        assert len(resp.json['forms']['model']["ChannelList"]) == len(channel_list) - 1
        # The messages are tested for deletion.
        assert Message.objects.filter(typ=15, channel_id=channel_list[0]['key']).count() == 0

        # SPLIT CHANNEL

        channel_list, chosen_channel = find_channel_to_choose(
            resp.json['forms']['model']["ChannelList"])
        # One channel is selected to split.
        # Chosen channels's subscriber and message counts are taken.
        split_ch_subs_count = Subscriber.objects.filter(channel_id=chosen_channel['key']).count()
        split_ch_msg_count = Message.objects.filter(channel_id=chosen_channel['key']).count()

        resp = self.client.post(cmd="find_chosen_channel",
                                form={'ChannelList': channel_list, 'find_chosen_channel': 1})
        # Chosen's channel subscribers are expected.
        assert 'Subscribers' in resp.json['forms']['schema']['title']
        subscriber_list = resp.json['forms']['model']["SubscriberList"]
        # Subscriber count at screen and at database should be equal.
        assert len(subscriber_list) == Subscriber.objects.filter(channel_id=chosen_channel['key'],
                                                                 typ=15).count()

        # SPLIT_OPERATION_INCORRECT_OPERATIONS

        resp = self.client.post(cmd="create_new_channel", form={'new_channel': 1})
        assert resp.json['msgbox']['title'] == 'Incorrect Operation'
        assert 'one subscriber' in resp.json['msgbox']['msg']

        resp = self.client.post(cmd="create_new_channel", form={'existing_channel': 1})
        assert resp.json['msgbox']['title'] == 'Incorrect Operation'
        assert 'one subscriber' in resp.json['msgbox']['msg']

        # SPLIT_OPERATION_TO_NEW_CHANNEL

        subscriber_list[0]['choice'] = True
        subscriber_list[1]['choice'] = True

        resp = self.client.post(cmd="create_new_channel",
                                form={'SubscriberList': subscriber_list, 'new_channel': 1})
        # New Create Channel screen is expected.
        assert 'Specify' in resp.json['forms']['schema']['title']
        # New channel's features are specified.
        resp = self.client.post(flow="find_target_channel",
                                form={'description': "New_Split_Channel", 'forward': 1,
                                      'name': 'New_Split_Channel',
                                      'owner_id': 'HjgPuHelltHC9USbj8wqd286vbS'})
        # It is checked come back again to channel screen.
        assert resp.json['forms']['schema']["title"] == 'Public Channel List'
        # Successful Operation title is checked.
        assert resp.json['msgbox']['title'] == 'Successful Operation'
        # Success operation message should contain two channels.
        assert chosen_channel['name'] and 'New_Split_Channel' in resp.json['msgbox']['msg']

        channel_name_list, new_channel_key = find_channel_name_list(
            resp.json['forms']['model']["ChannelList"], 'New_Split_Channel')

        ch.append(new_channel_key)
        msg.extend([m.key for m in Message.objects.filter(channel_id=new_channel_key)])
        # Two channels should be in channel name list.
        assert chosen_channel['name'] and 'New_Split_Channel' in channel_name_list
        # New channel's subscriber and message counts are taken.
        new_ch_subs_count = Subscriber.objects.filter(channel_id=new_channel_key).count()
        new_ch_msg_count = Message.objects.filter(channel_id=new_channel_key).count()
        # Splitted channel updated subsriber count should be equal to difference between first
        # subscriber count and new channel's subscriber count.
        assert Subscriber.objects.filter(
            channel_id=chosen_channel['key']).count() == split_ch_subs_count - new_ch_subs_count
        # Splitted channel and new channel's message histories should be equal.
        assert new_ch_msg_count == split_ch_msg_count

        # New channel is created, channel count should increase one.
        assert len(resp.json['forms']['model']["ChannelList"]) == len(channel_list) + 1

        # SPLIT_OPERATION_TO_EXISTING_CHANNEL

        channel_list, chosen_channel = find_channel_to_choose(
            resp.json['forms']['model']["ChannelList"])
        # One channel is selected to split.

        chosen_channel['choice'] = True
        split_ch_subs_count = Subscriber.objects.filter(channel_id=chosen_channel['key']).count()

        resp = self.client.post(cmd="find_chosen_channel",
                                form={'ChannelList': channel_list, 'find_chosen_channel': 1})
        subscriber_list = resp.json['forms']['model']["SubscriberList"]

        # Two subscribers are selected.
        subscriber_list[0]['choice'] = True
        subscriber_list[1]['choice'] = True

        resp = self.client.post(cmd="choose_existing_channel",
                                form={'SubscriberList': subscriber_list, 'existing_channel': 1})

        # Channel choosing screen is expected.
        assert 'Choose a Channel' in resp.json['forms']['schema']['title']

        # Selectable channel count should be less than channel count. Not being itself.
        exist_channel_list = resp.json['forms']['model']["ChannelList"]
        assert len(exist_channel_list) == len(channel_list) - 1
        # One existing channel is selected.
        exist_channel_list[0]['choice'] = True
        # Existing channel's subscriber count is taken.
        exs_channel_first_count = Subscriber.objects.filter(
            channel_id=exist_channel_list[0]['key']).count()
        resp = self.client.post(form={'ChannelList': exist_channel_list, 'choose': 1})

        # It is checked come back again to channel screen.
        assert resp.json['forms']['schema']["title"] == 'Public Channel List'
        # Successful Operation title is checked.
        assert resp.json['msgbox']['title'] == 'Successful Operation'
        assert chosen_channel['name'] and exist_channel_list[0]['name'] in resp.json['msgbox'][
            'msg']
        channel_name_list, new_channel_key = find_channel_name_list(
            resp.json['forms']['model']["ChannelList"])

        # Two channels should be screen.
        assert chosen_channel['name'] and exist_channel_list[0]['name'] in channel_name_list

        # Existing channel's updated subscriber count should increase 2.
        assert Subscriber.objects.filter(
            channel_id=exist_channel_list[0]['key']).count() == exs_channel_first_count + 2

        # Splitted channel's updated subscriber count should decrease 2.
        assert Subscriber.objects.filter(
            channel_id=chosen_channel['key']).count() == split_ch_subs_count - 2
        # Channel count at screen should remain same.
        assert len(channel_list) == len(resp.json['forms']['model']["ChannelList"])

        delete_test_data(ch, sb, msg)


def find_channel_name_list(form_info, name=None):
    """

    Args:
        form_info: form which contains channel info. (name, choice, key)
        name(str): channel name

    Returns:
        channel_name_list(list): Name list of channels in form
        new_channel_key(str): New created channel's key.

    """
    channel_name_list = []
    new_channel_key = ''
    for channel in form_info:
        channel_name_list.append(channel['name'])
        if name and name in channel['name']:
            new_channel_key = channel['key']

    return channel_name_list, new_channel_key


def find_channel_to_choose(channel_list):
    """
    A channel which has at least two subscriber is found and choice of channel
    is updated to True.

    Args:
        channel_list: form which contains channel info. (name, choice, key)

    Returns:
        channel_list: updated with choice True
        chosen_channel:(object) A channel which has at least 2 subscriber.

    """
    for i, c in enumerate(channel_list):
        if Subscriber.objects.filter(typ=15, channel_id=c['key']).count() >= 2:
            channel_list[i]['choice'] = True
            chosen_channel = channel_list[i]
            return channel_list, chosen_channel


def create_test_data():
    # Channels, subscribers and messages are created for test environment.
    ch = sb = msg = []
    a = [u for u in User.objects.all() if u.username != None]
    for i in range(5):
        c = Channel(name="%i Class" % random.randrange(1000, 9000), owner=random.choice(a),
                    typ=15).save()
        ch.append(c.key)
        for i in range(2):
            u = random.choice(a)
            s = Subscriber(channel=c, typ=15, name=u.username, user=u).save()
            sb.append(s.key)
        for i in range(2):
            m = Message(channel=c, typ=15, sender=random.choice(a),
                        receiver=random.choice(a), msg_title=str(random.randrange(1, 1000)),
                        body=str(random.randrange(1, 1000))).save()
            msg.append(m.key)
    return ch, sb, msg


def delete_test_data(ch, sb, msg):
    # Created channels, subscribers and messages are deleted.
    with BlockDelete(Channel):
        Channel.objects.filter(key__in=ch).delete()
    with BlockDelete(Subscriber):
        Subscriber.objects.filter(key__in=sb).delete()
    with BlockDelete(Message):
        Message.objects.filter(key__in=msg).delete()
