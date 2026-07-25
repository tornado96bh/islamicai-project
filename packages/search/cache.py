from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic
from typing import Any

@dataclass
class CacheItem:
    value: Any
    expires_at: float

class SearchCache:
    def __init__(self, maxsize: int = 256, ttl_seconds: int = 300):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[str, CacheItem] = OrderedDict()

    def get(self, key: str):
        item = self._store.get(key)
        if item is None:
            return None
        if item.expires_at < monotonic():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return item.value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = CacheItem(value=value, expires_at=monotonic() + self.ttl_seconds)
        self._store.move_to_end(key)
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
