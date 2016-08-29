# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2016 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

import pytest
from zengine.lib.test_utils import BaseTestCase
from zengine.lib import translation
from zengine.config import settings
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
        # Change the language to 'tr' to get the translated messages
        self.prepare_client('/change_language/', user=test_user)
        self.client.post(locale_language='tr', locale_datetime='tr', locale_number='tr')
        self.client.set_path('/i18n/', None)
        resp = self.client.post()
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
        initial_user = User.objects.get(username='super_user')
        # First, let's make the engine switch to a language other than the default
        self.prepare_client('/change_language/', user=initial_user)
        self.client.post(locale_language='tr', locale_datetime='tr', locale_number='tr')
        # This user doesn't have any language preferences
        test_user = User.objects.get(username='test_user2')
        self.prepare_client('/i18n/', user=test_user)
        resp = self.client.post()
        # Since no language preferences exist for this user, the engine should switch to the defaults
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
        self.prepare_client('/change_language/', user=test_user)
        self.client.post(locale_language='tr', locale_datetime='tr', locale_number='tr')
        # Next, we'll change specifically to the default language
        self.prepare_client('/change_language/', user=test_user)
        self.client.post(locale_language='en', locale_datetime='en', locale_number='en')
        self.client.set_path('/i18n/', None)
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
        # We'll connect with a language code that we don't have the translations for
        self.prepare_client('/change_language/', user=test_user)
        self.client.post(locale_language='klingon', locale_datetime='klingon', locale_number='klingon')
        self.client.set_path('/i18n/', None)
        resp = self.client.post()
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

    def test_mixed_locales(self):
        test_user = User.objects.get(username='super_user')
        # We'll request different language and locale codes
        self.prepare_client('/change_language/', user=test_user)
        self.client.post(locale_language='en', locale_datetime='en_GB', locale_number='tr_TR')
        self.client.set_path('/i18n/', None)
        resp = self.client.post()
        # The messages should be in English
        assert resp.json['message'] == _MSG_EN
        assert resp.json['untranslated'] == _MSG_UNTRANSLATED
        assert resp.json['singular'] == _MSG_EN_SINGULAR
        assert resp.json['plural'] == _MSG_EN_PLURAL
        assert resp.json['marked'] == _MSG_EN_MARKED
        assert resp.json['marked_translated'] == _MSG_EN_MARKED
        # The datetimes should be in Great Britain English format
        assert resp.json['datetime'] == '21 Jul 2016, 17:32:00'
        # The numbers should be in Turkish format
        assert resp.json['decimal'] == _MSG_TR_DECIMAL

    def test_load_user_prefs(self):
        test_user = User.objects.get(username='test_user')
        # 'test_user's localization preferences are set on his model as Turkish
        self.prepare_client('/i18n/', user=test_user)
        resp = self.client.post()
        assert resp.json['message'] == _MSG_TR
        assert resp.json['singular'] == _MSG_TR_SINGULAR
        assert resp.json['plural'] == _MSG_TR_PLURAL
        assert resp.json['marked'] == _MSG_EN_MARKED
        assert resp.json['marked_translated'] == _MSG_TR_MARKED
        assert resp.json['datetime'] == _MSG_TR_DATETIME
        assert resp.json['decimal'] == _MSG_TR_DECIMAL
        assert resp.json['second_day'] == _MSG_TR_SECOND_DAY
        assert resp.json['untranslated'] == _MSG_UNTRANSLATED

    def test_available_languages_locales(self):
        assert len(translation.available_translations) > 0
        assert len(translation.available_datetimes) > 0
        assert len(translation.available_numbers) > 0

        assert settings.DEFAULT_LANG in translation.available_translations.keys()

        for k, v in translation.available_translations.items():
            # This shouldn't throw any errors
            translation.InstalledLocale.install_language(k)
            # Make sure the human readable string is well-formed
            assert v != ''
            assert 'None' not in v

        for k, v in translation.available_datetimes.items():
            # This shouldn't throw any errors
            translation.InstalledLocale.install_locale(k, 'datetime')
            # Make sure the human readable string is well-formed
            assert v != ''
            assert 'None' not in v

        for k, v in translation.available_numbers.items():
            # This shouldn't throw any errors
            translation.InstalledLocale.install_locale(k, 'number')
            # Make sure the human readable string is well-formed
            assert v != ''
            assert 'None' not in v
            assert '123' in v and '456' in v and '789' in v
