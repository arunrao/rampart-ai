"""
Bounded in-memory stores for per-process request data (traces, incidents, results).

These stores evict the oldest entries once ``max_items`` is reached so a flood of
requests cannot grow process memory without limit.
"""
from collections import OrderedDict
from threading import Lock
from typing import Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class BoundedDict(OrderedDict, Generic[K, V]):
    """OrderedDict that drops the oldest entry when it exceeds ``max_items``."""

    def __init__(self, max_items: int = 10_000):
        super().__init__()
        self.max_items = max_items
        self._lock = Lock()

    def __setitem__(self, key, value) -> None:
        with self._lock:
            super().__setitem__(key, value)
            while len(self) > self.max_items:
                self.popitem(last=False)
