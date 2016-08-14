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


class KanalListelemeForm(JsonForm):
    """

    """

    class Meta:
        inline_edit = ['secim']

    class KanalListesi(ListNode):
        secim = fields.Boolean("Seçim", type="checkbox")
        ad = fields.String('Kanal Adı')
        sahip = fields.String('Kanal Sahibi')
        key = fields.String(hidden=True)


class AboneListelemeForm(JsonForm):
    """

    """

    class Meta:
        inline_edit = ['secim']

    class AboneListesi(ListNode):
        secim = fields.Boolean("Seçim", type="checkbox")
        ad = fields.String('Abone Adı')
        key = fields.String(hidden=True)


class Kanal_Yonetimi(CrudView):
    class Meta:
        model = "Channel"

    def kanal_listele(self):
        _form = KanalListelemeForm(current=self.current)
        _form.title = 'Kanal Listesi'

        for kanal in Channel.objects.filter():
            _form.KanalListesi(secim=False, ad=kanal.name, sahip=kanal.owner.username, key=kanal.key)

        _form.yeni_kanal = fields.Button("Yeni Bir Kanalda Birleştir", cmd="yeni_kanal_olustur")
        _form.varolan_kanal = fields.Button("Varolan Bir Kanalla Birleştir", cmd="varolan_kanal_sec")
        _form.kanali_bol = fields.Button("Kanalı Böl", cmd="kanali_bol")

        self.form_out(_form)

    def yeni_kanal_olustur(self):

        try:
            self.current.task_data['secilen_aboneler'] = secilen_dondur(self.input['form']['AboneListesi'])
        except:
            self.current.task_data['secilen_kanallar'] = secilen_dondur(self.input['form']['KanalListesi'])

        _form = JsonForm(Channel(), current=self.current)
        _form.title = 'Oluşturulacak Yeni Kanalın' \
                      ' Özelliklerini Belirleyiniz'
        _form.ilerle = fields.Button("İlerle")
        self.form_out(_form)

    def varolan_kanal_sec(self):

        try:
            self.current.task_data['secilen_aboneler'] = secilen_dondur(self.input['form']['AboneListesi'])
        except:
            self.current.task_data['secilen_kanallar'] = secilen_dondur(self.input['form']['KanalListesi'])

        _form = KanalListelemeForm(current=self.current)
        _form.title = 'Seçtiğiniz Kanalların Birleştirileceği Kanalı Seçiniz'

        for kanal in Channel.objects.filter():
            if not kanal.key in self.current.task_data['secilen_kanallar']:
                _form.KanalListesi(secim=False, ad=kanal.name, sahip=kanal.owner.username, key=kanal.key)

        _form.sec = fields.Button("Seç")
        self.form_out(_form)

    def kanali_bol(self):

        self.current.task_data['secilen_kanallar'] = secilen_dondur(self.input['form']['KanalListesi'])
        channel = Channel.objects.get(self.current.task_data['secilen_kanallar'][0])

        _form = AboneListelemeForm(current=self.current,
                                   title='Taşınacak Aboneleri Seçiniz')

        for abone in Subscriber.objects.filter(channel=channel):
            _form.AboneListesi(secim=True, ad=abone.name, key=abone.key)

        _form.yeni_kanal = fields.Button("Yeni Bir Kanala Taşı", cmd="yeni_kanal_olustur")
        _form.varolan_kanal = fields.Button("Varolan Bir Kanalla Taşı", cmd="varolan_kanal_sec")
        self.form_out(_form)

    def kanala_tasi(self):

        try:
            secilen_kanallar = secilen_dondur(self.input['form']['KanalListesi'])
            channel = Channel.objects.get(secilen_kanallar[0])
        except:
            channel = yeni_kanal_kaydet(self.input['form'])

        try:
            for abone in self.current.task_data['secilen_aboneler']:
                secilen_abone = Subscriber.objects.get(abone)
                secilen_abone.channel = channel
                secilen_abone.save()
                secilen_abone_mesaj_tasi(secilen_abone, channel, self.current.task_data['secilen_kanallar'][0])

        except:
            for kanal in self.current.task_data['secilen_kanallar']:
                secilen_kanal = Channel.objects.get(kanal)
                abone_ve_mesaj_tasi(secilen_kanal, channel)
                secilen_kanal.blocking_delete()


def yeni_kanal_kaydet(form_bilgi):
    channel = Channel()
    channel.typ = form_bilgi['typ']
    channel.name = form_bilgi['name']
    channel.code_name = form_bilgi['code_name']
    channel.description = form_bilgi['description']
    try:
        user = User.objects.get(form_bilgi['owner_id'])
        channel.owner = user
    except exceptions.MultipleObjectsReturned, exceptions.ObjectDoesNotExist:
        pass
    channel.blocking_save()

    return channel


def secilen_dondur(form_bilgi):
    secilenler = []
    for secilen in form_bilgi:
        if secilen['secim']:
            secilenler.append(secilen['key'])

    return secilenler


def abone_ve_mesaj_tasi(secilen_kanal, channel):
    for i in range(2):

        model = Subscriber if i == 0 else Message

        for tasinan in model.objects.filter(channel=secilen_kanal):
            tasinan.channel = channel
            tasinan.save()

    return


def secilen_abone_mesaj_tasi(abone, channel, kanal):
    kanal = Channel.objects.get(kanal)

    for i in range(2):

        k = 'sender' if i == 0 else 'receiver'

        for mesaj in Message.objects.filter(**{k: abone.user, 'channel': kanal}):
            mesaj.key = ''
            mesaj.save()
            mesaj = Message.objects.get(mesaj.key)
            mesaj.channel = channel
            mesaj.save()
