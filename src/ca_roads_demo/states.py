"""Out-of-state data adapters for the map.

First wave of the multi-state expansion (docs/state-expansion-audit.md):

- Maine / New Hampshire / Vermont via the tri-state NE Compass C2C XML
  portal (keyless): incidents, lane closures, message signs, road
  weather, and cameras. Camera snapshots arrive as base64 JPEG bytes
  embedded in the XML, so the map serves them through /api/stcam
  instead of an external image host.
- Iowa roadwork/closures via the Iowa DOT WZDx feed (keyless, CC0).

Everything is normalized into the exact marker dicts /api/mapdata
already ships for California, tagged with a "src" agency label the
popups display. Feeds are TTL-cached with stale-while-revalidate and
fetched only when the requested viewport touches the state, so
California browsing never pays for them.
"""

from __future__ import annotations

import re
import time
from base64 import b64decode
from datetime import datetime
from urllib.parse import quote
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from ca_roads.cache import TTLCache

NEC_URL = "https://nec-por.ne-compass.com/NEC.XmlDataPortal/api/c2c"
IA_WZDX_URL = "https://iowa-atms.cloud-q-free.com/api/rest/dataprism/wzdx/wzdxfeed"
UA = {"User-Agent": "commutescout.com feed client (nic@glazkov.com)"}

TTL = 180.0
MAX_SERVE = 1800.0
CAM_TTL = 600.0          # the camera XML is ~20 MB per state; refresh slowly
TZ_EAST = ZoneInfo("America/New_York")

# (lat_min, lon_min, lat_max, lon_max) - fetch a state only when the
# viewport overlaps it.
NEC_STATES = {
    "me": ("Maine", "MaineDOT", (42.9, -71.2, 47.5, -66.8)),
    "nh": ("NewHampshire", "NHDOT", (42.6, -72.6, 45.4, -70.6)),
    "vt": ("Vermont", "VTrans", (42.7, -73.5, 45.1, -71.4)),
}
IA_BOUNDS = (40.3, -96.7, 43.6, -90.0)

_cache = TTLCache()
# (state, camera id) -> (jpeg bytes, monotonic stamp); filled when the
# camera bundle parses, served by /api/stcam.
_snapshots: dict[tuple[str, str], tuple[bytes, float]] = {}
# (state, camera id) -> (lat, lon); filled from cctvStatusData in the
# main bundle so snapshot frames can be placed on the map.
_cam_locs: dict[tuple[str, str], tuple[float, float]] = {}


def _iter_records(data: bytes, local_name: str):
    """Complete elements whose LOCAL tag name matches, namespace-blind.

    The NEC feed namespaces every element ({http://its.gov/c2c_icd}dms),
    so plain tag comparison never matches. Pull-parsing also salvages
    whatever completed if the stream is ever truncated, same policy as
    ca_roads.xmlutil for the California feeds. Parsing stays on the
    stdlib pull parser: modern expat rejects entity-expansion bombs by
    default and ElementTree never resolves external entities.
    """
    parser = ElementTree.XMLPullParser(events=("end",))
    records = []
    try:
        parser.feed(data)
        for _, elem in parser.read_events():
            if _strip_ns(elem.tag) == local_name:
                records.append(elem)
        parser.close()
    except ElementTree.ParseError:
        for _, elem in parser.read_events():
            if _strip_ns(elem.tag) == local_name:
                records.append(elem)
    return records


def _overlaps(box, bounds) -> bool:
    lat_min, lon_min, lat_max, lon_max = box
    b0, b1, b2, b3 = bounds
    return not (lat_max < b0 or lat_min > b2 or lon_max < b1 or lon_min > b3)


def _micro(v: str | None) -> float | None:
    try:
        return int(v) / 1_000_000.0
    except (TypeError, ValueError):
        return None


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(el, name: str) -> str:
    child = el.find(f".//{{*}}{name}")
    return (child.text or "").strip() if child is not None and child.text else ""


def _nec_reported(el) -> str | None:
    """confirmedDate 'M/D/YYYY' + confirmedTime 'HH:MM:SS' in Eastern."""
    date, clock = _text(el, "confirmedDate"), _text(el, "confirmedTime")
    if not date:
        return None
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            stamp = datetime.strptime(f"{date} {clock}".strip(), fmt)
            return stamp.replace(tzinfo=TZ_EAST).isoformat()
        except ValueError:
            continue
    return None


# TMDD-style DMS messages embed formatting codes like [nl] (new line),
# [np] (new page) and [jl3]/[pt...] justification/timing codes.
_DMS_BREAK = re.compile(r"\[(?:nl|np)[^\]]*\]", re.IGNORECASE)
_DMS_NOISE = re.compile(r"\[[a-z]{2}[^\]]*\]", re.IGNORECASE)


def _dms_lines(message: str) -> list[str]:
    parts = _DMS_BREAK.split(message or "")
    lines = [_DMS_NOISE.sub("", p).strip() for p in parts]
    return [ln for ln in lines if ln]


def _closure_cls(el) -> str:
    blocked = [d for d in el.iter() if _strip_ns(d.tag) == "laneDetails"
               and (d.get("status") or "").lower() in ("blocked", "closed")]
    total = [d for d in el.iter() if _strip_ns(d.tag) == "laneDetails"]
    if total and len(blocked) >= len(total):
        return "full-roadway"
    return "lane" if blocked else "other"


def _parse_nec_bundle(data: bytes, code: str, agency: str) -> list[dict]:
    """One state's incidents, closures, signs, weather, and camera
    locations (cctvStatusData), as map markers."""
    markers: list[dict] = []

    for inc in _iter_records(data, "incident"):
        loc = inc.find(".//{*}startLocation")
        if loc is None:
            continue
        lat, lon = _micro(_text(loc, "lat")), _micro(_text(loc, "lon"))
        if not lat or not lon:
            continue
        road = _text(loc, "roadway")
        city = _text(loc, "city")
        markers.append({
            "kind": "incident", "lat": lat, "lon": lon,
            "type": _text(inc, "eventType") or "Incident",
            "location": ", ".join(x for x in (road, city) if x)
                        or _text(inc, "desc")[:120],
            "area": "", "src": agency,
            "dir": _text(loc, "direction") or None,
            "reported": _nec_reported(inc),
            "detail": _text(inc, "desc")[:300] or None,
        })

    for clo in _iter_records(data, "laneClosure"):
        loc = clo.find(".//{*}startLocation")
        if loc is None:
            continue
        lat, lon = _micro(_text(loc, "lat")), _micro(_text(loc, "lon"))
        if not lat or not lon:
            continue
        marker = {
            "kind": "lane_closure", "lat": lat, "lon": lon,
            "label": _text(clo, "desc")[:250],
            "cls": _closure_cls(clo),
            "route": _text(loc, "roadway"),
            "county": _text(loc, "county"), "src": agency,
            "lanes": None, "work": None, "facility": None,
            "delay_min": None, "since": None, "until": None,
        }
        end = clo.find(".//{*}endLocation")
        if end is not None:
            elat, elon = _micro(_text(end, "lat")), _micro(_text(end, "lon"))
            if elat and elon and (abs(elat - lat) > 0.002
                                  or abs(elon - lon) > 0.002):
                marker["end"] = [round(elat, 5), round(elon, 5)]
                path = [[lat, lon]]
                for pt in clo.iter():
                    if _strip_ns(pt.tag) == "point":
                        plat = _micro(_text(pt, "lat"))
                        plon = _micro(_text(pt, "lon"))
                        if plat and plon:
                            path.append([round(plat, 5), round(plon, 5)])
                path.append([elat, elon])
                if len(path) > 2:
                    marker["path"] = path[:80]
        markers.append(marker)

    for dms in _iter_records(data, "dms"):
        if "online" not in _text(dms, "status").lower():
            continue
        lat, lon = _micro(_text(dms, "lat")), _micro(_text(dms, "lon"))
        if not lat or not lon:
            continue
        lines = _dms_lines(_text(dms, "message"))
        marker = {
            "kind": "sign", "lat": lat, "lon": lon,
            "route": _text(dms, "roadway"),
            "direction": _text(dms, "direction") or None,
            "near": _text(dms, "locationDescription") or _text(dms, "name"),
            "message": " / ".join(lines), "lines": lines, "src": agency,
        }
        if not lines:
            marker["blank"] = True
        markers.append(marker)

    for ess in _iter_records(data, "ess"):
        if "online" not in _text(ess, "status").lower():
            continue
        lat, lon = _micro(_text(ess, "lat")), _micro(_text(ess, "lon"))
        if not lat or not lon:
            continue

        def tenth(name, el=ess):
            raw = _text(el, name)
            try:
                return int(raw) / 10.0   # TMDD reports tenths of a unit
            except (TypeError, ValueError):
                return None

        vis = None
        raw_vis = _text(ess, "visibility")
        if raw_vis.isdigit():
            vis = int(raw_vis)
        markers.append({
            "kind": "rwis", "lat": lat, "lon": lon,
            "station": _text(ess, "name"),
            "route": _text(ess, "roadway"), "src": agency,
            "air_c": tenth("airTemp"), "pave_c": tenth("pavementTemp"),
            "wind": tenth("windSpeed") if tenth("windSpeed") else None,
            "gust": None, "vis_m": vis,
        })

    # Camera locations: snapshots carry no coordinates, so remember
    # where each camera lives for _parse_nec_cameras to join on id.
    for cam in _iter_records(data, "cctvStatus"):
        cam_id = (cam.get("id") or "").strip()
        lat, lon = _micro(_text(cam, "lat")), _micro(_text(cam, "lon"))
        if cam_id and lat and lon:
            _cam_locs[(code, cam_id)] = (lat, lon)
    return markers


def _parse_nec_cameras(data: bytes, code: str, agency: str) -> list[dict]:
    """Camera markers; snapshot bytes go into _snapshots for /api/stcam.

    The 20 MB payload is XML with one base64 JPEG per camera; parse
    iteratively and keep only the decoded bytes.
    """
    markers: list[dict] = []
    now = time.monotonic()
    for cam in _iter_records(data, "cctvSnapshot"):
        cam_id = (cam.get("id") or "").strip()
        name = _text(cam, "name") or cam_id
        snippet = _text(cam, "snippet")
        if not cam_id or not snippet:
            continue
        loc = _cam_locs.get((code, cam_id))
        if not loc:
            continue   # no coordinates known for this camera; cannot map it
        try:
            _snapshots[(code, cam_id)] = (b64decode(snippet), now)
        except Exception:  # noqa: BLE001 - a bad frame is not fatal
            continue
        markers.append({
            "kind": "camera", "lat": loc[0], "lon": loc[1],
            "name": name, "route": None, "direction": None,
            "near": name, "src": agency,
            "image": f"/api/stcam/{code}/{quote(cam_id)}",
            "stream": None,
        })
    return markers


async def _fetch_nec(client, code: str) -> dict:
    net, agency, _bounds = NEC_STATES[code]
    resp = await client.get(
        NEC_URL, headers=UA, timeout=30.0,
        params={"networks": net,
                "dataTypes": "incidentData,laneClosureData,dmsData,essData,"
                             "cctvStatusData"})
    resp.raise_for_status()
    return {"markers": _parse_nec_bundle(resp.content, code, agency)}


async def _fetch_nec_cameras(client, code: str) -> dict:
    net, agency, _bounds = NEC_STATES[code]
    resp = await client.get(
        NEC_URL, headers=UA, timeout=60.0,
        params={"networks": net, "dataTypes": "cctvSnapshotData"})
    resp.raise_for_status()
    return {"markers": _parse_nec_cameras(resp.content, code, agency)}


_IMPACT_CLS = {
    "all-lanes-closed": "full-roadway",
    "some-lanes-closed": "lane",
    "some-lanes-closed-merge-left": "lane",
    "some-lanes-closed-merge-right": "lane",
    "alternating-one-way": "one-way-traffic",
    "all-lanes-open": "other",
}


def _iso_epoch(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _parse_ia_wzdx(payload: dict) -> list[dict]:
    markers: list[dict] = []
    for feat in payload.get("features", []):
        props = (feat.get("properties") or {})
        core = props.get("core_details") or {}
        if core.get("event_type") not in (None, "work-zone", "restriction"):
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") == "MultiPoint" or geom.get("type") == "LineString":
            pts = coords
        else:
            continue
        pts = [c for c in pts if isinstance(c, list) and len(c) >= 2]
        if not pts:
            continue
        lat, lon = pts[0][1], pts[0][0]
        marker = {
            "kind": "lane_closure", "lat": lat, "lon": lon,
            "label": (core.get("description") or "")[:250],
            "cls": _IMPACT_CLS.get(props.get("vehicle_impact"), "other"),
            "route": ", ".join(core.get("road_names") or [])[:60],
            "county": None, "src": "Iowa DOT",
            "lanes": None,
            "work": (props.get("types_of_work") or [{}])[0].get("type_name")
                    if props.get("types_of_work") else None,
            "facility": None, "delay_min": None,
            "since": _iso_epoch(props.get("start_date")),
            "until": _iso_epoch(props.get("end_date")),
        }
        if len(pts) > 1:
            step = max(1, len(pts) // 60)
            path = [[round(c[1], 5), round(c[0], 5)] for c in pts[::step]]
            if path[-1] != [round(pts[-1][1], 5), round(pts[-1][0], 5)]:
                path.append([round(pts[-1][1], 5), round(pts[-1][0], 5)])
            marker["end"] = path[-1]
            marker["path"] = path
        markers.append(marker)
    return markers


async def _fetch_iowa(client) -> dict:
    resp = await client.get(IA_WZDX_URL, headers=UA, timeout=30.0)
    resp.raise_for_status()
    return {"markers": _parse_ia_wzdx(resp.json())}


def snapshot(code: str, cam_id: str) -> bytes | None:
    hit = _snapshots.get((code, cam_id))
    return hit[0] if hit else None


async def markers_for_bbox(client, box, want) -> list[dict]:
    """All out-of-state markers intersecting the viewport. Never raises:
    a failing state simply contributes nothing this cycle."""
    lat_min, lon_min, lat_max, lon_max = box
    out: list[dict] = []
    # Honor the same kinds filter the California feeds do.
    kind_group = {"incident": "incident", "lane_closure": "closure",
                  "chain_control": "chain", "wildfire": "fire",
                  "camera": "camera", "sign": "sign", "rwis": "rwis"}

    async def add(outcome):
        if outcome.value:
            for m in outcome.value["markers"]:
                if kind_group.get(m.get("kind")) not in want:
                    continue
                if m.get("lat") and m.get("lon") \
                        and lat_min <= m["lat"] <= lat_max \
                        and lon_min <= m["lon"] <= lon_max:
                    out.append(m)

    for code, (_net, _agency, bounds) in NEC_STATES.items():
        if not _overlaps(box, bounds):
            continue
        await add(await _cache.get(
            f"nec:{code}", TTL, MAX_SERVE,
            lambda c=code: _fetch_nec(client, c)))
        if "camera" in want:
            await add(await _cache.get(
                f"neccam:{code}", CAM_TTL, MAX_SERVE,
                lambda c=code: _fetch_nec_cameras(client, c)))
    if _overlaps(box, IA_BOUNDS):
        await add(await _cache.get(
            "ia:wzdx", TTL, MAX_SERVE, lambda: _fetch_iowa(client)))
    return out


def source_status() -> list[dict]:
    """Entries for /api/sources describing the expansion states. Reports
    cache state without forcing a fetch."""
    out = []
    for code, (_net, agency, _bounds) in NEC_STATES.items():
        entry = _cache._entries.get(f"nec:{code}")  # noqa: SLF001 - read-only peek
        out.append({
            "name": f"{agency} (NE Compass)", "agency": agency,
            "on_demand": entry is None,
            **({"ok": True, "stale": False, "count": len(entry.value["markers"]),
                "as_of": entry.fetched_at.isoformat()} if entry else {}),
        })
    entry = _cache._entries.get("ia:wzdx")  # noqa: SLF001
    out.append({
        "name": "Roadwork (WZDx)", "agency": "Iowa DOT",
        "on_demand": entry is None,
        **({"ok": True, "stale": False, "count": len(entry.value["markers"]),
            "as_of": entry.fetched_at.isoformat()} if entry else {}),
    })
    return out
