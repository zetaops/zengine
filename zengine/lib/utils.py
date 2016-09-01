# -*- coding: utf-8 -*-
from zengine.lib import translation


class DotDict(dict):
    """
    A dict object that support dot notation for item access.

    Slower that pure dict.
    """

    def __getattr__(self, attr):
        return self.get(attr, None)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def date_to_solr(d):
    """ converts DD-MM-YYYY to YYYY-MM-DDT00:00:00Z"""
    return "{y}-{m}-{day}T00:00:00Z".format(day=d[:2], m=d[3:5], y=d[6:]) if d else d


def solr_to_date(d):
    """ converts YYYY-MM-DDT00:00:00Z to DD-MM-YYYY """
    return "{day}:{m}:{y}".format(y=d[:4], m=d[5:7], day=d[8:10]) if d else d


def solr_to_year(d):
    """ converts YYYY-MM-DDT00:00:00Z to DD-MM-YYYY """
    return d[:4]

import re
def to_safe_str(s):
    """
    converts some (tr) non-ascii chars to ascii counterparts,
    then return the result as lowercase
    """
    # TODO: This is insufficient as it doesn't do anything for other non-ascii chars
    return re.sub(r'[^0-9a-zA-Z]+', '_', s.strip().replace(u'ğ', 'g').replace(u'ö', 'o').replace(
        u'ç', 'c').replace(u'Ç','c').replace(u'Ö', u'O').replace(u'Ş', 's').replace(
        u'Ü', 'u').replace(u'ı', 'i').replace(u'İ','i').replace(u'Ğ', 'g').replace(
        u'ö', 'o').replace(u'ş', 's').replace(u'ü', 'u').lower(), re.UNICODE)


def merge_truthy(*dicts):
    """Merge multiple dictionaries, keeping the truthy values in case of key collisions.

    Accepts any number of dictionaries, or any other object that returns a 2-tuple of
    key and value pairs when its `.items()` method is called.

    If a key exists in multiple dictionaries passed to this function, the values from the latter
    dictionary is kept. If the value of the latter dictionary does not evaluate to True, then
    the value of the previous dictionary is kept.

    >>> merge_truthy({'a': 1, 'c': 4}, {'a': None, 'b': 2}, {'b': 3})
    {'a': 1, 'b': 3, 'c': 4}
    """
    merged = {}
    for d in dicts:
        for k, v in d.items():
            merged[k] = v or merged.get(k, v)
    return merged


_Z_DOMAIN = 'zengine'

def gettext(message):
    """A wrapper around `zengine.lib.translation.gettext` that sets the correct domain for ZEngine."""
    return translation.gettext(message, domain=_Z_DOMAIN)

def gettext_lazy(message):
    """A wrapper around `zengine.lib.translation.gettext_lazy` that sets the correct domain for ZEngine."""
    return translation.gettext_lazy(message, domain=_Z_DOMAIN)
