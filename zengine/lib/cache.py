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
        self._key = ''

    def key(self):
        if not self._key:
            self._key = (str('_'.join([repr(n) for n in self.args]))
                         if len(self.args) > 1 else self.args[0])
        return self._key

    def __unicode__(self):
        return 'Cache object for %s' % self.key


    def get(self, default=None):
        """
        cacheden donen degeri, o yoksa `default` degeri dondurur
        """
        d = cache.get(self.key)
        return d if d is not None else default

    def set(self, val=1, lifetime=None):
        """
        val :: atanacak deger (istege bagli bossa 1 atanir).
        lifetime :: önbellek süresi, varsayilan 100saat
        """
        cache.set(self.key, val, lifetime or settings.DEFAULT_CACHE_EXPIRE_TIME)
        return val

    def delete(self, *args):
        """
        cache degerini temizler
        """
        return cache.delete(self.key)

    def incr(self, delta=1):
        """
        degeri delta kadar arttirir
        """
        return cache.incr(self.key, delta=delta)

    def decr(self, delta=1):
        """
        degeri delta kadar azaltir
        """
        return cache.decr(self.key, delta=delta)
