"""Flare step 2: community reports and confirmations. Reports need an
account, are capped, expire by kind, hide after three 'gone' votes,
show on the map as CommuteScout's own source, and are forwarded to
plugins that accept reports under a per-plugin pseudonym."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_flare import FakePlugin
from tests.test_flare_sources import MANIFEST
from tests.test_watch import auth, store  # noqa: F401 - fixture

from ca_roads import flare
from ca_roads_demo import flare_sources

NOW = datetime(2026, 9, 17, 1, 0, tzinfo=UTC)
STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")


def test_ttl_by_kind():
    assert flare_sources.report_ttl("POLICE_HIDING") == 1800
    assert flare_sources.report_ttl("ROAD_CLOSED") == 7200
    assert flare_sources.report_ttl("CAMERA_SPEED") == 86400
    assert flare_sources.report_ttl("OTHER") == 1800


@pytest.mark.asyncio
async def test_reports_live_expire_and_hide_after_three_gone_votes():
    clock = {"now": NOW}
    mem = flare_sources.MemorySourceStore()
    r = flare_sources.Reports(mem, now=lambda: clock["now"])
    pub = await r.add("sam", "HAZARD_ON_ROAD", 37.5, -122.2, description="ladder")
    assert flare.validate_alert(pub, now=NOW) == [] and pub["ttl_s"] == 3600
    assert "_uid" not in pub and mem.docs[pub["id"]]["_uid"] == "sam"
    m = r.markers_for_bbox((37, -123, 38, -121))
    assert len(m) == 1 and m[0]["source"] == "CommuteScout community"
    assert m[0]["id"] == "commutescout:" + pub["id"]
    # The reporter and repeat voters do not count; others do.
    assert (await r.confirm(pub["id"], "up", "sam"))["n_confirmations"] == 0
    assert (await r.confirm(pub["id"], "up", "pat"))["n_confirmations"] == 1
    assert (await r.confirm(pub["id"], "up", "pat"))["n_confirmations"] == 1
    for who in ("a", "b"):
        assert await r.confirm(pub["id"], "gone", who) is not None
    assert await r.confirm(pub["id"], "gone", "c") is None
    assert pub["id"] not in r.records and pub["id"] not in mem.docs
    # Expiry by ttl.
    pub2 = await r.add("sam", "JAM_HEAVY", 37.5, -122.2)
    clock["now"] = NOW + timedelta(seconds=1300)
    assert r.markers_for_bbox((37, -123, 38, -121)) == [] and pub2["id"] not in r.records
    # A restart reloads what is still live.
    pub3 = await r.add("sam", "POLICE_VISIBLE", 37.5, -122.2)
    r2 = flare_sources.Reports(mem, now=lambda: clock["now"])
    assert await r2.load() == 1 and pub3["id"] in r2.records


def test_caps_one_a_minute_and_twenty_a_day():
    r = flare_sources.Reports(flare_sources.MemorySourceStore())
    assert r.allow("sam") is None
    assert "minute" in r.allow("sam")
    r._last.clear()
    for _ in range(19):
        assert r.allow("sam") is None
        r._last.clear()
    assert "day" in r.allow("sam")


@pytest.fixture
def api(store, monkeypatch):  # noqa: F811 - fixture
    plugin = FakePlugin()
    mem = flare_sources.MemorySourceStore()
    poller = flare_sources.Poller(mem, now=lambda: NOW)
    poller.sources = {"sabreplus": dict(MANIFEST, enabled=True)}
    monkeypatch.setattr(flare_sources, "poller", poller)
    monkeypatch.setattr(flare_sources, "reports",
                        flare_sources.Reports(flare_sources.MemorySourceStore(),
                                              now=lambda: NOW))

    class _Road:
        client = httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler))

    from ca_roads_mcp import server as tools
    monkeypatch.setattr(tools, "get_road", lambda: _Road())
    app = Starlette(routes=[
        Route("/api/flare/report", flare_sources.api_flare_report, methods=["POST"]),
        Route("/api/flare/confirm", flare_sources.api_flare_confirm, methods=["POST"]),
    ])
    return TestClient(app), plugin


def test_report_needs_sign_in_validates_and_forwards(api):
    c, plugin = api
    anon = c.post("/api/flare/report", json={"kind": "OTHER", "lat": 1, "lon": 1})
    assert anon.status_code == 401
    assert c.post("/api/flare/report", json={"kind": "UFO", "lat": 1, "lon": 1},
                  headers=auth()).status_code == 400
    assert c.post("/api/flare/report", json={"kind": "OTHER", "lat": 99, "lon": 1},
                  headers=auth()).status_code == 400
    r = c.post("/api/flare/report", json={"kind": "OTHER", "lat": 37.5, "lon": -122.2,
                                          "description": "  cone in lane 2 <b>x</b> "},
               headers=auth())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"].startswith("commutescout:") and body["alert"]["description"]
    assert body["forwarded"] == ["sabreplus"]  # the fake plugin accepts OTHER
    sent = plugin.alerts["new-1"]
    assert sent["kind"] == "OTHER"
    # Second report within a minute is refused.
    r2 = c.post("/api/flare/report", json={"kind": "OTHER", "lat": 37.5, "lon": -122.2},
                headers=auth())
    assert r2.status_code == 429 and r2.headers["retry-after"] == "60"


def test_confirm_routes_to_our_source_or_the_plugin(api):
    c, plugin = api
    r = c.post("/api/flare/report", json={"kind": "CRASH_MAJOR", "lat": 37.5, "lon": -122.2},
               headers=auth())
    alert_id = r.json()["id"]
    anon = c.post("/api/flare/confirm", json={"alert_id": alert_id, "vote": "up"})
    assert anon.status_code == 401
    ok = c.post("/api/flare/confirm", json={"alert_id": alert_id, "vote": "up"},
                headers=auth("tok-admin"))
    assert ok.status_code == 200 and ok.json()["alert"]["n_confirmations"] == 1
    assert c.post("/api/flare/confirm", json={"alert_id": "commutescout:nope", "vote": "up"},
                  headers=auth()).status_code == 404
    # A plugin alert is forwarded with a pseudonym, never the account.
    r = c.post("/api/flare/confirm", json={"alert_id": "sabreplus:" + list(plugin.alerts)[0],
                                           "vote": "gone"}, headers=auth())
    assert r.status_code == 200 and r.json()["forwarded"] is True
    assert c.post("/api/flare/confirm", json={"alert_id": "sabreplus:missing", "vote": "up"},
                  headers=auth()).status_code == 404
    assert c.post("/api/flare/confirm", json={"alert_id": "ghost:x", "vote": "up"},
                  headers=auth()).status_code == 404


def test_map_has_one_report_control_and_votes_on_plugin_popups():
    assert HTML.count('id="reportbtn"') == 1
    assert "report: 'Click the map where it is'," in APP
    assert "if (mode === 'report') { openReportForm(await snapForReport(e.latlng), e.latlng); return; }" in APP
    block = APP[APP.index("const REPORT_KINDS"):APP.index("async function authToken")]
    kinds = re.findall(r"\['([A-Z_]+)', '", block)
    assert set(kinds) <= flare.KINDS and "POLICE_VISIBLE" in kinds and "ROAD_CLOSED" in kinds
    assert "flarePost('/api/flare/confirm', { alert_id: m.id, vote })" in APP
    assert "window.csAuth = { token: async () => (user ? user.getIdToken() : null) };" in \
        (STATIC / "watch-app.js").read_text(encoding="utf-8")


def test_only_https_links_reach_a_popup():
    src = dict(MANIFEST, attribution={"name": "x", "url": "javascript:alert(1)"})
    a = {"id": "a", "kind": "OTHER", "lat": 1.0, "lon": 1.0, "report_ts": NOW.isoformat(),
         "ttl_s": 60, "source_url": "javascript:alert(2)"}
    assert "source_url" not in flare_sources.alert_marker(src, a)
    a["source_url"] = "https://example.com/x"
    assert flare_sources.alert_marker(src, a)["source_url"] == "https://example.com/x"
    assert flare.validate_manifest(src) == ["attribution.url: https URL"]
    assert r"/^https:\/\//.test(m.source_url || '')" in APP
