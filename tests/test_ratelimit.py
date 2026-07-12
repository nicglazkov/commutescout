from ca_roads_mcp.ratelimit import RateLimiter, TokenBucket


def test_bucket_burst_then_deny():
    bucket = TokenBucket(capacity=3, refill_per_second=1)
    now = 100.0
    assert bucket.allow(now)
    assert bucket.allow(now)
    assert bucket.allow(now)
    assert not bucket.allow(now)


def test_bucket_refills_over_time():
    bucket = TokenBucket(capacity=2, refill_per_second=1)
    now = 100.0
    assert bucket.allow(now)
    assert bucket.allow(now)
    assert not bucket.allow(now)
    assert bucket.allow(now + 1.5)  # one token refilled


def test_bucket_never_exceeds_capacity():
    bucket = TokenBucket(capacity=2, refill_per_second=100)
    now = 100.0
    bucket.allow(now)
    # Long idle: capacity caps the refill.
    assert bucket.allow(now + 1000)
    assert bucket.allow(now + 1000)
    assert not bucket.allow(now + 1000)


def test_limiter_keys_are_independent():
    limiter = RateLimiter(capacity=1, refill_per_second=0)
    now = 100.0
    assert limiter.allow("a", now)
    assert not limiter.allow("a", now)
    assert limiter.allow("b", now)


def test_limiter_prunes_at_max_keys():
    limiter = RateLimiter(capacity=1, refill_per_second=0, max_keys=4)
    now = 100.0
    for i in range(4):
        limiter.allow(f"ip{i}", now + i)
    limiter.allow("overflow", now + 10)
    assert len(limiter._buckets) <= 4


def test_trusted_client_ip_ignores_spoofed_first_hop():
    from ca_roads_mcp.ratelimit import trusted_client_ip

    # A client sets a fake XFF; Cloud Run appends the address it saw.
    assert trusted_client_ip("6.6.6.6, 203.0.113.9", "10.0.0.1") == "203.0.113.9"
    assert trusted_client_ip("a, b, 198.51.100.2", "10.0.0.1") == "198.51.100.2"
    # No spoofing: single platform-appended entry.
    assert trusted_client_ip("203.0.113.9", "10.0.0.1") == "203.0.113.9"
    # No header at all (local dev): transport peer.
    assert trusted_client_ip(None, "127.0.0.1") == "127.0.0.1"
    assert trusted_client_ip("  ,  ", None) == "unknown"


async def test_static_paths_bypass_the_bucket():
    from ca_roads_mcp.ratelimit import RateLimiter, RateLimitMiddleware

    served = []

    async def inner(scope, receive, send):
        served.append(scope["path"])

    mw = RateLimitMiddleware(
        inner, RateLimiter(capacity=1, refill_per_second=0),
        exempt_prefixes=("/static/",),
    )
    scope = {"type": "http", "headers": [], "client": ("1.2.3.4", 0)}
    # Static requests never consume tokens, no matter how many.
    for _ in range(10):
        await mw({**scope, "path": "/static/vendor/leaflet.js"}, None, None)
    # The single bucket token is still available for the API call.
    await mw({**scope, "path": "/api/ask"}, None, _sink)
    assert served.count("/static/vendor/leaflet.js") == 10
    assert "/api/ask" in served


async def _sink(message):
    pass


def test_security_headers_and_softlimit():
    from starlette.testclient import TestClient

    from ca_roads_demo.app import app

    client = TestClient(app)
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "geolocation=(self)" in r.headers["permissions-policy"]
