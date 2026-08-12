"""Per-IP rate limiting for the hosted HTTP transport.

The data behind this server comes from free public feeds; the point of the
limiter is to make sure a runaway agent can't hammer Caltrans or CHP through
us. Token bucket per client IP, in process (Cloud Run scale-to-zero with a
single instance makes this good enough for v1 - no shared store needed).
"""

from __future__ import annotations

import ipaddress
import time

# Cloudflare's published edge ranges (cloudflare.com/ips, vendored
# 2026-07-27). They change rarely; refresh from the same URLs if
# Cloudflare announces new blocks.
_CLOUDFLARE_RANGES = tuple(ipaddress.ip_network(n) for n in (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22",
    "103.31.4.0/22", "141.101.64.0/18", "108.162.192.0/18",
    "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22",
    "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32",
    "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29",
    "2c0f:f248::/32",
))


def is_cloudflare_ip(ip: str) -> bool:
    """Whether ``ip`` belongs to Cloudflare's published edge ranges.

    Shared by the rate limiter (to decide when CF-Connecting-IP is
    trustworthy) and the demo's origin gate (to refuse traffic that
    reached the origin without going through Cloudflare at all).
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _CLOUDFLARE_RANGES)


def trusted_client_ip(
    forwarded_for: str | None,
    peer: str | None,
    cf_connecting_ip: str | None = None,
) -> str:
    """The client IP the fronting infrastructure vouches for.

    X-Forwarded-For arrives as "<whatever the client sent>, <real client>"
    on Cloud Run: the platform APPENDS the IP it actually saw. Trusting the
    first entry (the old behavior) let a client spoof its identity with one
    header and bypass per-IP limits; the last entry is the only one added
    by infrastructure we trust. Off Cloud Run there is usually no header
    and the transport peer is the answer.

    Behind Cloudflare the platform-vouched address is a Cloudflare edge
    and the real client rides in CF-Connecting-IP. That header is honored
    ONLY when the vouched address really is Cloudflare's: anyone hitting
    the origin directly can send the header, and trusting it blindly
    would reopen the spoofing hole the last-entry rule closed.
    """
    vouched = None
    if forwarded_for:
        entries = [e.strip() for e in forwarded_for.split(",") if e.strip()]
        if entries:
            vouched = entries[-1]
    if vouched is None:
        vouched = peer or "unknown"
    if cf_connecting_ip and is_cloudflare_ip(vouched):
        return cf_connecting_ip.strip()
    return vouched


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

    Client identity: the platform-appended (last) X-Forwarded-For entry when
    present, else the transport peer address. Paths under exempt_prefixes
    skip the bucket entirely: static assets are cheap to serve, and counting
    them starves the requests that matter (a page load fetching local fonts
    and map libraries once drained the whole bucket before the question).

    exempt_exact is a separate, exact-match set for paths that must NOT be
    exempted as a prefix - "/" is the motivating case: exempt_prefixes uses
    str.startswith, so a "/" entry there would match every path in the app
    and silently disable the limiter entirely. exempt_exact is checked
    before the prefix loop and only ever matches the literal path.
    """

    def __init__(
        self,
        app,
        limiter: RateLimiter | None = None,
        exempt_prefixes: tuple[str, ...] = (),
        exempt_exact: frozenset[str] = frozenset(),
    ) -> None:
        self.app = app
        self.limiter = limiter or RateLimiter()
        self.exempt_prefixes = exempt_prefixes
        self.exempt_exact = exempt_exact

    @staticmethod
    def _client_key(scope) -> str:
        forwarded = None
        cf_ip = None
        for name, value in scope.get("headers") or []:
            if name == b"x-forwarded-for":
                forwarded = value.decode("latin-1")
            elif name == b"cf-connecting-ip":
                cf_ip = value.decode("latin-1")
        client = scope.get("client")
        return trusted_client_ip(forwarded, client[0] if client else None,
                                 cf_ip)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in self.exempt_exact:
            await self.app(scope, receive, send)
            return
        if any(path.startswith(p) for p in self.exempt_prefixes):
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
