"""In-process TTL cache with stale-serve.

A transient upstream failure must not blank a source for the whole request:
when a refresh fails, the last good value is served (flagged stale) until it
exceeds ``max_serve``. Only when there is nothing servable does the caller see
a failure.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class CacheOutcome:
    """Result of a cache lookup: the value actually served plus its health."""

    value: object | None
    fetched_at: datetime | None
    served: bool  # False = nothing to serve (fetch failed, no usable cache)
    stale: bool = False  # served from cache because the live fetch failed
    error: str | None = None  # fetch error, present even when stale-serving


class _Entry:
    __slots__ = ("value", "fetched_monotonic", "fetched_at")

    def __init__(self, value: object) -> None:
        self.value = value
        self.fetched_monotonic = time.monotonic()
        self.fetched_at = datetime.now(UTC)


class TTLCache:
    """Per-key TTL cache. One fetch per key at a time; concurrent callers wait
    and then read the fresh entry."""

    def __init__(self) -> None:
        self._entries: dict[object, _Entry] = {}
        self._locks: dict[object, asyncio.Lock] = {}

    def _lock(self, key: object) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = self._locks.setdefault(key, asyncio.Lock())
        return lock

    async def get(
        self,
        key: object,
        ttl_seconds: float,
        max_serve_seconds: float,
        fetch: Callable[[], Awaitable[object]],
    ) -> CacheOutcome:
        async with self._lock(key):
            entry = self._entries.get(key)
            now = time.monotonic()
            if entry is not None and now - entry.fetched_monotonic < ttl_seconds:
                return CacheOutcome(entry.value, entry.fetched_at, served=True)
            try:
                value = await fetch()
            except Exception as exc:  # noqa: BLE001 - any fetch failure falls back to cache
                error = f"{type(exc).__name__}: {exc}"
                if entry is not None and now - entry.fetched_monotonic <= max_serve_seconds:
                    return CacheOutcome(
                        entry.value, entry.fetched_at, served=True, stale=True, error=error
                    )
                return CacheOutcome(None, None, served=False, error=error)
            entry = _Entry(value)
            self._entries[key] = entry
            return CacheOutcome(entry.value, entry.fetched_at, served=True)
