# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

import gettext as gettextlib


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
    5 mesajınız var

    Both singular and plural forms of the message should have the exactly same variables.

    Args:
        singular (str): The singular form of the message.
        plural (str): The plural form of the message.
        n (int): The integer, used to decide which form should be used.
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


def install(cat):
    """Installs a new translation catalog. All gettext functions will start using the new catalog."""
    global _catalog
    _catalog = cat
