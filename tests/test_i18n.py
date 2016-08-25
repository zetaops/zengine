# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

import pytest
from zengine.lib.test_utils import BaseTestCase
from zengine.models import User


_MSG_TR = 'Bu çevirilebilir bir mesajdır.'
_MSG_EN = 'This is a translateable message.'
_MSG_UNTRANSLATED = 'This message has not been translated.'
_MSG_EN_SINGULAR = 'One'
_MSG_EN_PLURAL = 'Many'
_MSG_TR_SINGULAR = 'Tek'
_MSG_TR_PLURAL = 'Çok'
_MSG_EN_MARKED = 'This message is marked, but not translated yet.'
_MSG_TR_MARKED = 'Bu mesaj işaretlendi, ancak henüz çevirilmedi.'
_MSG_EN_DATETIME = 'Jul 21, 2016, 5:32:00 PM'
_MSG_EN_DECIMAL = '1.235'
_MSG_EN_SECOND_DAY = 'Tuesday'
_MSG_TR_DATETIME = '21 Tem 2016 17:32:00'
_MSG_TR_DECIMAL = '1,235'
_MSG_TR_SECOND_DAY = 'Salı'


class TestCase(BaseTestCase):
    def test_translation(self):
        test_user = User.objects.get(username='super_user')
        # We'll connect with the 'tr' language code to get the translated message
        self.prepare_client('/i18n/', user=test_user)
        resp = self.client.post(lang_code='tr')
        assert resp.json['message'] == _MSG_TR
        assert resp.json['singular'] == _MSG_TR_SINGULAR
        assert resp.json['plural'] == _MSG_TR_PLURAL
        assert resp.json['marked'] == _MSG_EN_MARKED
        assert resp.json['marked_translated'] == _MSG_TR_MARKED
        assert resp.json['datetime'] == _MSG_TR_DATETIME
        assert resp.json['decimal'] == _MSG_TR_DECIMAL
        assert resp.json['second_day'] == _MSG_TR_SECOND_DAY
        # This message was not translated yet, so this message only should fall back to default message
        assert resp.json['untranslated'] == _MSG_UNTRANSLATED

    def test_default(self):
        test_user = User.objects.get(username='super_user')
        # First, let's make the engine switch to a language other than the default
        self.prepare_client('/i18n/', user=test_user)
        resp = self.client.post(lang_code='tr')
        assert resp.json['message'] == _MSG_TR
        # Next, we'll connect without a language code to get the default language
        self.prepare_client('/i18n/', user=test_user)
        resp = self.client.post()
        # Since no language code was given, the engine should switch back to default language
        assert resp.json['message'] == _MSG_EN
        assert resp.json['untranslated'] == _MSG_UNTRANSLATED
        assert resp.json['singular'] == _MSG_EN_SINGULAR
        assert resp.json['plural'] == _MSG_EN_PLURAL
        assert resp.json['marked'] == _MSG_EN_MARKED
        assert resp.json['marked_translated'] == _MSG_EN_MARKED
        assert resp.json['datetime'] == _MSG_EN_DATETIME
        assert resp.json['decimal'] == _MSG_EN_DECIMAL
        assert resp.json['second_day'] == _MSG_EN_SECOND_DAY

    def test_default_with_code(self):
        test_user = User.objects.get(username='super_user')
        # First, let's make the engine switch to a language other than the default
        self.prepare_client('/i18n/', user=test_user)
        resp = self.client.post(lang_code='tr')
        assert resp.json['message'] == _MSG_TR
        # Next, we'll connect specifically with the default language code
        self.prepare_client('/i18n/', user=test_user)
        resp = self.client.post()
        # The engine should have switched to the default language
        assert resp.json['message'] == _MSG_EN
        assert resp.json['untranslated'] == _MSG_UNTRANSLATED
        assert resp.json['singular'] == _MSG_EN_SINGULAR
        assert resp.json['plural'] == _MSG_EN_PLURAL
        assert resp.json['marked'] == _MSG_EN_MARKED
        assert resp.json['marked_translated'] == _MSG_EN_MARKED
        assert resp.json['datetime'] == _MSG_EN_DATETIME
        assert resp.json['decimal'] == _MSG_EN_DECIMAL
        assert resp.json['second_day'] == _MSG_EN_SECOND_DAY

    def test_fallback(self):
        test_user = User.objects.get(username='super_user')
        # We'll connect witha language code that we don't have the translations for
        self.prepare_client('/i18n/', user=test_user)
        resp = self.client.post(lang_code='klingon')
        # The engine should fall back to the default language since the translations are missing
        assert resp.json['message'] == _MSG_EN
        assert resp.json['untranslated'] == _MSG_UNTRANSLATED
        assert resp.json['singular'] == _MSG_EN_SINGULAR
        assert resp.json['plural'] == _MSG_EN_PLURAL
        assert resp.json['marked'] == _MSG_EN_MARKED
        assert resp.json['marked_translated'] == _MSG_EN_MARKED
        assert resp.json['datetime'] == _MSG_EN_DATETIME
        assert resp.json['decimal'] == _MSG_EN_DECIMAL
        assert resp.json['second_day'] == _MSG_EN_SECOND_DAY
