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

REMOVE_SCRIPT = """
local keys = redis.call('keys', ARGV[1])
for i=1, #keys, 5000 do
    redis.call('del', unpack(keys, i, math.min(i+4999, #keys)))
end
return keys
"""

_remove_keys = cache.register_script(REMOVE_SCRIPT)

class Cache(object):
    PREFIX = 'DFT'
    SERIALIZE = True



    def __init__(self, *args, **kwargs):
        self.serialize = kwargs.get('serialize', self.SERIALIZE)
        self.key = "%s:%s" % (self.PREFIX, ':'.join(args))

    def __unicode__(self):
        return 'Cache object for %s' % self.key

    def get(self, default=None):
        """
        return the cached value or default if it can't be found

        :param default: default value
        :return: cached value
        """
        d = cache.get(self.key)
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
        cache.set(self.key,
                  (json.dumps(val) if self.serialize else val))
        # lifetime or settings.DEFAULT_CACHE_EXPIRE_TIME)
        return val

    def delete(self, *args):
        return cache.delete(self.key)

    def incr(self, delta=1):
        return cache.incr(self.key, delta=delta)

    def decr(self, delta=1):
        return cache.decr(self.key, delta=delta)

    def add(self, val):
        # add to list
        return cache.lpush(self.key, json.dumps(val) if self.serialize else val)

    def get_all(self):
        # get all list items
        result = cache.lrange(self.key, 0, -1)
        return (json.loads(item.decode('utf-8')) for item in result if
                item) if self.serialize else result

    def remove_all(self):
        # get all list items
        return cache.ltrim(self.key, 0, -1)

    def remove_item(self, val):
        # get all list items
        return cache.lrem(self.key, json.dumps(val))

    @classmethod
    def flush(cls):
        """
        removes all keys in this current namespace
        If called from class itself, clears all keys starting with cls.PREFIX
        if called from class instance, clears keys starting with given key.
        :return: list of removed keys
        """
        return _remove_keys([], [getattr(cls, 'key', cls.PREFIX) + '*'])



class NotifyCache(Cache):
    PREFIX = 'NTFY'

    def __init__(self, user_id):
        super(NotifyCache, self).__init__(user_id)

class CatalogCache(Cache):
    PREFIX = 'CTDT'

    def __init__(self, lang_code, key):
        super(CatalogCache, self).__init__(lang_code, key)


class WFCache(Cache):
    PREFIX = 'WF'

    def __init__(self, wf_token):
        super(WFCache, self).__init__(wf_token)
