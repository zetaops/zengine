# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from datetime import datetime
from collections import defaultdict
import gettext as gettextlib
from babel import Locale, UnknownLocaleError, dates, numbers, lists
from babel.support import LazyProxy
from zengine.log import log
from zengine.config import settings
import six



LazyProxy.__hash__ = lambda self: hash((iter(self._args), iter(self._kwargs.items())))
"""Patch LazyProxy to make it consistently hashable.

Assumes that LazyProxy will be used only with pure functions, or
that even if the function is impure, the results of the function
can be considered equal if the parameters are equal. This is the
case for the purposes of the translation system, however other
modules should take care using this class.

The monkey patching is performed because inheriting LazyProxy causes
infinite recursion due to the override of __getattr__ method of LazyProxy.
"""

DEFAULT_PREFS = {
    'locale_language': settings.DEFAULT_LANG,
    'locale_datetime': settings.DEFAULT_LOCALIZATION_FORMAT,
    'locale_number': settings.DEFAULT_LOCALIZATION_FORMAT,
}

# The domain used for all messages in the application.
# The .mo file of the application should have this name.
DEFAULT_DOMAIN = 'messages'


def _load_translations():
    all_translations = {}
    log.debug('Loading translations')
    for language in settings.TRANSLATIONS:
        translations = {}
        for domain, default_lang in settings.TRANSLATION_DOMAINS.items():
            if language == default_lang:
                # For the default language of the domain, use untranslated messages
                catalog = gettextlib.NullTranslations()
            else:
                # For other languages, we need to insert the translations
                log.debug(
                    'Loading translation of language {lang} for {domain}'.format(
                        lang=language, domain=domain))
                try:
                    catalog = gettextlib.translation(
                        domain=domain,
                        localedir=settings.TRANSLATIONS_DIR,
                        languages=[language],
                        fallback=False,
                    )
                except IOError:
                    log.error('Translations for language {lang} for {domain} not found! '
                              'Falling back to default language!'.format(lang=language,
                                                                         domain=domain))
                    catalog = gettextlib.NullTranslations()
            translations[domain] = catalog
        all_translations[language] = translations
    return all_translations


class InstalledLocale(object):
    # Force the first language install to swap out the
    # initial NullTranslations of `_active_catalogs`
    language = ''

    datetime = DEFAULT_PREFS['locale_datetime']
    number = DEFAULT_PREFS['locale_number']
    # Until ZEngine runs and translations get installed (i.e. when using the shell),
    # just show untranslated messages for everything
    _active_catalogs = defaultdict(gettextlib.NullTranslations)
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
            cls._active_catalogs = cls._translation_catalogs[language_code]
            cls.language = language_code
            log.debug('Installed language %s', language_code)
        except KeyError:
            default = settings.DEFAULT_LANG
            log.warning('Unknown language %s, falling back to %s', language_code, default)
            cls._active_catalogs = cls._translation_catalogs[default]
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


def gettext(message, domain=DEFAULT_DOMAIN):
    """Mark a message as translateable, and translate it.

    All messages in the application that are translateable should be wrapped with this function.
    When importing this function, it should be renamed to '_'. For example:

    .. code-block:: python

        from zengine.lib.translation import gettext as _
        print(_('Hello, world!'))
        'Merhaba, dünya!'

    For the messages that will be formatted later on, instead of using the position-based
    formatting, key-based formatting should be used. This gives the translator an idea what
    the variables in the format are going to be, and makes it possible for the translator
    to reorder the variables. For example:

    .. code-block:: python

        name, number = 'Elizabeth', 'II'
        _('Queen %(name)s %(number)s') % {'name': name, 'number': number}
        'Kraliçe II. Elizabeth'

    The message returned by this function depends on the language of the current user.
    If this function is called before a language is installed (which is normally done
    by ZEngine when the user connects), this function will simply return the message
    without modification.

    If there are messages containing unicode characters, in Python 2 these messages must
    be marked as unicode. Otherwise, python will not be able to correctly match these
    messages with translations. For example:

    .. code-block:: python

        print(_('Café'))
        'Café'
        print(_(u'Café'))
        'Kahve'

    Args:
        message (basestring, unicode): The input message.
        domain (basestring): The domain of the message. Defaults to 'messages', which
            is the domain where all application messages should be located.

    Returns:
        unicode: The translated message.
    """

    if six.PY2:
        return InstalledLocale._active_catalogs[domain].ugettext(message)
    else:
        return InstalledLocale._active_catalogs[domain].gettext(message)


def gettext_lazy(message, domain=DEFAULT_DOMAIN):
    """Mark a message as translatable, but delay the translation until the message is used.

    Sometimes, there are some messages that need to be translated, but the translation
    can't be done at the point the message itself is written. For example, the names of
    the fields in a Model can't be translated at the point they are written, otherwise
    the translation would be done when the file is imported, long before a user even connects.
    To avoid this, `gettext_lazy` should be used. For example:


    .. code-block:: python

        from zengine.lib.translation import gettext_lazy, InstalledLocale
        from pyoko import model, fields
        class User(model.Model):
             name = fields.String(gettext_lazy('User Name'))
        print(User.name.title)
        'User Name'
        
        InstalledLocale.install_language('tr')
        print(User.name.title)
        'Kullanıcı Adı'

    Args:
        message (basestring, unicode): The input message.
        domain (basestring): The domain of the message. Defaults to 'messages', which
            is the domain where all application messages should be located.
    Returns:
        unicode: The translated message, with the translation itself being delayed until
            the text is actually used.

    """
    return LazyProxy(gettext, message, domain=domain, enable_cache=False)


def ngettext(singular, plural, n, domain=DEFAULT_DOMAIN):
    """Mark a message as translateable, and translate it considering plural forms.

    Some messages may need to change based on a number. For example, consider a message
    like the following:

    .. code-block:: python

        def alert_msg(msg_count): print(
        'You have %d %s' % (msg_count, 'message' if msg_count == 1 else 'messages'))

        alert_msg(1)
        'You have 1 message'
        alert_msg(5)
        'You have 5 messages'

    To translate this message, you can use ngettext to consider the plural forms:

    .. code-block:: python

        from zengine.lib.translation import ngettext
        def alert_msg(msg_count): print(ngettext('You have %(count)d message',
                                                 'You have %(count)d messages',
                                                 msg_count) % {'count': msg_count})
        alert_msg(1)
        '1 mesajınız var'

        alert_msg(5)
        '5 mesajlarınız var'

    When doing formatting, both singular and plural forms of the message should
    have the exactly same variables.

    Args:
        singular (unicode): The singular form of the message.
        plural (unicode): The plural form of the message.
        n (int): The number that is used to decide which form should be used.
        domain (basestring): The domain of the message. Defaults to 'messages', which
            is the domain where all application messages should be located.
    Returns:
        unicode: The correct pluralization, translated.

    """

    if six.PY2:
        return InstalledLocale._active_catalogs[domain].ungettext(singular, plural, n)
    else:
        return InstalledLocale._active_catalogs[domain].ngettext(singular, plural, n)


def ngettext_lazy(singular, plural, n, domain=DEFAULT_DOMAIN):
    """Mark a message with plural forms translateable, and delay the translation
    until the message is used.

    Works the same was a `ngettext`, with a delaying functionality similiar to `gettext_lazy`.

    Args:
        singular (unicode): The singular form of the message.
        plural (unicode): The plural form of the message.
        n (int): The number that is used to decide which form should be used.
        domain (basestring): The domain of the message. Defaults to 'messages', which
                             is the domain where all application messages should be located.
    Returns:
        unicode: The correct pluralization, with the translation being
                 delayed until the message is used.
    """
    return LazyProxy(ngettext, singular, plural, n, domain=domain, enable_cache=False)


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
        message (unicode): The input message.
    Returns:
        unicode: The input message, with no modifications. To do the actual translation,
            gettext should be called on this string when needed.
    """
    return message


def _wrap_locale_formatter(fn, locale_type):
    """Wrap a Babel data formatting function to automatically format
    for currently installed locale."""

    def wrapped_locale_formatter(*args, **kwargs):
        """A Babel formatting function, wrapped to automatically use the
        currently installed language.

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
            log.warning(
                """Can\'t do formatting for language code {locale},
                           falling back to default {default}""".format(
                    locale=kwargs_['locale'],
                    default=settings.DEFAULT_LANG)
            )
            kwargs_['locale'] = settings.DEFAULT_LANG
            formatted = fn(*args, **kwargs_)
        return formatted

    return wrapped_locale_formatter


# Date and Time
format_date = _wrap_locale_formatter(dates.format_date, 'datetime')
format_datetime = _wrap_locale_formatter(dates.format_datetime, 'datetime')
format_interval = _wrap_locale_formatter(dates.format_interval, 'datetime')
format_time = _wrap_locale_formatter(dates.format_time, 'datetime')
format_timedelta = _wrap_locale_formatter(dates.format_timedelta, 'datetime')
get_timezone_name = _wrap_locale_formatter(dates.get_timezone_name, 'datetime')
get_day_names = _wrap_locale_formatter(dates.get_day_names, 'datetime')
get_month_names = _wrap_locale_formatter(dates.get_month_names, 'datetime')

# Number
format_decimal = _wrap_locale_formatter(numbers.format_decimal, 'number')
format_number = _wrap_locale_formatter(numbers.format_number, 'number')
format_scientific = _wrap_locale_formatter(numbers.format_scientific, 'number')
format_percent = _wrap_locale_formatter(numbers.format_percent, 'number')
format_currency = _wrap_locale_formatter(numbers.format_currency, 'number')
format_list = _wrap_locale_formatter(lists.format_list, 'number')


def _get_available_translations():
    translations = {}
    for language in InstalledLocale._translation_catalogs.keys():
        translations[language] = Locale(language).language_name
    return translations


available_translations = _get_available_translations()


def _get_available_locales(sample_formatter, sample_value):
    locales = {}
    for lcode in settings.LOCALIZATION_FORMATS:
        locales[lcode] = "{sample} - {name}".format(
            sample=sample_formatter(sample_value, locale=lcode),

            # For some languages, only the 2-character code has
            # a name, i.e. tr has a name but tr_TR doesn't
            name=Locale(lcode).language_name or Locale(lcode.split('_')[0]).language_name
        )
    return locales


available_datetimes = _get_available_locales(format_datetime, datetime.now().replace(
    # Just take the current year, rest of the date is hardcoded to provide a more descriptive sample
    month=7, day=25, hour=18, minute=35, second=0, microsecond=0))

available_numbers = _get_available_locales(format_decimal, 123456.789)
