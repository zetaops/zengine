# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

CATALOG_DATA = []


def gettext(source_text):
    """
    Fake gettext object.

    Args:
        source_text: original text

    Returns:
        Translated text.
    """
    CATALOG_DATA.append(source_text)
    return source_text


def gettext_lazy(source_text):
    """
    Lazy version of :attr:`gettxt()`

    Args:
        source_text: Original text

    Returns:
        Translated text
    """
    CATALOG_DATA.append(source_text)
    return source_text
