# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json

from zengine.config import settings
from redis import Redis

redis_host, redis_port = settings.REDIS_SERVER.split(':')
cache = Redis(redis_host, redis_port)
#
# def dumper(obj):
#     try:
#         return obj.toJSON()
#     except:
#         return obj.__dict__
#
class Cache:
    def __init__(self, *args, **kwargs):
        self.args = args

        self._key_str = kwargs.pop('key', '')
        self.serialize = kwargs.pop('serialize')

    def _key(self):
        if not self._key_str:
            self._key_str = str('_'.join([repr(n) for n in self.args]))
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
        return ((json.loads(d.decode('utf-8')) if self.serialize else d)
                if d is not None
                else default)

    def set(self, val, lifetime=None):
        """
        set cache value

        :param val: any picklable object
        :param lifetime: exprition time in sec
        :return: val
        """
        cache.set(self._key(),
                  (json.dumps(val) if self.serialize else val))
                  # lifetime or settings.DEFAULT_CACHE_EXPIRE_TIME)
        return val

    def delete(self, *args):
        return cache.delete(self._key())

    def incr(self, delta=1):
        return cache.incr(self._key(), delta=delta)

    def decr(self, delta=1):
        return cache.decr(self._key(), delta=delta)

    def add(self, val):
        # add to list
        return cache.lpush(self._key(), json.dumps(val) if self.serialize else val)

    def get_all(self):
        # get all list items
        result = cache.lrange(self._key(), 0, -1)
        return (json.loads(item.decode('utf-8')) for item in result if item) if self.serialize else result

    def remove_all(self):
        # get all list items
        return cache.ltrim(self._key(), 0, -1)

    def remove_item(self, val):
        # get all list items
        return cache.lrem(self._key(), val)
