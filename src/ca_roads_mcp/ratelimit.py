"""Per-IP rate limiting for the hosted HTTP transport.

The data behind this server comes from free public feeds; the point of the
limiter is to make sure a runaway agent can't hammer Caltrans or CHP through
us. Token bucket per client IP, in process (Cloud Run scale-to-zero with a
single instance makes this good enough for v1 - no shared store needed).
"""

from __future__ import annotations

import time


def trusted_client_ip(forwarded_for: str | None, peer: str | None) -> str:
    """The client IP that Google's frontend vouches for.

    X-Forwarded-For arrives as "<whatever the client sent>, <real client>"
    on Cloud Run: the platform APPENDS the IP it actually saw. Trusting the
    first entry (the old behavior) let a client spoof its identity with one
    header and bypass per-IP limits; the last entry is the only one added
    by infrastructure we trust. Off Cloud Run there is usually no header
    and the transport peer is the answer.
    """
    if forwarded_for:
        entries = [e.strip() for e in forwarded_for.split(",") if e.strip()]
        if entries:
            return entries[-1]
    return peer or "unknown"


class TokenBucket:
    """Classic token bucket: ``capacity`` burst, ``refill_per_second`` sustained."""

    __slots__ = ("capacity", "refill_per_second", "tokens", "updated")

    def __init__(self, capacity: float, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.tokens = capacity
        self.updated = time.monotonic()

    def allow(self, now: float | None = None) -> bool:
        if now is None:
            now = time.monotonic()
        elapsed = max(0.0, now - self.updated)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """Per-key (client IP) token buckets with periodic pruning."""

    def __init__(
        self,
        capacity: float = 20,
        refill_per_second: float = 0.5,  # 30/minute sustained
        max_keys: int = 10_000,
    ) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.max_keys = max_keys
        self._buckets: dict[str, TokenBucket] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self.max_keys:
                self._prune()
            bucket = self._buckets.setdefault(
                key, TokenBucket(self.capacity, self.refill_per_second)
            )
        return bucket.allow(now)

    def _prune(self) -> None:
        # Drop the stalest half; full buckets are indistinguishable from new ones.
        by_age = sorted(self._buckets.items(), key=lambda kv: kv[1].updated)
        for key, _ in by_age[: len(by_age) // 2 + 1]:
            del self._buckets[key]


class RateLimitMiddleware:
    """ASGI middleware answering 429 when a client exceeds its bucket.

    Client identity: first hop of X-Forwarded-For when present (Cloud Run
    appends the real client there), else the transport peer address.
    """

    def __init__(self, app, limiter: RateLimiter | None = None) -> None:
        self.app = app
        self.limiter = limiter or RateLimiter()

    @staticmethod
    def _client_key(scope) -> str:
        forwarded = None
        for name, value in scope.get("headers") or []:
            if name == b"x-forwarded-for":
                forwarded = value.decode("latin-1")
        client = scope.get("client")
        return trusted_client_ip(forwarded, client[0] if client else None)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not self.limiter.allow(self._client_key(scope)):
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", b"10"),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error": "rate limited, slow down"}',
                }
            )
            return
        await self.app(scope, receive, send)
