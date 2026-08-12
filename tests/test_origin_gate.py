"""The demo origin only answers traffic that came through Cloudflare.

commutescout.com is proxied by Cloudflare, but the run.app origin URL
answers anyone who finds it, skipping the WAF and bot filtering entirely.
The gate closes that: when REQUIRE_CLOUDFLARE is set, a request whose
platform-vouched peer (the last X-Forwarded-For entry, the only one Cloud
Run itself appends) is not a Cloudflare edge address is refused - or, for
browser GETs aimed at the legacy run.app host, redirected to the real
site. Cloud Scheduler still calls the run.app URL directly with OIDC, so
its endpoint must stay reachable, as must /health for deploy checks.
"""

import pytest
from starlette.testclient import TestClient

from ca_roads_demo.app import app

CF_EDGE = "103.21.244.7"  # inside Cloudflare's published 103.21.244.0/22
NOT_CF = "203.0.113.9"    # TEST-NET-3, never a Cloudflare edge
RUN_HOST = "ca-roads-demo-15002631928.us-west1.run.app"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def gated(monkeypatch, client):
    monkeypatch.setenv("REQUIRE_CLOUDFLARE", "1")
    return client


def test_gate_off_by_default(client):
    """Without the env flag nothing changes: local dev and tests hit the
    app directly and must keep working."""
    r = client.get("/map", headers={"x-forwarded-for": NOT_CF})
    assert r.status_code == 200


def test_direct_run_app_get_redirects_to_site(gated):
    """A human who found the legacy run.app URL lands on the real site,
    same path and query intact."""
    r = gated.get(
        "/map?focus=fires",
        headers={"host": RUN_HOST, "x-forwarded-for": NOT_CF},
        follow_redirects=False,
    )
    assert r.status_code == 301
    assert r.headers["location"] == "https://commutescout.com/map?focus=fires"


def test_direct_api_post_is_refused(gated):
    """Non-GET traffic gets a hard refusal, not a redirect a script would
    silently follow."""
    r = gated.post(
        "/api/trip",
        headers={"host": RUN_HOST, "x-forwarded-for": NOT_CF},
    )
    assert r.status_code == 403
    assert "commutescout.com" in r.text


def test_forged_site_host_is_refused_not_redirected(gated):
    """Direct origin traffic claiming the public hostname must not earn a
    redirect: only the legacy run.app host gets the courtesy hop, so a
    stale Cloudflare IP list can never produce a redirect loop through
    the proxy."""
    r = gated.get(
        "/map",
        headers={"host": "commutescout.com", "x-forwarded-for": NOT_CF},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_cloudflare_traffic_passes(gated):
    """The platform-appended (last) X-Forwarded-For entry being a
    Cloudflare edge is the pass condition."""
    r = gated.get(
        "/map",
        headers={
            "host": "commutescout.com",
            "x-forwarded-for": f"{NOT_CF}, {CF_EDGE}",
        },
    )
    assert r.status_code == 200


def test_spoofed_cf_connecting_ip_does_not_open_gate(gated):
    """CF-Connecting-IP is client-settable on direct hits; the gate must
    key on the vouched peer alone."""
    r = gated.get(
        "/map",
        headers={
            "host": "commutescout.com",
            "x-forwarded-for": NOT_CF,
            "cf-connecting-ip": CF_EDGE,
        },
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_scheduler_endpoint_stays_reachable(gated):
    """Cloud Scheduler hits the run.app URL directly (never through
    Cloudflare); the gate must hand its endpoint to the OIDC check, whose
    own refusal reads "not authorized" rather than the gate's message."""
    r = gated.post(
        "/api/check-watches",
        headers={"host": RUN_HOST, "x-forwarded-for": NOT_CF},
    )
    assert r.status_code == 403
    assert r.json() == {"error": "not authorized"}


def test_health_stays_reachable(gated):
    """Deploy verification curls run.app /health before traffic routing;
    it serves nothing sensitive."""
    r = gated.get(
        "/health",
        headers={"host": RUN_HOST, "x-forwarded-for": NOT_CF},
    )
    assert r.status_code == 200
