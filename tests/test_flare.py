"""Flare: the vocabulary, record validation with the caps, the reporter
pseudonym, and the conformance check against a fake plugin."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from ca_roads import flare

NOW = datetime(2026, 9, 17, 1, 0, tzinfo=UTC)
GOOD = {
    "id": "sabreplus:2026-09-16:8f3a", "kind": "POLICE_VISIBLE",
    "lat": 37.3382, "lon": -121.8863, "heading_deg": 270,
    "road_names": ["I-280 N"], "description": "CHP on the right shoulder",
    "report_ts": "2026-09-17T00:40:00+00:00", "n_confirmations": 3,
    "reliability": 0.8, "ttl_s": 1800, "notify": True,
    "geometry": {"type": "LineString", "coordinates": [[-121.89, 37.34], [-121.87, 37.35]]},
    "source_url": "https://example.com/a/8f3a", "extra": {"unit": "CHP 42"},
}
HANDSHAKE = {
    "protocol": "flare/1", "id": "sabreplus", "name": "SABRE Plus", "version": "2.1.0",
    "capabilities": {"alerts": True, "report": True, "confirm": True, "notify": True},
    "kinds": ["POLICE_VISIBLE", "OTHER"],
    "coverage": {"bbox": [32.5, -124.5, 42.0, -114.1]}, "refresh_s": 60,
    "attribution": {"name": "SABRE Plus", "url": "https://example.com"},
    "contact": "mailto:owner@example.com", "auth": "none",
}


def test_vocabulary_covers_waze_and_sabre():
    for k in ("POLICE_VISIBLE", "POLICE_HIDING", "CRASH_MAJOR", "HAZARD_SHOULDER_CAR",
              "WEATHER_FOG", "ROAD_CLOSED", "LANE_CLOSED", "JAM_STANDSTILL",
              "CHAINS_REQUIRED", "CAMERA_ISSUE", "MAP_ISSUE"):
        assert k in flare.KINDS
    assert len(flare.KINDS) == 31


def test_good_alert_passes_and_each_rule_is_checked():
    assert flare.validate_alert(GOOD, now=NOW) == []
    bad = dict(GOOD, kind="UFO")
    assert "kind: not in the Flare vocabulary" in flare.validate_alert(bad)
    assert any(p.startswith("ttl_s") for p in flare.validate_alert(dict(GOOD, ttl_s=0)))
    assert any(p.startswith("ttl_s") for p in flare.validate_alert(dict(GOOD, ttl_s=True)))
    bad_ts = ("yesterday", "2026-09-17T00:40:00")  # the second has no offset
    for ts in bad_ts:
        assert any(p.startswith("report_ts")
                   for p in flare.validate_alert(dict(GOOD, report_ts=ts)))
    cases = [("heading_deg", dict(heading_deg=360)), ("description", dict(description="x" * 201)),
             ("geometry", dict(geometry={"type": "Polygon", "coordinates": []})),
             ("source_url", dict(source_url="http://x")), ("extra", dict(extra={"k": "v" * 3000}))]
    for field, change in cases:
        assert any(p.startswith(field) for p in flare.validate_alert(dict(GOOD, **change))), field
    assert any(p.startswith("id") for p in flare.validate_alert(dict(GOOD, id="has space")))
    assert flare.validate_alert("nope") == ["not an object"]


def test_stale_alerts_are_rejected_by_confirm_or_report_time():
    old = dict(GOOD, report_ts=(NOW - timedelta(hours=2)).isoformat())
    assert flare.validate_alert(old, now=NOW) == ["stale: past ttl_s"]
    refreshed = dict(old, confirm_ts=(NOW - timedelta(minutes=5)).isoformat())
    assert flare.validate_alert(refreshed, now=NOW) == []


def test_accept_alerts_drops_bad_records_and_caps_the_list():
    data = {"alerts": [GOOD, dict(GOOD, id="b", kind="NOPE"), "junk"]}
    kept, problems = flare.accept_alerts(data, now=NOW)
    assert [a["id"] for a in kept] == [GOOD["id"]]
    assert len(problems) == 2 and "alerts[1] b" in problems[0] and "alerts[2]" in problems[1]
    many = {"alerts": [dict(GOOD, id=f"a{i}") for i in range(flare.MAX_ALERTS + 5)]}
    kept, problems = flare.accept_alerts(many, now=NOW)
    assert len(kept) == flare.MAX_ALERTS and "cut at 500" in problems[0]
    assert flare.accept_alerts({"nope": 1}) == ([], ["response: {alerts: [...]} required"])


def test_handshake_and_manifest_rules():
    assert flare.validate_handshake(HANDSHAKE) == []
    assert flare.validate_handshake(dict(HANDSHAKE, protocol="sabre/1"))
    assert flare.validate_handshake(dict(HANDSHAKE, capabilities={"report": True}))
    assert flare.validate_handshake(dict(HANDSHAKE, refresh_s=5))
    assert flare.validate_handshake(dict(HANDSHAKE, coverage={"bbox": [42, -124, 32, -114]}))
    assert flare.validate_handshake(dict(HANDSHAKE, kinds=["UFO"]))
    m = {"id": "sabreplus", "base": "https://plugins.example.com", "protocol": "flare/1",
         "visibility": "public", "trust": "community"}
    assert flare.validate_manifest(m) == []
    assert flare.validate_manifest(dict(m, trust="private")) == [
        "a public plugin cannot have private trust"]
    assert flare.validate_manifest(dict(m, base="http://plugins.example.com"))


def test_reporter_pseudonym_is_stable_opaque_and_per_plugin():
    a = flare.reporter_pseudonym("sabreplus", "uid-1", "secret")
    assert a == flare.reporter_pseudonym("sabreplus", "uid-1", "secret")
    assert a.startswith("r:") and len(a) == 26 and "uid" not in a
    assert a != flare.reporter_pseudonym("other", "uid-1", "secret")
    assert a != flare.reporter_pseudonym("sabreplus", "uid-2", "secret")


class FakePlugin:
    """A conformant plugin in a MockTransport; knobs break one rule at a time."""

    def __init__(self, **knobs):
        self.k = knobs
        self.alerts = {GOOD["id"]: dict(GOOD)}

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/flare/v1/handshake":
            return httpx.Response(200, json=dict(HANDSHAKE, **self.k.get("handshake", {})))
        if path == "/flare/v1/alerts":
            r = float(request.url.params.get("r", "0"))
            if r > flare.MAX_RADIUS_M and self.k.get("strict_radius"):
                return httpx.Response(400, json={"error": {"code": "bad_request", "message": "r"}})
            alerts = list(self.alerts.values())
            if self.k.get("undeclared_kind"):
                alerts.append(dict(GOOD, id="x", kind="CRASH_MAJOR"))
            return httpx.Response(200, json={"alerts": alerts, "ttl_s": 60,
                                             "as_of": NOW.isoformat()})
        if path == "/flare/v1/report" and request.method == "POST":
            body = httpx.Response(200, content=request.content).json()
            new = {"id": "new-1", "kind": body["kind"], "lat": body["lat"], "lon": body["lon"],
                   "report_ts": body["ts"], "ttl_s": 600}
            self.alerts["new-1"] = new
            return httpx.Response(201, json={"id": "new-1", "alert": new})
        if path == "/flare/v1/confirm" and request.method == "POST":
            body = httpx.Response(200, content=request.content).json()
            if body["alert_id"] not in self.alerts:
                return httpx.Response(404, json={"error": {"code": "unknown_alert",
                                                           "message": "?"}})
            return httpx.Response(200, json=self.alerts[body["alert_id"]])
        return httpx.Response(404)


@pytest.mark.asyncio
async def test_conformance_passes_a_good_plugin_and_names_what_breaks():
    plugin = FakePlugin()
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        rep = await flare.check_plugin("https://plugins.example.com", client=c, now=NOW)
    assert rep.success, rep.text()
    assert "confirm round trip" in rep.passed and "confirm unknown alert is 404" in rep.passed

    plugin = FakePlugin(undeclared_kind=True, handshake={"refresh_s": 5})
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        rep = await flare.check_plugin("https://plugins.example.com", client=c, now=NOW)
    assert not rep.success and any("refresh_s" in f for f in rep.failed)

    plugin = FakePlugin(undeclared_kind=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(plugin.handler)) as c:
        rep = await flare.check_plugin("https://plugins.example.com", client=c, now=NOW)
    assert any("kinds not declared" in f for f in rep.failed)


@pytest.mark.asyncio
async def test_conformance_refuses_plain_http_off_localhost():
    rep = await flare.check_plugin("http://plugins.example.com")
    assert rep.failed == ["base: must be https:// (localhost allowed for development)"]
