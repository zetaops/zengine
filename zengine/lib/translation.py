# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

import gettext as gettextlib
from babel import Locale, UnknownLocaleError, dates, numbers
from zengine.log import log
from zengine.config import settings


DEFAULT_PREFS = {
    'locale_language': settings.DEFAULT_LANG,
    'locale_datetime': settings.DEFAULT_LOCALIZATION_FORMAT,
    'locale_number': settings.DEFAULT_LOCALIZATION_FORMAT,
}


def _load_translations():
    translations = {}
    # `gettext` has support for domains, which can be used to seperate
    # the translations of one language into multiple files. We expect
    # all translations of a language to be in a single 'messages.mo' file.
    TRANSLATION_DOMAIN = 'messages'
    # For the default language, translations will be return without modification
    log.debug('Loading translations')
    translations[settings.DEFAULT_LANG] = gettextlib.NullTranslations()
    for language in settings.TRANSLATIONS:
        log.debug('Loading translation of language {lang}'.format(lang=language))
        translations[language] = gettextlib.translation(
            domain=TRANSLATION_DOMAIN,
            localedir=settings.TRANSLATIONS_DIR,
            languages=[language],
            fallback=False,
        )
    return translations


class InstalledLocale(object):
    language = DEFAULT_PREFS['locale_language']
    datetime = DEFAULT_PREFS['locale_datetime']
    number   = DEFAULT_PREFS['locale_number']
    _catalog = gettextlib.NullTranslations()
    _translation_catalogs = _load_translations()

    @classmethod
    def install_language(cls, language_code):
        """Install the translations for language specified by `language_code`.

        If we don't have translations for this language, then the default language will be used.

        If the language specified is already installed, then this is a no-op.
        """
        # Skip if the language is already installed
        if language_code == cls.language:
            return
        try:
            cls._catalog = cls._translation_catalogs[language_code]
            cls.language = language_code
            log.debug('Installed language %s', language_code)
        except KeyError:
            default = settings.DEFAULT_LANG
            log.warning('Unknown language %s, falling back to %s', language_code, default)
            cls._catalog = cls._translation_catalogs[default]
            cls.language = default

    @classmethod
    def install_locale(cls, locale_code, locale_type):
        """Install the locale specified by `language_code`, for localizations of type `locale_type`.

        If we can't perform localized formatting for the specified locale,
        then the default localization format will be used.

        If the locale specified is already installed for the selected type, then this is a no-op.
        """
        # Skip if the locale is already installed
        if locale_code == getattr(cls, locale_type):
            return
        try:
            # We create a Locale instance to see if the locale code is supported
            locale = Locale(locale_code)
            log.debug('Installed locale %s', locale_code)
        except UnknownLocaleError:
            default = settings.DEFAULT_LOCALIZATION_FORMAT
            log.warning('Unknown locale %s, falling back to %s', locale_code, default)
            locale = Locale(default)
        setattr(cls, locale_type, locale.language)


def gettext(message):
    """Mark a message as translateable, and translate it.

    All messages in the application that are translateable should be wrapped with this function.
    When importing this function, it should be renamed to '_'. For example:

    >>> from zengine.lib.translation import gettext as _
    >>> print(_('Hello, world!'))
    Merhaba, dünya!

    For the messages that will be formatted later on, instead of using the position-based
    formatting, key-based formatting should be used. This gives the translator an idea what
    the variables in the format are going to be, and makes it possible for the translator
    to reorder the variables. For example:

    >>> name, number = 'Elizabeth', 'II'
    >>> _('Queen %(name)s %(number)s') % {'name': name, 'number': number}
    Kraliçe II. Elizabeth

    The message returned by this function depends on the language of the current user.
    If this function is called before a language is installed (which is normally done
    by ZEngine when the user connects), this function will simply return the message
    without modification.

    Args:
        message (str): The input message.
    Returns:
        str: The translated message.
    """
    return InstalledLocale._catalog.gettext(message)


def ngettext(singular, plural, n):
    """Mark a message as translateable, and translate it considering plural forms.

    Some messages may need to change based on a number. For example, consider a message
    like the following:

    >>> def alert_msg(msg_count): print('You have %d %s' % (msg_count, 'message' if msg_count == 1 else 'messages'))
    >>> alert_msg(1)
    You have 1 message
    >>> alert_msg(5)
    You have 5 messages

    To translate this message, you can use ngettext to consider the plural forms:

    >>> from zengine.lib.translation import ngettext
    >>> def alert_msg(msg_count): print(ngettext('You have %(count)d message',
    ...                                          'You have %(count)d messages',
    ...                                          msg_count) % {'count': msg_count})
    >>> alert_msg(1)
    1 mesajınız var
    >>> alert_msg(5)
    5 mesajlarınız var

    When doing formatting, both singular and plural forms of the message should have the exactly same variables.

    Args:
        singular (str): The singular form of the message.
        plural (str): The plural form of the message.
        n (int): The number that is used to decide which form should be used.
    Returns:
        str: The correct pluralization, translated.
    """
    return InstalledLocale._catalog.ngettext(singular, plural, n)


def markonly(message):
    """Used to mark a message as translateable, without actually translating it.

    For example, consider a list literal that contains strings that should be translated, such as:

    >>> fruits = ['apple', 'banana', 'orange']

    These strings could be marked and translated at the same time with gettext:

    >>> from zengine.lib.translation import gettext as _
    >>> fruits = [_('apple'), _('banana'), _('orange')]

    However, this is undesireable if some operations need to be done on these strings before
    they are translated:

    >>> fruits[0] == 'apple'
    False

    In this case, the strings can be marked using this function, and translated later with gettext.
    >>> from zengine.lib.translation import markonly as N_
    >>> fruits = [N_('apple'), N_('banana'), N_('orange')]
    >>> fruits[0] == 'apple'
    True
    >>> for fruit in fruits: print(_(fruit))
    elma
    muz
    portakal

    Args:
        message (str): The input message.
    Returns:
        str: The input message, with no modifications. To do the actual translation,
            gettext should be called on this string when needed.
    """
    return message


def _wrap_locale_formatter(fn, locale_type):
    """Wrap a Babel data formatting function to automatically format for currently installed locale."""
    def wrapped_locale_formatter(*args, **kwargs):
        """A Babel formatting function, wrapped to automatically use the currently installed language.

        The wrapped function will not throw any exceptions for unknown locales,
        if Babel doesn't recognise the locale, we will simply fall back to
        the default language.

        The locale used by the wrapped function can be overriden by passing it a `locale` keyword.
        To learn more about this function, check the documentation of Babel for the function of
        the same name.
        """
        # Get the current locale from the class
        kwargs_ = {'locale': getattr(InstalledLocale, locale_type)}
        # By creating a dict then updating it, we allow locale to be overridden
        kwargs_.update(kwargs)
        try:
            formatted = fn(*args, **kwargs_)
        except UnknownLocaleError:
            log.warning('Can\'t do formatting for language code {locale}, falling back to default {default}'.format(
                locale=kwargs_['locale'], default=settings.DEFAULT_LANG))
            kwargs_['locale'] = settings.DEFAULT_LANG
            formatted = fn(*args, **kwargs_)
        return formatted
    return wrapped_locale_formatter

# Date and Time
format_date =       _wrap_locale_formatter(dates.format_date, 'datetime')
format_datetime =   _wrap_locale_formatter(dates.format_datetime, 'datetime')
format_interval =   _wrap_locale_formatter(dates.format_interval, 'datetime')
format_time =       _wrap_locale_formatter(dates.format_time, 'datetime')
format_timedelta =  _wrap_locale_formatter(dates.format_timedelta, 'datetime')
get_timezone_name = _wrap_locale_formatter(dates.get_timezone_name, 'datetime')
get_day_names =     _wrap_locale_formatter(dates.get_day_names, 'datetime')
get_month_names =   _wrap_locale_formatter(dates.get_month_names, 'datetime')

# Number
format_decimal =    _wrap_locale_formatter(numbers.format_decimal, 'number')
format_number =     _wrap_locale_formatter(numbers.format_number, 'number')
format_scientific = _wrap_locale_formatter(numbers.format_scientific, 'number')
format_percent =    _wrap_locale_formatter(numbers.format_percent, 'number')
format_currency =   _wrap_locale_formatter(numbers.format_currency, 'number')
