"""In-process TTL cache with stale-serve and background revalidation.

Reads never wait on a slow upstream. A key within its TTL is served straight
from memory. A key past its TTL but still within ``max_serve`` is served
immediately from the last good value while a single background task refreshes
it (stale-while-revalidate), so only the first fetch of a cold key blocks a
caller. When a refresh fails, the last good value keeps being served — flagged
stale with the error — until it exceeds ``max_serve``; only then does a caller
see a failure.
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
    stale: bool = False  # served from cache because the live refresh failed
    error: str | None = None  # fetch error, present even when stale-serving


class _Entry:
    __slots__ = ("value", "fetched_monotonic", "fetched_at")

    def __init__(self, value: object) -> None:
        self.value = value
        self.fetched_monotonic = time.monotonic()
        self.fetched_at = datetime.now(UTC)


class TTLCache:
    """Per-key TTL cache with stale-while-revalidate.

    A fresh or still-servable key returns without ever awaiting ``fetch``; the
    refresh runs in the background, one at a time per key. Only a cold key (or
    one past ``max_serve``) fetches on the caller's path, where concurrent
    callers for the same key share the single in-flight fetch.
    """

    def __init__(self) -> None:
        self._entries: dict[object, _Entry] = {}
        self._locks: dict[object, asyncio.Lock] = {}
        self._refreshing: set[object] = set()
        self._tasks: set[asyncio.Task] = set()
        self._errors: dict[object, str] = {}

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
        entry = self._entries.get(key)
        now = time.monotonic()
        if entry is not None and now - entry.fetched_monotonic < ttl_seconds:
            return CacheOutcome(entry.value, entry.fetched_at, served=True)
        if entry is not None and now - entry.fetched_monotonic <= max_serve_seconds:
            # Serve the last good value now and refresh off the caller's path,
            # so a slow feed never adds request latency. A serve is only flagged
            # stale once a background refresh has actually failed.
            self._schedule_refresh(key, fetch)
            error = self._errors.get(key)
            return CacheOutcome(
                entry.value, entry.fetched_at, served=True,
                stale=error is not None, error=error,
            )
        return await self._fetch_blocking(key, ttl_seconds, max_serve_seconds, fetch)

    async def _fetch_blocking(
        self,
        key: object,
        ttl_seconds: float,
        max_serve_seconds: float,
        fetch: Callable[[], Awaitable[object]],
    ) -> CacheOutcome:
        """Cold path: nothing servable, so fetch on the caller's path.
        Concurrent callers for the same key share one fetch."""
        async with self._lock(key):
            entry = self._entries.get(key)
            now = time.monotonic()
            if entry is not None and now - entry.fetched_monotonic < ttl_seconds:
                return CacheOutcome(entry.value, entry.fetched_at, served=True)
            try:
                value = await fetch()
            except Exception as exc:  # noqa: BLE001 - any failure falls back to cache
                error = f"{type(exc).__name__}: {exc}"
                self._errors[key] = error
                if entry is not None and now - entry.fetched_monotonic <= max_serve_seconds:
                    return CacheOutcome(
                        entry.value, entry.fetched_at, served=True,
                        stale=True, error=error,
                    )
                return CacheOutcome(None, None, served=False, error=error)
            self._errors.pop(key, None)
            entry = _Entry(value)
            self._entries[key] = entry
            return CacheOutcome(entry.value, entry.fetched_at, served=True)

    def _schedule_refresh(
        self, key: object, fetch: Callable[[], Awaitable[object]],
    ) -> None:
        """Start one background refresh per key (a no-op if one is running)."""
        if key in self._refreshing:
            return
        self._refreshing.add(key)
        task = asyncio.create_task(self._refresh(key, fetch))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _refresh(
        self, key: object, fetch: Callable[[], Awaitable[object]],
    ) -> None:
        try:
            async with self._lock(key):
                try:
                    value = await fetch()
                except Exception as exc:  # noqa: BLE001 - keep serving the last good value
                    self._errors[key] = f"{type(exc).__name__}: {exc}"
                    return
                self._errors.pop(key, None)
                self._entries[key] = _Entry(value)
        finally:
            self._refreshing.discard(key)

    async def _drain(self) -> None:
        """Await any in-flight background refreshes (test / shutdown helper)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
