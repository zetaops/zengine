# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

import gettext as gettextlib
import babel
from babel import dates
from babel import numbers
from zengine.log import log
from zengine.config import settings


installed_lang = ''
_catalog = gettextlib.NullTranslations()


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
    return _catalog.gettext(message)


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
    return _catalog.ngettext(singular, plural, n)


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


def _wrap_locale_formatter(fn):
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
        kwargs_ = {'locale': installed_lang}
        kwargs_.update(kwargs)
        try:
            formatted = fn(*args, **kwargs_)
        except babel.core.UnknownLocaleError:
            log.warning('Can\'t do formatting for language code {locale}, falling back to default {default}'.format(
                locale=installed_lang, default=settings.DEFAULT_LANG))
            kwargs_['locale'] = settings.DEFAULT_LANG
            formatted = fn(*args, **kwargs_)
        return formatted
    return wrapped_locale_formatter

# Date and Time
format_date =       _wrap_locale_formatter(dates.format_date)
format_datetime =   _wrap_locale_formatter(dates.format_datetime)
format_interval =   _wrap_locale_formatter(dates.format_interval)
format_time =       _wrap_locale_formatter(dates.format_time)
format_timedelta =  _wrap_locale_formatter(dates.format_timedelta)
get_timezone_name = _wrap_locale_formatter(dates.get_timezone_name)
get_day_names =     _wrap_locale_formatter(dates.get_day_names)
get_month_names =   _wrap_locale_formatter(dates.get_month_names)

# Number
format_decimal =    _wrap_locale_formatter(numbers.format_decimal)
format_number =     _wrap_locale_formatter(numbers.format_number)
format_scientific = _wrap_locale_formatter(numbers.format_scientific)
format_percent =    _wrap_locale_formatter(numbers.format_percent)
format_currency =   _wrap_locale_formatter(numbers.format_currency)


def _install(cat, lang_code):
    """Installs a new translation catalog. All gettext functions will start using the new catalog."""
    global _catalog, installed_lang
    _catalog = cat
    installed_lang = lang_code



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

_translation_catalogs = _load_translations()


def install_translation(langs):
    """Install the translations for one of the languages in `langs`.

    After this function is called, all translation functions will now
    return the translations for this language, as well performing
    time, money and number formattings appropriate to this locale.

    This function will handle the negotiation of the locale. `langs`
    parameter should contain the preferred languages of the user.
    The preferences will be compared with the languages that are
    available, and the most suitable one will be picked. For example,
    if the preferences are ['en_US', 'en'] and only 'en' is available,
    that will be picked automatically. If there are no translations
    available that would be suitable to the selected preference, the
    default language will be used instead.

    If the currently installed language is already the specified one,
    then calling this function is a no-op.

    Args:
         langs (`list` of `str`): The language code to be installed.
    """
    lang_code = babel.negotiate_locale(langs, _translation_catalogs.keys())
    # If the language is already installed, don't do anything
    if lang_code != installed_lang:
        catalog = _translation_catalogs.get(lang_code)
        # If the catalog doesn't exist, or if the language negotiation failed, warn and fall back to default
        if catalog is None:
            fallback = settings.DEFAULT_LANG
            log.warning('Unable to find requested language {lang}, falling back to {fallback}'.format(
                lang=lang_code, fallback=fallback))
            lang_code = fallback
            catalog = _translation_catalogs[lang_code]
        _install(catalog, lang_code)
        log.debug('Language {lang} installed.'.format(lang=lang_code))
