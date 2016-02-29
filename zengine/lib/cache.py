# -*-  coding: utf-8 -*-
"""
Base Cache object and some builtin subclasses of it.
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
    """
    Base cache object to implement specific cache object for each use case.

    Subclasses of this class can be consist of just a ```PREFIX``` attribute;

    .. code-block:: python

        class MyFooCache(Cache):
            PREFIX = 'FOO'

        # create cache object
        mycache = MyFooCache(*args)

        # set value
        mycache.set(value)

        # clear the whole PREFIX namespace
        MyFooCache.flush()
        # initial part(s) of keys can be used for finer control over keys.
        MyFooCache.flush('EXTRA_PREFIX')

    Or you can override the __init__ method to define strict positional
    args with docstrings.

    .. code-block:: python

        class MyFooCache(Cache):
            PREFIX = 'FOO'

            def __init__(self, model_name, obj_key):
                super(MyFooCache, self).__init__(model_name, obj_key)

    """
    PREFIX = 'DFT'
    SERIALIZE = True

    def __init__(self, *args, **kwargs):
        self.serialize = kwargs.get('serialize', self.SERIALIZE)
        self.key = self._make_key(args)

    @classmethod
    def _make_key(cls, args):
        return "%s:%s" % (cls.PREFIX, ':'.join(args))

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

    def delete(self):
        """
        Deletes the object.

        Returns:
            Cache backend response.
        """
        return cache.delete(self.key)

    def incr(self, delta=1):
        """
        Increment the value of item.

        Args:
            delta: Incrementation amount.

        Returns:
            Cache backend response.
        """
        return cache.incr(self.key, delta)

    def decr(self, delta=1):
        """
        Reduce the value of item.

        Args:
            delta: Reduction amount.

        Returns:
            Cache backend response.
        """
        return cache.decr(self.key, delta)

    def add(self, val):
        """
        Add given value to item (list)

        Args:
            val: A JSON serializable object.

        Returns:
            Cache backend response.
        """
        return cache.lpush(self.key, json.dumps(val) if self.serialize else val)

    def get_all(self):
        """
        Get all list items.

        Returns:
            Cache backend response.
        """
        result = cache.lrange(self.key, 0, -1)
        return (json.loads(item.decode('utf-8')) for item in result if
                item) if self.serialize else result

    def remove_all(self):
        """
        Remove items of the list.

        Returns:
            Cache backend response.
        """
        return cache.ltrim(self.key, 0, -1)

    def remove_item(self, val):
        """
        Removes given from the list.

        Args:
            val: Item

        Returns:
            Cache backend response.
        """
        return cache.lrem(self.key, json.dumps(val))

    @classmethod
    def flush(cls, *args):
        """
        Removes all keys in this current namespace
        If called from class itself, clears all keys starting with cls.PREFIX
        if called with args, clears keys starting with given cls.PREFIX + args

        Args:
            *args: Arbitrary number of arguments.

        Returns:
            List of removed keys.
        """
        return _remove_keys([], [(cls._make_key(args) if args else cls.PREFIX) + '*'])


class CatalogCache(Cache):
    """
    Cache object for the CatalogData.

    Args:
        lang_code: Language code
        key: Item key
    """
    PREFIX = 'CTDT'

    def __init__(self, lang_code, key):
        super(CatalogCache, self).__init__(lang_code, key)


class WFCache(Cache):
    """
    Cache object for workflow instances.

    Args:
        wf_token: Token of the workflow instance.
    """
    PREFIX = 'WF'

    def __init__(self, wf_token):
        super(WFCache, self).__init__(wf_token)


class ClearCache(Cache):
    """
    Empty cache object to flush all cache entries
    """
    PREFIX = ''


class Session(object):
    """
    Cache object for user sessions.
    Args:
        sessid: user session id.
    """
    PREFIX = 'SES'

    def __getitem__(self, key):
        key = self._make_key(key)
        return cache.get(key)

    def __delitem__(self, key):
        key = self._make_key(key)
        cache.delete(key)

    def __setitem__(self, key, value):
        key = self._make_key(key)
        cache.set(key, value)

    def __contains__(self, item):
        return bool(self.__getitem__(item))

    def __init__(self, sessid=''):
        self.key = ""
        self.key = self._make_key(sessid)


    def _make_key(self, args):
        return "%s%s" % (self.key or self.PREFIX, ":%s" % args if args else "")


    def flush(self):
        """
        Removes all contents attached to this session object.
         If sessid is empty, all sessions will be cleaned up.
        """
        return _remove_keys([], [self.key + '*'])
