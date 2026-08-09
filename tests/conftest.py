import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_bytes():
    def _load(name: str) -> bytes:
        return (FIXTURES / name).read_bytes()

    return _load


@pytest.fixture(autouse=True)
def _fresh_rate_limiter(monkeypatch):
    """Give the process-shared rate buckets a fresh, generous limiter for
    every test.

    The main RateLimitMiddleware and SoftLimit buckets are one
    process-lifetime instance keyed on TestClient's fixed peer, so a test
    module that makes several requests drains them and 429s a LATER
    module - a cross-file flake that only shows in the full suite and had
    to be patched per file (test_signin_link, test_contact,
    test_admin_waitlist). This does it once for all tests. Only runs when
    the demo app is already imported, so pure unit tests don't pay for
    the import. In-process caps (the trip daily quota, the redeem
    throttle) are separate limiters and are deliberately untouched, so
    tests asserting those 429s still work.
    """
    demo_app = sys.modules.get("ca_roads_demo.app")
    if demo_app is None:
        return
    from ca_roads_mcp.ratelimit import RateLimiter

    layer = demo_app.app
    for _ in range(12):
        if layer is None:
            break
        if hasattr(layer, "limiter"):
            monkeypatch.setattr(
                layer, "limiter",
                RateLimiter(capacity=1000, refill_per_second=1000))
        layer = getattr(layer, "app", None)
