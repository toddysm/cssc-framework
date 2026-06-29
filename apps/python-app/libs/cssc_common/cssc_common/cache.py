"""A tiny thread-safe time-to-live cache.

The capability services cache GitHub responses so that many ``dashboard-web``
replicas do not exhaust the GitHub API rate limit. The cache is deliberately
minimal — a process-local dictionary keyed by a hashable cache key with an
absolute expiry timestamp.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Callable, Hashable, TypeVar

T = TypeVar("T")


class TTLCache:
    """A minimal TTL cache.

    A ``ttl_seconds`` of ``0`` disables caching entirely (every lookup calls the
    producer), which is convenient in tests.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = max(0, int(ttl_seconds))
        self._store: dict[Hashable, tuple[float, Any]] = {}
        self._lock = Lock()

    def get_or_set(self, key: Hashable, producer: Callable[[], T]) -> T:
        """Return the cached value for ``key`` or compute and store it."""

        if self._ttl == 0:
            return producer()

        now = time.monotonic()
        with self._lock:
            hit = self._store.get(key)
            if hit is not None and hit[0] > now:
                return hit[1]

        value = producer()
        with self._lock:
            self._store[key] = (now + self._ttl, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
