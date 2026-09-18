"""Per-IP rate limiting for the hosted HTTP transport.

The data behind this server comes from free public feeds; the point of the
limiter is to make sure a runaway agent can't hammer Caltrans or CHP through
us. Token bucket per client IP, in process (Cloud Run scale-to-zero with a
single instance makes this good enough for v1 - no shared store needed).
"""

from __future__ import annotations

import ipaddress
import json
import logging
import time

from ca_roads import apikeys
from ca_roads.budget import DailyCounter

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


def limiter_key(ip: str) -> str:
    """The identity a limit is keyed on. IPv4 is the address itself.
    IPv6 is folded to its /64: a residential allocation is one /64 with
    2**64 addresses, so a client rotating the low bits per request
    would otherwise get unlimited fresh buckets and daily counters.
    Non-addresses ("unknown") pass through."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if addr.version == 6:
        mapped = addr.ipv4_mapped
        if mapped is not None:
            return str(mapped)
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return ip


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
        key = limiter_key(key)  # idempotent: middleware may pre-fold
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
        daily_limit: int | None = None,
    ) -> None:
        self.app = app
        self.limiter = limiter or RateLimiter()
        self.exempt_prefixes = exempt_prefixes
        self.exempt_exact = exempt_exact
        # The bucket bounds the rate; this bounds the day. A client at
        # the sustained rate for 24 hours is 43k requests, which on the
        # MCP service is real CPU money (one client did 60k in a day).
        # The key is the client address, and hosted MCP clients can
        # share an egress address, so the limit must stay well above
        # what a whole office or connector fleet does in a day.
        self.daily_limit = daily_limit
        self.daily = DailyCounter()

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
        # A keyed request was already limited by its key (ApiKeyMiddleware).
        if (scope.get("state") or {}).get("api_key"):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in self.exempt_exact:
            await self.app(scope, receive, send)
            return
        if any(path.startswith(p) for p in self.exempt_prefixes):
            await self.app(scope, receive, send)
            return
        key = limiter_key(self._client_key(scope))
        # The keyless path answers with the same envelope as a keyed one:
        # {"error": {"code", "message", "hint"}}, with CORS, so a client
        # written against the documented shape survives its first 429.
        if not self.limiter.allow(key):
            status, headers, body = _json_error(
                429, "rate_limited", "Too many requests at once from your address.",
                "Slow down, or use an API key for a higher rate.",
                ((b"retry-after", b"2"),))
            await send({"type": "http.response.start", "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return
        # Counted after the bucket: a client the bucket already turned
        # away has not spent anything, so it must not burn its day.
        if self.daily_limit and not self.daily.allow(key, self.daily_limit):
            status, headers, body = _json_error(
                429, "daily_limit",
                f"Your address has used its {self.daily_limit} requests for today (UTC).",
                "An API key has its own daily allowance.",
                ((b"retry-after", b"3600"),))
            await send({"type": "http.response.start", "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def _json_error(status: int, code: str, message: str, hint: str | None = None,
                headers: tuple = ()) -> tuple[int, list, bytes]:
    body = {"code": code, "message": message}
    if hint:
        body["hint"] = hint
    raw = json.dumps({"error": body}).encode("utf-8")
    return status, [(b"content-type", b"application/json"),
                    (b"access-control-allow-origin", b"*"), *headers], raw


class ApiKeyMiddleware:
    """Resolves an API key and applies its tier's limits.

    Keyless requests pass straight through to the per-address limiter
    behind this one. A keyed request is limited per key instead (its
    tier's bucket and daily count), marked in ``scope["state"]`` so the
    inner limiter steps aside, answered with ``RateLimit-*`` headers,
    and logged as one JSON line for metering. A bad key is a 401 with
    the API's error envelope, never a silent fall back to keyless.
    """

    def __init__(self, app, resolver: apikeys.KeyResolver | None = None) -> None:
        self.app = app
        self.resolver = resolver or apikeys.KeyResolver()
        self.daily = DailyCounter()
        self.buckets: dict[str, TokenBucket] = {}
        self.log = logging.getLogger("ca_roads.apikeys")

    async def _send_error(self, send, status, code, message, hint=None, headers=()):
        status, hdrs, raw = _json_error(status, code, message, hint, headers)
        await send({"type": "http.response.start", "status": status, "headers": hdrs})
        await send({"type": "http.response.body", "body": raw})

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers") or []}
        presented = apikeys.from_headers(headers.get)
        if not presented:
            await self.app(scope, receive, send)
            return
        try:
            info = await self.resolver.resolve(presented)
        except Exception:  # noqa: BLE001 - the key store is down
            self.log.exception("api key lookup failed")
            await self._send_error(send, 503, "keys_unavailable",
                                   "Key checks are unavailable right now.",
                                   "Retry in a minute, or call without a key.")
            return
        if not info:
            await self._send_error(send, 401, "invalid_key",
                                   "That API key is unknown or revoked.",
                                   "Create a key under Settings on commutescout.com/map.")
            return
        limits = apikeys.tier_limits(info["tier"])
        bucket = self.buckets.get(info["id"])
        if bucket is None:
            if len(self.buckets) > 10_000:
                self.buckets.clear()
            bucket = self.buckets[info["id"]] = TokenBucket(
                limits["burst"], limits["per_second"])
        if not bucket.allow():
            await self._send_error(send, 429, "rate_limited",
                                   "Too many requests at once for this key.",
                                   "Slow to the sustained rate for your tier.",
                                   ((b"retry-after", b"2"),))
            return
        if not self.daily.allow(info["id"], limits["daily"]):
            await self._send_error(
                send, 429, "daily_limit",
                f"This key has used its {limits['daily']} requests for today (UTC).",
                "Pro keys get 10,000 a day; ask for more from the contact page.",
                ((b"retry-after", b"3600"),
                 (b"ratelimit-limit", str(limits["daily"]).encode()),
                 (b"ratelimit-remaining", b"0")))
            return
        remaining = max(0, limits["daily"] - self.daily.used(info["id"]))
        scope.setdefault("state", {})["api_key"] = info
        status_seen = {"status": 0}

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                status_seen["status"] = message["status"]
                message["headers"] = list(message.get("headers") or []) + [
                    (b"ratelimit-limit", str(limits["daily"]).encode()),
                    (b"ratelimit-remaining", str(remaining).encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            self.log.info(json.dumps({
                "log_type": "api_use", "key": info["id"], "tier": info["tier"],
                "path": scope.get("path", ""), "status": status_seen["status"]}))
