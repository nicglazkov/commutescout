"""Flare, the open protocol for third-party road alert sources.

The specification is docs/flare.md. This module is the reference
implementation of everything a caller needs: the vocabulary, record
validation with the caps, the reporter pseudonym, and a conformance
check that a plugin author runs against a live plugin::

    python -m ca_roads.flare check https://plugins.example.com

The backend uses the same validators on every mediated fetch, so a
plugin that passes the check here is accepted there.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

PROTOCOL = "flare/1"
KINDS = frozenset({
    "POLICE_VISIBLE", "POLICE_HIDING", "POLICE_OTHER",
    "CRASH_MINOR", "CRASH_MAJOR",
    "HAZARD_ON_ROAD", "HAZARD_OBJECT", "HAZARD_POTHOLE", "HAZARD_ANIMAL",
    "HAZARD_CONSTRUCTION",
    "HAZARD_SHOULDER", "HAZARD_SHOULDER_CAR", "HAZARD_SHOULDER_ANIMAL",
    "WEATHER_FLOOD", "WEATHER_FOG", "WEATHER_ICE", "WEATHER_HAIL", "WEATHER_SNOW",
    "ROAD_CLOSED", "LANE_CLOSED", "RAMP_CLOSED",
    "JAM_MODERATE", "JAM_HEAVY", "JAM_STANDSTILL",
    "CHAINS_REQUIRED", "CHAINS_NOT_REQUIRED",
    "CAMERA_SPEED", "CAMERA_RED_LIGHT", "CAMERA_ISSUE",
    "MAP_ISSUE", "OTHER",
})
CAPABILITIES = ("alerts", "report", "confirm", "notify")
VOTES = ("up", "gone")
TRUST = ("official", "verified", "community", "private")
TIERS = ("approved", "unreviewed", "private")


def tier_of(manifest: dict) -> str:
    """The three levels a plugin is shown as. Approved: reviewed by
    CommuteScout (official or verified trust); its notify alerts may
    speak. Unreviewed: public and listed after the conformance check,
    but nobody has vouched for it; drawn on the map, labelled as such,
    voice only if the user turns it on. Private: added by URL on one
    device; nothing about it leaves the user's own path."""
    if manifest.get("visibility") == "private" or manifest.get("trust") == "private":
        return "private"
    if manifest.get("trust") in ("official", "verified"):
        return "approved"
    return "unreviewed"
VISIBILITY = ("public", "unlisted", "private")

MAX_ALERTS = 500
MAX_PER_CELL = 50
MAX_BYTES = 1_000_000
MAX_TTL_S = 86_400
MAX_RADIUS_M = 100_000
MAX_DESCRIPTION = 200
MAX_GEOMETRY_POINTS = 500
MAX_EXTRA_BYTES = 2_048
MIN_REFRESH_S = 15

_ID_RE = re.compile(r"^[A-Za-z0-9_.:@-]{1,128}$")


def parse_ts(value: Any) -> datetime | None:
    """ISO 8601 with an offset; a bare 'Z' is accepted. None otherwise."""
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else None


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_alert(a: Any, *, now: datetime | None = None) -> list[str]:
    """Problems with one alert record; an empty list means it is accepted."""
    if not isinstance(a, dict):
        return ["not an object"]
    p: list[str] = []
    if not isinstance(a.get("id"), str) or not _ID_RE.match(a["id"]):
        p.append("id: 1 to 128 characters of letters, digits, _ . : @ -")
    if a.get("kind") not in KINDS:
        p.append("kind: not in the Flare vocabulary")
    if not (_num(a.get("lat")) and -90 <= a["lat"] <= 90):
        p.append("lat: number in -90..90")
    if not (_num(a.get("lon")) and -180 <= a["lon"] <= 180):
        p.append("lon: number in -180..180")
    if "heading_deg" in a and not (_num(a["heading_deg"]) and 0 <= a["heading_deg"] < 360):
        p.append("heading_deg: number in 0..359")
    if "road_names" in a and not (isinstance(a["road_names"], list)
                                  and all(isinstance(x, str) for x in a["road_names"])):
        p.append("road_names: list of strings")
    if "description" in a and not (isinstance(a["description"], str)
                                   and len(a["description"]) <= MAX_DESCRIPTION):
        p.append(f"description: string of at most {MAX_DESCRIPTION} characters")
    reported = parse_ts(a.get("report_ts"))
    if reported is None:
        p.append("report_ts: ISO 8601 with an offset")
    confirmed = None
    if "confirm_ts" in a:
        confirmed = parse_ts(a["confirm_ts"])
        if confirmed is None:
            p.append("confirm_ts: ISO 8601 with an offset")
    if "n_confirmations" in a and not (isinstance(a["n_confirmations"], int)
                                       and a["n_confirmations"] >= 0):
        p.append("n_confirmations: integer >= 0")
    if "reliability" in a and not (_num(a["reliability"]) and 0 <= a["reliability"] <= 1):
        p.append("reliability: number in 0..1")
    ttl = a.get("ttl_s")
    if not (isinstance(ttl, int) and not isinstance(ttl, bool) and 1 <= ttl <= MAX_TTL_S):
        p.append(f"ttl_s: integer in 1..{MAX_TTL_S}")
    if "notify" in a and not isinstance(a["notify"], bool):
        p.append("notify: boolean")
    geom = a.get("geometry")
    if geom is not None:
        ok = (isinstance(geom, dict) and geom.get("type") in ("Point", "LineString")
              and isinstance(geom.get("coordinates"), list))
        if ok and geom["type"] == "LineString":
            ok = (2 <= len(geom["coordinates"]) <= MAX_GEOMETRY_POINTS and all(
                isinstance(c, list) and len(c) >= 2 and _num(c[0]) and _num(c[1])
                for c in geom["coordinates"]))
        if ok and geom["type"] == "Point":
            c = geom["coordinates"]
            ok = len(c) >= 2 and _num(c[0]) and _num(c[1])
        if not ok:
            p.append(f"geometry: GeoJSON Point or LineString of at most "
                     f"{MAX_GEOMETRY_POINTS} points")
    if "source_url" in a and not (isinstance(a["source_url"], str)
                                  and a["source_url"].startswith("https://")):
        p.append("source_url: https URL")
    if "extra" in a:
        if not isinstance(a["extra"], dict):
            p.append("extra: object")
        elif len(json.dumps(a["extra"])) > MAX_EXTRA_BYTES:
            p.append(f"extra: at most {MAX_EXTRA_BYTES} bytes")
    if not p and now is not None and reported is not None:
        anchor = confirmed or reported
        if anchor + timedelta(seconds=ttl) < now:
            p.append("stale: past ttl_s")
    return p


def accept_alerts(data: Any, *, now: datetime | None = None) -> tuple[list[dict], list[str]]:
    """The alerts a caller keeps from an /alerts response, and why the
    rest were dropped. Applies the response caps: unknown kinds and
    malformed records are dropped, and the list is cut at MAX_ALERTS."""
    if not isinstance(data, dict) or not isinstance(data.get("alerts"), list):
        return [], ["response: {alerts: [...]} required"]
    kept: list[dict] = []
    problems: list[str] = []
    for i, a in enumerate(data["alerts"]):
        errs = validate_alert(a, now=now)
        if errs:
            ident = a.get("id") if isinstance(a, dict) else None
            problems.append(f"alerts[{i}]{' ' + str(ident) if ident else ''}: " + "; ".join(errs))
            continue
        kept.append(a)
    if len(kept) > MAX_ALERTS:
        problems.append(f"alerts: {len(kept)} returned, cut at {MAX_ALERTS}")
        kept = kept[:MAX_ALERTS]
    return kept, problems


def validate_handshake(h: Any) -> list[str]:
    if not isinstance(h, dict):
        return ["not an object"]
    p: list[str] = []
    if h.get("protocol") != PROTOCOL:
        p.append(f"protocol: must be {PROTOCOL!r}")
    if not isinstance(h.get("id"), str) or not re.match(r"^[a-z0-9][a-z0-9-]{1,62}$", h["id"]):
        p.append("id: 2 to 63 lowercase letters, digits and hyphens")
    if not isinstance(h.get("name"), str) or not 1 <= len(h["name"]) <= 80:
        p.append("name: 1 to 80 characters")
    caps = h.get("capabilities")
    if not isinstance(caps, dict) or caps.get("alerts") is not True:
        p.append("capabilities: object with alerts: true")
    elif any(k not in CAPABILITIES or not isinstance(v, bool) for k, v in caps.items()):
        p.append("capabilities: only " + ", ".join(CAPABILITIES) + ", each a boolean")
    kinds = h.get("kinds")
    if not isinstance(kinds, list) or not kinds or any(k not in KINDS for k in kinds):
        p.append("kinds: non-empty list from the Flare vocabulary")
    cov = h.get("coverage")
    bbox = cov.get("bbox") if isinstance(cov, dict) else None
    if not (isinstance(bbox, list) and len(bbox) == 4 and all(_num(x) for x in bbox)
            and -90 <= bbox[0] < bbox[2] <= 90 and -180 <= bbox[1] < bbox[3] <= 180):
        p.append("coverage.bbox: [south, west, north, east]")
    r = h.get("refresh_s")
    if not (isinstance(r, int) and not isinstance(r, bool) and MIN_REFRESH_S <= r <= MAX_TTL_S):
        p.append(f"refresh_s: integer in {MIN_REFRESH_S}..{MAX_TTL_S}")
    attr = h.get("attribution")
    if not (isinstance(attr, dict) and isinstance(attr.get("name"), str) and attr["name"]):
        p.append("attribution: {name, url?}")
    if h.get("auth") not in ("none", "bearer"):
        p.append("auth: 'none' or 'bearer'")
    return p


def validate_manifest(m: Any) -> list[str]:
    if not isinstance(m, dict):
        return ["not an object"]
    p: list[str] = []
    if not isinstance(m.get("id"), str) or not re.match(r"^[a-z0-9][a-z0-9-]{1,62}$", m["id"]):
        p.append("id: 2 to 63 lowercase letters, digits and hyphens")
    if not isinstance(m.get("base"), str) or not m["base"].startswith("https://"):
        p.append("base: https URL")
    if m.get("protocol") != PROTOCOL:
        p.append(f"protocol: must be {PROTOCOL!r}")
    if m.get("visibility") not in VISIBILITY:
        p.append("visibility: public, unlisted or private")
    if m.get("trust") not in TRUST:
        p.append("trust: official, verified, community or private")
    if m.get("visibility") == "public" and m.get("trust") == "private":
        p.append("a public plugin cannot have private trust")
    attr = m.get("attribution")
    if attr is not None and (not isinstance(attr, dict) or not isinstance(attr.get("name"), str)):
        p.append("attribution: {name, url?}")
    elif isinstance(attr, dict) and "url" in attr and not (
            isinstance(attr["url"], str) and attr["url"].startswith("https://")):
        p.append("attribution.url: https URL")
    return p


def reporter_pseudonym(plugin_id: str, uid: str, secret: str) -> str:
    """The per-plugin, stable, opaque reporter id: a keyed hash, so a
    plugin can rate-limit and score a reporter without learning who it
    is, and two plugins cannot join their reporters."""
    mac = hmac.new(secret.encode("utf-8"), f"{plugin_id}\n{uid}".encode(), hashlib.sha256)
    return "r:" + mac.hexdigest()[:24]


# ---------------------------------------------------------------- checks

class Report:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def ok(self, what: str) -> None:
        self.passed.append(what)

    def fail(self, what: str, why: str) -> None:
        self.failed.append(f"{what}: {why}")

    @property
    def success(self) -> bool:
        return not self.failed

    def text(self) -> str:
        lines = [f"PASS {p}" for p in self.passed] + [f"FAIL {f}" for f in self.failed]
        lines.append(f"{len(self.passed)} passed, {len(self.failed)} failed")
        return "\n".join(lines)


async def check_plugin(base: str, *, token: str | None = None, client=None,
                       now: datetime | None = None) -> Report:
    """Run the conformance suite against a live plugin at ``base``.

    ``client`` is an httpx.AsyncClient (injectable for tests). Reports
    and confirmations, when declared, use a clearly marked test record.
    """
    import httpx

    rep = Report()
    base = base.rstrip("/")
    if not base.startswith("https://") and not base.startswith("http://127.0.0.1") \
            and not base.startswith("http://localhost"):
        rep.fail("base", "must be https:// (localhost allowed for development)")
        return rep
    headers = {"Accept": "application/json", "User-Agent": "flare-check/1"}
    own = client is None
    client = client or httpx.AsyncClient(timeout=20.0)
    try:
        r = await client.get(f"{base}/flare/v1/handshake", headers=headers)
        if r.status_code != 200:
            rep.fail("handshake", f"HTTP {r.status_code}")
            return rep
        try:
            hs = r.json()
        except ValueError:
            rep.fail("handshake", "not JSON")
            return rep
        errs = validate_handshake(hs)
        if errs:
            rep.fail("handshake", "; ".join(errs))
            return rep
        rep.ok("handshake shape")
        if hs.get("auth") == "bearer":
            if not token:
                rep.fail("auth", "plugin wants a bearer token; pass --token")
                return rep
            headers["Authorization"] = f"Bearer {token}"
        s, w, n, e = hs["coverage"]["bbox"]
        lat, lon = (s + n) / 2, (w + e) / 2
        r = await client.get(f"{base}/flare/v1/alerts",
                             params={"lat": lat, "lon": lon, "r": 25_000}, headers=headers)
        if r.status_code != 200:
            rep.fail("alerts", f"HTTP {r.status_code}")
            return rep
        if len(r.content) > MAX_BYTES:
            rep.fail("alerts", f"{len(r.content)} bytes, cap is {MAX_BYTES}")
        try:
            data = r.json()
        except ValueError:
            rep.fail("alerts", "not JSON")
            return rep
        kept, problems = accept_alerts(data, now=now or datetime.now(UTC))
        ttl = data.get("ttl_s")
        if not (isinstance(ttl, int) and 1 <= ttl <= MAX_TTL_S):
            rep.fail("alerts.ttl_s", "integer in 1..86400 required")
        if parse_ts(data.get("as_of")) is None:
            rep.fail("alerts.as_of", "ISO 8601 with an offset required")
        for pr in problems:
            rep.fail("alerts", pr)
        if not problems:
            rep.ok(f"alerts: {len(kept)} valid record(s)")
        declared = {k for k in hs["kinds"]}
        undeclared = {a["kind"] for a in kept} - declared
        if undeclared:
            rep.fail("alerts", "kinds not declared in the handshake: "
                     + ", ".join(sorted(undeclared)))
        r = await client.get(f"{base}/flare/v1/alerts", headers=headers,
                             params={"lat": lat, "lon": lon, "r": MAX_RADIUS_M * 10})
        if r.status_code not in (200, 400, 422):
            rep.fail("alerts oversize radius", f"HTTP {r.status_code}; answer 200 (clamped) or 400")
        else:
            rep.ok("alerts oversize radius handled")
        caps = hs["capabilities"]
        if caps.get("report"):
            body = {"kind": "OTHER", "lat": lat, "lon": lon,
                    "ts": datetime.now(UTC).isoformat(),
                    "description": "flare-check test report (ignore)",
                    "reporter": "r:flarecheck000000000000", "client": "flare-check/1"}
            r = await client.post(f"{base}/flare/v1/report", json=body, headers=headers)
            if r.status_code in (201, 202, 422):
                rep.ok(f"report answered {r.status_code}")
                if r.status_code == 201:
                    try:
                        created = r.json()
                    except ValueError:
                        created = {}
                    alert = created.get("alert") if isinstance(created, dict) else None
                    if alert is not None and validate_alert(alert):
                        rep.fail("report", "returned alert is invalid: "
                                 + "; ".join(validate_alert(alert)))
                    if caps.get("confirm") and isinstance(created, dict) and created.get("id"):
                        r2 = await client.post(f"{base}/flare/v1/confirm", headers=headers,
                                               json={"alert_id": created["id"], "vote": "gone",
                                                     "ts": datetime.now(UTC).isoformat(),
                                                     "reporter": body["reporter"]})
                        if r2.status_code == 200:
                            rep.ok("confirm round trip")
                        else:
                            rep.fail("confirm", f"HTTP {r2.status_code}")
            else:
                rep.fail("report", f"HTTP {r.status_code}; answer 201, 202 or 422")
        if caps.get("confirm"):
            r = await client.post(f"{base}/flare/v1/confirm", headers=headers,
                                  json={"alert_id": "flare-check-unknown", "vote": "up",
                                        "ts": datetime.now(UTC).isoformat(),
                                        "reporter": "r:flarecheck000000000000"})
            if r.status_code == 404:
                rep.ok("confirm unknown alert is 404")
            else:
                rep.fail("confirm unknown alert", f"HTTP {r.status_code}; answer 404")
        return rep
    finally:
        if own:
            await client.aclose()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2 or argv[0] != "check":
        print("usage: python -m ca_roads.flare check https://plugin.example.com [--token T]")
        return 2
    token = None
    if "--token" in argv:
        token = argv[argv.index("--token") + 1]
    rep = asyncio.run(check_plugin(argv[1], token=token))
    print(rep.text())
    return 0 if rep.success else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
