# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.config import settings
from redis import Redis

redis_host, redis_port = settings.REDIS_SERVER.split(':')
cache = Redis(redis_host, redis_port)


class Cache:
    def __init__(self, *args):
        self.args = args
        self._key_str = ''

    def _key(self):
        if not self._key_str:
            self._key_str = (str('_'.join([repr(n) for n in self.args]))
                         if len(self.args) > 1 else self.args[0])
        return self._key_str

    def __unicode__(self):
        return 'Cache object for %s' % self.key

    def get(self, default=None):
        """
        return the cached value or default if it can't be found

        :param default: default value
        :return: cached value
        """
        d = cache.get(self._key())
        return d if d is not None else default

    def set(self, val, lifetime=None):
        """
        set cache value

        :param val: any picklable object
        :param lifetime: exprition time in sec
        :return: val
        """
        cache.set(self._key(), val,
                  lifetime or settings.DEFAULT_CACHE_EXPIRE_TIME)
        return val

    def delete(self, *args):
        return cache.delete(self._key())

    def incr(self, delta=1):
        return cache.incr(self._key(), delta=delta)

    def decr(self, delta=1):
        return cache.decr(self._key(), delta=delta)
