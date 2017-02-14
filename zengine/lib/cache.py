# -*-  coding: utf-8 -*-
"""
Base Cache object and some builtin subclasses of it.
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json

import time

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
                  (json.dumps(val) if self.serialize else val),
                  lifetime or settings.DEFAULT_CACHE_EXPIRE_TIME)
        return val

    def get_data_to_cache(self):
        return ""

    def get_or_set(self, lifetime=None):
        return self.get() or self.set(self.get_data_to_cache(), lifetime)

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
        return cache.ltrim(self.key, -1, 0)

    def remove_item(self, val):
        """
        Removes given item from the list.

        Args:
            val: Item

        Returns:
            Cache backend response.
        """
        return cache.lrem(self.key, json.dumps(val))

    @classmethod
    def flush(cls, *args):
        """
        Removes all keys of this namespace
        Without args, clears all keys starting with cls.PREFIX
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


class UserSessionID(Cache):
    """
    Cache object for the User -> Active Session ID.

    Args:
        user_id: User key
    """
    PREFIX = 'USID'
    SERIALIZE = False

    def __init__(self, user_id):
        if user_id:
            super(UserSessionID, self).__init__(user_id)


class KeepAlive(Cache):
    """
    Websocket keepalive request timestamp store

    Args:
        user_id: User key
        sess_id: Session id
    """
    PREFIX = 'KEEP'
    SERIALIZE = False
    SESSION_EXPIRE_TIME = 300  # sec

    def __init__(self, user_id=None, sess_id=None):
        self.user_id = user_id or Session(sess_id).get('user_id')
        self.sess_id = sess_id
        if self.user_id:
            super(KeepAlive, self).__init__(self.user_id)

    def update_or_expire_session(self):
        """
        Deletes session if keepalive request expired
        otherwise updates the keepalive timestamp value
        """
        if not hasattr(self, 'key'):
            return
        now = time.time()
        timestamp = float(self.get() or 0) or now
        sess_id = self.sess_id or UserSessionID(self.user_id).get()
        if sess_id and now - timestamp > self.SESSION_EXPIRE_TIME:
            Session(sess_id).delete()
            return False
        else:
            self.set(now)
            return True

    def reset(self):
        self.set(time.time())

    def is_alive(self):
        if not hasattr(self, 'key'):
            return
        return time.time() - float(self.get(0.0)) < self.SESSION_EXPIRE_TIME


class ClearCache(Cache):
    """
    Empty cache object to flush all cache entries
    """
    PREFIX = ''


class Session(object):
    """
    Redis based dict like session object to store user session data

    Examples:

        .. code-block:: python

            sess = Session(session_key)
            sess['user_data'] = {"foo":"bar"}
            sess

    Args:
        sessid: user session id.
    """
    PREFIX = 'SES'

    def __init__(self, sessid=''):
        self.key = ""
        self.sess_id = sessid
        self.key = self._make_key(sessid)

    def _j_load(self, val):
        return json.loads(val.decode())

    def __getitem__(self, key):
        val = self.get(key)
        if val:
            return val
        else:
            raise KeyError

    def __delitem__(self, key):
        key = self._make_key(key)
        cache.delete(key)

    def __setitem__(self, key, value):
        key = self._make_key(key)
        cache.set(key, json.dumps(value))

    def __contains__(self, item):
        try:
            self.__getitem__(item)
            return True
        except KeyError:
            return False

    def _make_key(self, args=None):
        return "%s%s" % (self.key or self.PREFIX, ":%s" % args if args else "")

    def _keys(self):
        return cache.keys(self._make_key() + "*")

    def get(self, key, default=None):
        key = self._make_key(key)
        val = cache.get(key)
        return self._j_load(val) if val else default

    def keys(self):
        return [k[len(self.key) + 1:] for k in self._keys()]

    def values(self):
        return (self._j_load(cache.get(k)) for k in self._keys())

    def items(self):
        return ((k[len(self.key) + 1:], self._j_load(cache.get(k))) for k in self._keys())

    def delete(self):
        """
        Removes all contents attached to this session object.
         If sessid is empty, all sessions will be cleaned up.
        """
        return _remove_keys([], [self.key + '*'])


class WFSpecNames(Cache):
    """

    """
    PREFIX = "WFSPECNAMES"

    def __init__(self):
        super(WFSpecNames, self).__init__('wf_spec_names')

    def get_data_to_cache(self):
        return self.get_data()

    @staticmethod
    def get_data():
        from zengine.models import BPMNWorkflow
        return BPMNWorkflow.objects.values_list('name', 'title', 'menu_category')

    def refresh(self):
        self.delete()
        self.get_or_set()
