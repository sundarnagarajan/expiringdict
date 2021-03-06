'''
Dictionary with auto-expiring values for caching purposes.

Expiration happens on any access, object is locked during cleanup from expired
values. Can not store more than max_len elements - the oldest will be deleted.

>>> ExpiringDict(max_len=100, max_age_seconds=10)

The values stored in the following way:
{
    key1: (value1, created_time1),
    key2: (value2, created_time2)
}

NOTE: iteration over dict and also keys() do not remove expired values!
'''

import time
from threading import RLock
import sys

try:
    from collections import OrderedDict
except ImportError:
    # Python < 2.7
    from ordereddict import OrderedDict


class ExpiringDict(OrderedDict):
    def __init__(self, *args, **kwargs):
        '''
        ExpiringDict-specific kwargs:
        max_age_seconds-->int: Expiration time in seconds
        max_age_len-->int or None:
            If None, number of dict items is unlimited
        max_age_seconds and max_len cannot be used as keys if
        constructing ExpiringDict using kwargs
        '''
        try:
            max_age_seconds = kwargs.pop('max_age_seconds')
        except KeyError:
            max_age_seconds = 60
        try:
            max_len = kwargs.pop('max_len')
        except KeyError:
            max_len = None
        assert (isinstance(max_len, int) or max_len is None)
        assert isinstance(max_age_seconds, int)
        assert max_age_seconds >= 0

        self.max_len = max_len
        self.max_age = max_age_seconds
        self.lock = RLock()
        if self.max_len is not None:
            if len(kwargs) >= self.max_len:
                args = kwargs.items()[-self.max_len:]
            else:
                args = list(args[0])[
                    -(self.max_len - len(kwargs)):] + [
                        x for x in list(kwargs.items())]
        else:
            args = list(args[0]) + [x for x in list(kwargs.items())]
        OrderedDict.__init__(self, args)

        if sys.version_info >= (3, 5):
            self._safe_keys = lambda: list(self.keys())
        else:
            self._safe_keys = self.keys

    def __contains__(self, key):
        """ Return True if the dict has a key, else return False. """
        try:
            item = OrderedDict.__getitem__(self, key)
            if time.time() - item[1] < self.max_age:
                return True
            else:
                del self[key]
        except KeyError:
            pass
        return False

    def __getitem__(self, key, with_age=False):
        """ Return the item of the dict.

        Raises a KeyError if key is not in the map.
        """
        with self.lock:
            item = OrderedDict.__getitem__(self, key)
            item_age = time.time() - item[1]
            if item_age < self.max_age:
                if with_age:
                    return item[0], item_age
                else:
                    return item[0]
            else:
                del self[key]
                raise KeyError(key)

    def __setitem__(self, key, value):
        """ Set d[key] to value. """
        with self.lock:
            if self.max_len is not None:
                while len(self) > self.max_len:
                    try:
                        self.popitem(last=False)
                    except KeyError:
                        pass
            OrderedDict.__setitem__(self, key, (value, time.time()))

    def pop(self, key, default=None):
        """ Get item from the dict and remove it.

        Return default if expired or does not exist. Never raise KeyError.
        """
        with self.lock:
            try:
                item = OrderedDict.__getitem__(self, key)
                del self[key]
                return item[0]
            except KeyError:
                return default

    def ttl(self, key):
        """ Return TTL of the `key` (in seconds).

        Returns None for non-existent or expired keys.
        """
        key_value, key_age = self.get(key, with_age=True)
        if key_age:
            key_ttl = self.max_age - key_age
            if key_ttl > 0:
                return key_ttl
        return None

    def get(self, key, default=None, with_age=False):
        " Return the value for key if key is in the dictionary, else default. "
        try:
            return self.__getitem__(key, with_age)
        except KeyError:
            if with_age:
                return default, None
            else:
                return default

    def items(self):
        """ Return a copy of the dictionary's list of (key, value) pairs. """
        r = []
        for key in self._safe_keys():
            try:
                r.append((key, self[key]))
            except KeyError:
                pass
        return r

    def values(self):
        """ Return a copy of the dictionary's list of values.
        See the note for dict.items(). """
        r = []
        for key in self._safe_keys():
            try:
                r.append(self[key])
            except KeyError:
                pass
        return r

    @classmethod
    def fromkeys(cls, iterable, value=None, max_age_seconds=60, max_len=None):
        '''
        Create a new dictionary with keys from seq and values set to value.
        Copied from collections.py OrderedDict.fromkeys
        '''
        self = cls(max_age_seconds=max_age_seconds, max_len=max_len)
        for key in iterable:
            self[key] = value
        return self

    def iteritems(self):
        """ Return an iterator over the dictionary's (key, value) pairs. """
        """ Copied from /collections.py OrderedDict.iteritems"""
        for k in self:
            yield (k, self[k])

    def itervalues(self):
        """ Return an iterator over the dictionary's values. """
        """ Copied from /collections.py OrderedDict.itervalues"""
        for k in self:
            yield self[k]

    def iterkeys(self):
        '''
        Return an iterator over the dictionary's keys
        Copied from collections.py OrderedDict.iterkeys
        '''
        for k in self:
            yield k

    # -----------------------------------------------------------------------
    # Following methods do not make sense for ExpiringDict since they
    # create a COPY of items, keys, values - and therefore:
    #     - Will end up returning the age part of the value tuple - will be
    #       unexpected by user of the class
    #     - Will not allow updating of the age field or expiring items on
    #       access
    # -----------------------------------------------------------------------

    def viewitems(self):
        '''Return a new view of ((key, value) pairs).'''
        raise NotImplementedError()

    def viewkeys(self):
        """ Return a new view of the dictionary's keys. """
        raise NotImplementedError()

    def viewvalues(self):
        """ Return a new view of the dictionary's values. """
        raise NotImplementedError()
