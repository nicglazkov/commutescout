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

import asyncio
import contextlib
import html as _html
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
UA = {"User-Agent":
      "commutescout.com feed client (https://commutescout.com)"}

TTL = 180.0
MAX_SERVE = 1800.0
CAM_TTL = 600.0          # the camera XML is ~20 MB per state; refresh slowly
WZDX_TTL = 600.0         # WZDx dumps change slowly and some are 8-16 MB
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
    # Some agencies park placeholder junk like "." or "-" on idle
    # boards; a line with no letters or digits is not a message.
    return [ln for ln in lines if re.search(r"[A-Za-z0-9]", ln)]


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


def _parse_ia_wzdx(payload: dict, src: str = "Iowa DOT",
                   cap: int = 2000) -> list[dict]:
    """WZDx FeatureCollection to closure markers. Only work that is
    ACTIVE NOW ships (same semantics as the California LCS layer):
    many feeds list projects months out, and a 16 MB statewide plan
    dump is noise on a live-conditions map."""
    now = time.time()
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
        since = _iso_epoch(props.get("start_date"))
        until = _iso_epoch(props.get("end_date"))
        # Prefer the feed's own status when it declares one (UDOT marks
        # everything with lapsed *estimated* end dates but
        # event_status=active); fall back to the date window.
        status = (props.get("event_status") or "").lower()
        if status in ("planned", "pending", "completed", "cancelled"):
            continue
        if status != "active" and (
                (since and since > now) or (until and until < now)):
            continue          # planned for later, or already done
        lat, lon = pts[0][1], pts[0][0]
        marker = {
            "kind": "lane_closure", "lat": lat, "lon": lon,
            "label": (core.get("description") or "")[:250],
            "cls": _IMPACT_CLS.get(props.get("vehicle_impact"), "other"),
            "route": ", ".join(core.get("road_names") or [])[:60],
            "county": None, "src": src,
            "lanes": None,
            "work": (props.get("types_of_work") or [{}])[0].get("type_name")
                    if props.get("types_of_work") else None,
            "facility": None, "delay_min": None,
            "since": since, "until": until,
        }
        if len(pts) > 1:
            step = max(1, len(pts) // 60)
            path = [[round(c[1], 5), round(c[0], 5)] for c in pts[::step]]
            if path[-1] != [round(pts[-1][1], 5), round(pts[-1][0], 5)]:
                path.append([round(pts[-1][1], 5), round(pts[-1][0], 5)])
            marker["end"] = path[-1]
            marker["path"] = path
        markers.append(marker)
        if len(markers) >= cap:
            break
    return markers


def snapshot(code: str, cam_id: str) -> bytes | None:
    hit = _snapshots.get((code, cam_id))
    return hit[0] if hit else None


# ── Wave 2: keyed states (WSDOT, TripCheck, OHGO) + NC WZDx ──────────

WA_BOUNDS = (45.5, -124.9, 49.05, -116.9)
OR_BOUNDS = (41.9, -124.7, 46.3, -116.4)
OH_BOUNDS = (38.4, -84.9, 42.0, -80.5)
NC_BOUNDS = (33.7, -84.4, 36.6, -75.4)
NC_WZDX_URL = "https://www.drivenc.gov/api/wzdx"

# Alert categories that are planned work rather than live incidents.
_WA_WORK = {"Closure", "Construction", "Maintenance"}


def _wa_key() -> str:
    import os
    return os.environ.get("WSDOT_API_KEY", "")


def _or_key() -> str:
    import os
    return os.environ.get("TRIPCHECK_API_KEY", "")


def _oh_key() -> str:
    import os
    return os.environ.get("OHGO_API_KEY", "")


def _ut_key() -> str:
    import os
    return os.environ.get("UT511_API_KEY", "")


UT_BOUNDS = (36.9, -114.1, 42.1, -109.0)

# Travel-IQ platform states: one client, per-state host and key.
# code: (state, bounds, api base, key env var, source label)
TRAVELIQ = {
    "utk": ("Utah", UT_BOUNDS, "https://www.udottraffic.utah.gov",
            "UT511_API_KEY", "UDOT"),
    "azk": ("Arizona", (31.3, -114.9, 37.1, -109.0), "https://az511.gov",
            "AZ511_API_KEY", "ADOT"),
    "akk": ("Alaska", (54.5, -170.0, 71.5, -129.9),
            "https://511.alaska.gov", "AK511_API_KEY", "Alaska DOT&PF"),
}


def _tiq_ready(code):
    import os
    env = TRAVELIQ[code][3]
    return lambda: os.environ.get(env, "")


async def _fetch_ut(client) -> dict:
    """Kept for tests and as the template call: Utah via Travel-IQ."""
    return await _fetch_traveliq(client, "utk")


async def _fetch_traveliq(client, code: str) -> dict:
    """Full coverage for a Travel-IQ state (same API family as the
    Nevada client): events, cameras, live sign text, and road weather.
    A ready key supersedes the state's WZDx-only feed."""
    import os
    _st, _bounds, host, env, src = TRAVELIQ[code]
    key = os.environ.get(env, "")
    base = f"{host}/api/v2/get"

    async def get(res):
        r = await client.get(f"{base}/{res}", headers=UA, timeout=30.0,
                             params={"key": key, "format": "json"})
        r.raise_for_status()
        return r.json() or []

    events, cams, signs, wx = await asyncio.gather(
        get("event"), get("cameras"), get("messagesigns"),
        get("weatherstations"))
    now = time.time()
    markers: list[dict] = []
    for e in events:
        try:
            lat, lon = float(e.get("Latitude")), float(e.get("Longitude"))
        except (TypeError, ValueError):
            continue
        if not lat or not lon:
            continue
        start = e.get("StartDate")
        # Future-scheduled work stays off the map. Lapsed planned
        # end dates are NOT trusted: these agencies keep them on
        # live work (the same quirk UDOT's WZDx feed has).
        if isinstance(start, (int, float)) and start > now:
            continue
        desc = re.sub(r"\s+", " ", (e.get("Description") or "")).strip()
        road = (e.get("RoadwayName") or "").strip()
        label = (f"{road}: {desc}" if road and desc else desc or road
                 or "Reported event")[:220]
        if (e.get("EventType") or "") == "accidentsAndIncidents":
            markers.append({
                "kind": "incident", "lat": lat, "lon": lon,
                "type": e.get("EventSubType") or "Incident",
                "label": label, "src": src})
        else:
            etype = (e.get("EventType") or "")
            lanes = (e.get("LanesAffected") or "").lower()
            cls = ("full-roadway"
                   if etype == "closures"
                   or re.search(r"all lanes|full closure", lanes)
                   else "lane")
            markers.append({
                "kind": "lane_closure", "lat": lat, "lon": lon,
                "cls": cls, "label": label, "route": road or None,
                "src": src})
    for c in cams:
        try:
            lat, lon = float(c.get("Latitude")), float(c.get("Longitude"))
        except (TypeError, ValueError):
            continue
        views = c.get("Views") or []
        url = (views[0] or {}).get("Url") if views else None
        if not lat or not lon or not url:
            continue
        markers.append({
            "kind": "camera", "lat": lat, "lon": lon,
            "name": c.get("Location") or c.get("Roadway"),
            "route": c.get("Roadway"), "direction": c.get("Direction"),
            "near": c.get("Location"), "image": url, "src": src})
    for s in signs:
        try:
            lat, lon = float(s.get("Latitude")), float(s.get("Longitude"))
        except (TypeError, ValueError):
            continue
        # Message pages are list entries; lines break on \n and tab
        # columns (travel-time boards) flatten to spaces.
        lines = [re.sub(r"[\t ]+", " ", ln).strip()
                 for msg in (s.get("Messages") or [])
                 if isinstance(msg, str) and msg != "NO_MESSAGE"
                 for ln in re.split(r"\n|<[^>]+>|\[nl\]|\[np\]", msg)
                 if ln.strip() and re.search(r"[A-Za-z0-9]", ln)][:6]
        m = {"kind": "sign", "lat": lat, "lon": lon,
             "route": s.get("Roadway"),
             "direction": s.get("DirectionOfTravel"),
             "near": s.get("Name") or "Message sign",
             "message": " / ".join(lines), "lines": lines, "src": src}
        if not lines:
            m["blank"] = True
        markers.append(m)
    for w in wx:
        try:
            lat, lon = float(w.get("Latitude")), float(w.get("Longitude"))
        except (TypeError, ValueError):
            continue
        marker = {"kind": "rwis", "lat": lat, "lon": lon,
                  "name": w.get("StationName") or "Weather station",
                  "src": src}
        with contextlib.suppress(TypeError, ValueError):
            marker["air_c"] = round(
                (float(w.get("AirTemperature")) - 32) * 5 / 9, 1)
        with contextlib.suppress(TypeError, ValueError):
            marker["gust"] = float(w.get("WindSpeedAvg"))
        surface = w.get("SurfaceStatus")
        if surface and surface not in ("None", "Unknown"):
            marker["surface"] = surface
        markers.append(marker)
    return {"markers": markers}


async def _fetch_wa(client) -> dict:
    key = _wa_key()
    base = "https://wsdot.wa.gov/Traffic/api"
    alerts, cams, passes, weather = [
        (await client.get(u, headers=UA, timeout=30.0)).json()
        for u in (
            f"{base}/HighwayAlerts/HighwayAlertsREST.svc/GetAlertsAsJson?AccessCode={key}",
            f"{base}/HighwayCameras/HighwayCamerasREST.svc/GetCamerasAsJson?AccessCode={key}",
            f"{base}/MountainPassConditions/MountainPassConditionsREST.svc/GetMountainPassConditionsAsJson?AccessCode={key}",
            f"{base}/WeatherInformation/WeatherInformationREST.svc/GetCurrentWeatherInformationAsJson?AccessCode={key}",
        )
    ]
    markers: list[dict] = []
    for a in alerts or []:
        loc = a.get("StartRoadwayLocation") or {}
        lat, lon = loc.get("Latitude"), loc.get("Longitude")
        if not lat or not lon:
            continue
        headline = (a.get("HeadlineDescription") or "")[:250]
        where = ", ".join(x for x in (loc.get("RoadName"),
                                      loc.get("Description")) if x)
        if a.get("EventCategory") in _WA_WORK:
            # No end/stretch here: WSDOT gives endpoints but no road
            # geometry, and a straight begin-to-end line cuts through
            # terrain. A dot beats a line in the forest.
            markers.append({
                "kind": "lane_closure", "lat": lat, "lon": lon,
                "label": headline, "cls": "lane"
                if a.get("EventCategory") != "Closure" else "full-roadway",
                "route": loc.get("RoadName") or "", "county": a.get("County"),
                "src": "WSDOT", "lanes": None, "work": a.get("EventCategory"),
                "facility": None, "delay_min": None,
                "since": None, "until": None,
            })
        else:
            markers.append({
                "kind": "incident", "lat": lat, "lon": lon,
                "type": a.get("EventCategory") or "Incident",
                "location": where or headline[:120],
                "area": "", "src": "WSDOT",
                "dir": loc.get("Direction") or None,
                "reported": None, "detail": headline,
            })
    for c in cams or []:
        loc = c.get("CameraLocation") or {}
        lat = c.get("DisplayLatitude") or loc.get("Latitude")
        lon = c.get("DisplayLongitude") or loc.get("Longitude")
        if not lat or not lon or not c.get("IsActive"):
            continue
        markers.append({
            "kind": "camera", "lat": lat, "lon": lon,
            "name": c.get("Title") or loc.get("Description") or "Camera",
            "route": loc.get("RoadName"), "direction": loc.get("Direction"),
            "near": loc.get("Description"), "src": "WSDOT",
            "image": c.get("ImageURL"), "stream": None,
        })
    for p in passes or []:
        lat, lon = p.get("Latitude"), p.get("Longitude")
        if not lat or not lon:
            continue
        r1 = ((p.get("RestrictionOne") or {}).get("RestrictionText") or "").strip()
        r2 = ((p.get("RestrictionTwo") or {}).get("RestrictionText") or "").strip()
        active = [r for r in (r1, r2)
                  if r and "no restriction" not in r.lower()]
        if not active:
            continue
        markers.append({
            "kind": "chain_control", "lat": lat, "lon": lon,
            "status": "Pass restriction",
            "route": p.get("MountainPassName") or "",
            "label": "; ".join(active)[:220], "src": "WSDOT",
            "updated": None,
        })
    for w in weather or []:
        lat, lon = w.get("Latitude"), w.get("Longitude")
        if not lat or not lon:
            continue
        temp_f = w.get("TemperatureInFahrenheit")
        markers.append({
            "kind": "rwis", "lat": lat, "lon": lon,
            "station": w.get("StationName") or "Weather station",
            "route": None, "src": "WSDOT",
            "air_c": round((temp_f - 32) * 5 / 9, 1)
            if isinstance(temp_f, (int, float)) else None,
            "pave_c": None, "wind": None,
            "gust": w.get("WindGustSpeedInMPH"), "vis_m": None,
        })
    return {"markers": markers}


_OR_HTTP_IMG = re.compile(r"^http://", re.IGNORECASE)


async def _fetch_or(client) -> dict:
    key = {"Ocp-Apim-Subscription-Key": _or_key(), **UA}
    base = "https://api.odot.state.or.us/tripcheck"
    inc = (await client.get(f"{base}/Incidents", headers=key,
                            timeout=30.0)).json()
    cams = (await client.get(f"{base}/Cctv/Inventory", headers=key,
                             timeout=30.0)).json()
    markers: list[dict] = []
    for i in (inc.get("incidents") or []):
        if str(i.get("is-active")).lower() != "true":
            continue
        loc = i.get("location") or {}
        start = loc.get("start-location") or {}
        lat, lon = start.get("start-lat"), start.get("start-long")
        if not lat or not lon:
            continue
        headline = (i.get("headline") or "")[:250]
        where = ", ".join(x for x in (loc.get("route-id"),
                                      loc.get("location-name")) if x)
        if (i.get("event-type-id") or "").upper() == "RW":
            # Same rule as WSDOT: no road geometry means no stretch line.
            markers.append({
                "kind": "lane_closure", "lat": lat, "lon": lon,
                "label": headline, "cls": "lane",
                "route": loc.get("route-id") or "", "county": None,
                "src": "Oregon DOT (TripCheck)", "lanes": None,
                "work": i.get("impact-desc"), "facility": None,
                "delay_min": None, "since": None, "until": None,
            })
        else:
            # Derive a display type from the headline so out-of-state
            # incidents classify into the same map buckets as CHP's.
            low = headline.lower()
            kind_label = ("Crash" if "crash" in low or "collision" in low
                          else "Fire" if "fire" in low
                          else "Hazard" if "debris" in low or "hazard" in low
                          else "Closure" if "closed" in low or "closure" in low
                          else "Incident")
            markers.append({
                "kind": "incident", "lat": lat, "lon": lon,
                "type": kind_label, "location": where or headline[:120],
                "area": "", "src": "Oregon DOT (TripCheck)",
                "dir": loc.get("direction") or None,
                "reported": i.get("update-time"), "detail": headline,
            })
    for c in (cams.get("CCTVInventoryRequest") or []):
        lat, lon = c.get("latitude"), c.get("longitude")
        url = c.get("cctv-url") or ""
        if not lat or not lon or not url:
            continue
        markers.append({
            "kind": "camera", "lat": float(lat), "lon": float(lon),
            "name": c.get("cctv-other") or c.get("device-name") or "Camera",
            "route": c.get("route-id"), "direction": None,
            "near": c.get("cctv-other"),
            "src": "Oregon DOT (TripCheck)",
            # The inventory hands out http:// URLs; the host serves https.
            "image": _OR_HTTP_IMG.sub("https://", url), "stream": None,
        })
    return {"markers": markers}


async def _fetch_oh(client) -> dict:
    hdr = {"Authorization": f"APIKEY {_oh_key()}", **UA}
    base = "https://publicapi.ohgo.com/api/v1"
    inc = (await client.get(f"{base}/incidents?page-all=true", headers=hdr,
                            timeout=30.0)).json()
    con = (await client.get(f"{base}/construction?page-all=true", headers=hdr,
                            timeout=30.0)).json()
    cams = (await client.get(f"{base}/cameras?page-all=true", headers=hdr,
                             timeout=30.0)).json()
    dms = (await client.get(f"{base}/digital-signs?page-all=true", headers=hdr,
                            timeout=30.0)).json()
    markers: list[dict] = []

    def road_items(payload, default_kind):
        for r in (payload.get("results") or []):
            lat, lon = r.get("latitude"), r.get("longitude")
            if not lat or not lon:
                continue
            lat, lon = float(lat), float(lon)
            desc = (r.get("description") or "")[:250]
            if default_kind == "lane_closure" \
                    or (r.get("category") or "") == "Road Work":
                is_ramp = desc.lower().startswith("ramp") \
                    or " ramp " in desc.lower()[:60]
                markers.append({
                    "kind": "lane_closure", "lat": lat, "lon": lon,
                    "label": desc,
                    "cls": "ramp" if is_ramp else "full-roadway"
                    if "closed" in (r.get("roadStatus") or "").lower()
                    else "lane",
                    "route": r.get("routeName") or "", "county": None,
                    "src": "OHGO", "lanes": None,
                    "work": r.get("category"), "facility": None,
                    "delay_min": None, "since": None, "until": None,
                })
            else:
                markers.append({
                    "kind": "incident", "lat": lat, "lon": lon,
                    "type": r.get("category") or "Incident",
                    "location": r.get("location") or "",
                    "area": "", "src": "OHGO",
                    "dir": r.get("direction") or None,
                    "reported": None, "detail": desc,
                })

    road_items(inc, "incident")
    road_items(con, "lane_closure")
    for c in (cams.get("results") or []):
        lat, lon = c.get("latitude"), c.get("longitude")
        views = c.get("cameraViews") or []
        if not lat or not lon or not views:
            continue
        markers.append({
            "kind": "camera", "lat": float(lat), "lon": float(lon),
            "name": c.get("location") or "Camera",
            "route": (views[0] or {}).get("mainRoute"), "direction": None,
            "near": c.get("location"), "src": "OHGO",
            "image": (views[0] or {}).get("largeUrl")
                     or (views[0] or {}).get("smallUrl"),
            "stream": None,
        })
    wx = (await client.get(f"{base}/weather-sensor-sites?page-all=true",
                           headers=hdr, timeout=30.0)).json()
    for w in (wx.get("results") or []):
        lat, lon = w.get("latitude"), w.get("longitude")
        if not lat or not lon:
            continue
        temp = w.get("averageAirTemperature")
        try:
            air_c = round((float(temp) - 32) * 5 / 9, 1)
        except (TypeError, ValueError):
            air_c = None
        markers.append({
            "kind": "rwis", "lat": float(lat), "lon": float(lon),
            "station": w.get("location") or "Weather station",
            "route": None, "src": "OHGO",
            "air_c": air_c, "pave_c": None, "wind": None,
            "gust": None, "vis_m": None,
        })
    for s in (dms.get("results") or []):
        lat, lon = s.get("latitude"), s.get("longitude")
        if not lat or not lon:
            continue
        lines = [ln for msg in (s.get("messages") or [])
                 for ln in str(msg).split("\n") if ln.strip()][:6]
        marker = {
            "kind": "sign", "lat": float(lat), "lon": float(lon),
            "route": None, "direction": None,
            "near": s.get("location") or s.get("description"),
            "message": " / ".join(lines), "lines": lines, "src": "OHGO",
        }
        if not lines:
            marker["blank"] = True
        markers.append(marker)
    return {"markers": markers}


def _co_key() -> str:
    import os
    return os.environ.get("COTRIP_API_KEY", "")


CO_BOUNDS = (36.9, -109.1, 41.1, -102.0)


def _co_when(iso: str | None) -> float | None:
    if not iso:
        return None
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    return None


async def _fetch_co(client) -> dict:
    """Colorado via CDOT's sanctioned data.cotrip.org API: incidents,
    roadwork, live sign text, and weather stations. The API publishes
    no still-camera resource; cameras wait."""
    key = _co_key()
    base = "https://data.cotrip.org/api/v1"

    async def get(res):
        r = await client.get(f"{base}/{res}", headers=UA, timeout=30.0,
                             params={"apiKey": key})
        r.raise_for_status()
        return (r.json() or {}).get("features") or []

    inc, planned, signs, wx = await asyncio.gather(
        get("incidents"), get("plannedEvents"), get("signs"),
        get("weatherStations"))
    now = time.time()
    markers: list[dict] = []

    def point(feat):
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") == "MultiPoint" and coords:
            coords = coords[0]
        if isinstance(coords, list) and len(coords) >= 2:
            return coords[1], coords[0]
        return None, None

    for f in inc:
        lat, lon = point(f)
        p = f.get("properties") or {}
        if not lat or not lon:
            continue
        label = re.sub(r"\s+", " ",
                       (p.get("travelerInformationMessage") or "")).strip()
        markers.append({
            "kind": "incident", "lat": lat, "lon": lon,
            "type": p.get("type") or "Incident",
            "label": (label or p.get("type") or "Incident")[:220],
            "src": "CDOT"})
    for f in planned:
        lat, lon = point(f)
        p = f.get("properties") or {}
        if not lat or not lon:
            continue
        start = _co_when(p.get("startTime"))
        clear = _co_when(p.get("clearTime"))
        if (start and start > now) or (clear and clear < now):
            continue
        label = re.sub(r"\s+", " ",
                       (p.get("travelerInformationMessage") or "")).strip()
        cls = "lane"
        for imp in p.get("laneImpacts") or []:
            types = [t.lower() for t in imp.get("closedLaneTypes") or []]
            closed = str(imp.get("laneClosures") or "0")
            if (closed.isdigit() and imp.get("laneCount")
                    and int(closed) >= imp["laneCount"]
                    and not all("shoulder" in t for t in types)):
                cls = "full-roadway"
        markers.append({
            "kind": "lane_closure", "lat": lat, "lon": lon, "cls": cls,
            "label": (label or p.get("type") or "Roadwork")[:220],
            "route": p.get("routeName"), "src": "CDOT"})
    for f in signs:
        lat, lon = point(f)
        p = f.get("properties") or {}
        if not lat or not lon:
            continue
        lines = (_dms_lines(p.get("messageMarkup") or "")[:6]
                 if (p.get("displayStatus") or "") == "on" else [])
        m = {"kind": "sign", "lat": lat, "lon": lon,
             "route": p.get("routeName"), "direction": p.get("direction"),
             "near": p.get("publicName") or "Message sign",
             "message": " / ".join(lines), "lines": lines, "src": "CDOT"}
        if not lines:
            m["blank"] = True
        markers.append(m)
    for f in wx:
        lat, lon = point(f)
        p = f.get("properties") or {}
        if not lat or not lon:
            continue
        marker = {"kind": "rwis", "lat": lat, "lon": lon,
                  "name": p.get("publicName") or p.get("name")
                  or "Weather station", "src": "CDOT"}
        for sensor in p.get("sensors") or []:
            stype = (sensor.get("type") or "").lower()
            reading = sensor.get("currentReading")
            if ("surface status" in stype and reading
                    and str(reading).lower() not in ("none", "unknown")):
                marker["surface"] = str(reading)
                break
        markers.append(marker)
    return {"markers": markers}


KEYED_STATES = {
    # code: (display state, bounds, fetcher, ready-check)
    "wa": ("Washington", WA_BOUNDS, _fetch_wa, _wa_key),
    "or": ("Oregon", OR_BOUNDS, _fetch_or, _or_key),
    "oh": ("Ohio", OH_BOUNDS, _fetch_oh, _oh_key),
    "cok": ("Colorado", CO_BOUNDS, _fetch_co, _co_key),
}
# Travel-IQ states share one fetcher; the registry entries are built
# from the TRAVELIQ table so a new state there is one line.
for _c in TRAVELIQ:
    KEYED_STATES[_c] = (
        TRAVELIQ[_c][0], TRAVELIQ[_c][1],
        (lambda client, cc=_c: _fetch_traveliq(client, cc)),
        _tiq_ready(_c))

# A ready keyed state replaces its WZDx-only feed so roadwork is not
# drawn twice. keyed code -> wzdx code.
SUPERSEDES = {"utk": "ut", "azk": "az"}


def _wzdx_superseded(wzdx_code: str) -> bool:
    return any(w == wzdx_code and KEYED_STATES[k][3]()
               for k, w in SUPERSEDES.items())


# ── Wave 3: the WZDx registry + remaining keyless states ─────────────
# One WZDx parser covers roadwork/closures in a dozen states; feeds
# listed here are keyless (verified live 2026-07-19).

MD_BOUNDS = (37.9, -79.5, 39.8, -74.9)
MI_BOUNDS = (41.6, -90.5, 48.4, -82.0)
DE_BOUNDS = (38.4, -75.8, 39.9, -74.9)
TN_BOUNDS = (34.9, -90.4, 36.7, -81.6)
MS_BOUNDS = (30.1, -91.7, 35.1, -88.0)
# TravelMidwest aggregates the upper midwest (IL plus IN/WI/IA/KY
# cameras), so its fetch gate covers the region, not just Illinois.
IL_BOUNDS = (36.5, -97.5, 47.5, -84.5)
AL_BOUNDS = (30.1, -88.5, 35.1, -84.9)
MO_BOUNDS = (35.9, -95.8, 40.7, -89.0)

WZDX_FEEDS = {
    # code: (state, src label, bounds, url)
    "ia": ("Iowa", "Iowa DOT", IA_BOUNDS, IA_WZDX_URL),
    "nc": ("North Carolina", "NCDOT", NC_BOUNDS, NC_WZDX_URL),
    "ut": ("Utah", "UDOT", (36.9, -114.1, 42.1, -109.0),
           "https://udottraffic.utah.gov/wzdx/udot/v40/data"),
    "az": ("Arizona", "ADOT", (31.3, -114.9, 37.1, -109.0),
           "https://az511.com/api/wzdx"),
    "id": ("Idaho", "ITD", (41.9, -117.3, 49.1, -111.0),
           "https://511.idaho.gov/api/wzdx"),
    "wi": ("Wisconsin", "WisDOT", (42.4, -92.9, 47.1, -86.7),
           "https://511wi.gov/api/wzdx"),
    "ny": ("New York", "511NY", (40.4, -79.8, 45.1, -71.8),
           "https://511ny.org/api/wzdx"),
    "in": ("Indiana", "INDOT", (37.7, -88.1, 41.8, -84.7),
           "https://in.carsprogram.org/carsapi_v1/api/wzdx"),
    "mnw": ("Minnesota", "MnDOT", (43.4, -97.3, 49.4, -89.4),
            "https://mn.carsprogram.org/carsapi_v1/api/wzdx"),
    "ks": ("Kansas", "KDOT", (36.9, -102.1, 40.1, -94.5),
           "https://kscars.kandrive.gov/carsapi_v1/api/wzdx"),
    "nj": ("New Jersey", "NJDOT", (38.8, -75.6, 41.4, -73.8),
           "https://smartworkzones.njit.edu/nj/wzdx"),
    "mdw": ("Maryland", "MDOT SHA", MD_BOUNDS,
            "https://filter.ritis.org/wzdx_v4.1/mdot.geojson"),
    "mow": ("Missouri", "MoDOT", MO_BOUNDS,
            "https://traveler.modot.org/timconfig/feed/desktop/mo_wzdx.json"),
    # 2026-07-20 wave. All CC0 per the FHWA registry. The Oklahoma
    # access token is PUBLISHED verbatim in the public registry entry
    # (intentionally public, not a secret).
    "ky": ("Kentucky", "KYTC", (36.4, -89.6, 39.2, -81.9),
           "https://storage.googleapis.com/kytc-its-2020-openrecords/"
           "public/feeds/WZDx/kytc_wzdx_v4.1.geojson"),
    "ok": ("Oklahoma", "ODOT (OK)", (33.6, -103.1, 37.1, -94.4),
           "https://oktraffic.org/api/Geojsons/workzones?access_token="
           "feOPynfHRJ5sdx8tf3IN5yOsGz89TAUuzHsN3V0jo1Fg41LcpoLhIRltaTPm"
           "DngD"),
    "hi": ("Hawaii", "HDOT", (18.5, -160.6, 22.6, -154.7),
           "https://ai.blyncsy.io/wzdx/hidot/feed"),
    "la": ("Louisiana", "Louisiana DOTD", (28.8, -94.1, 33.1, -88.7),
           "https://wzdx.e-dot.com/la_dot_d_feed_wzdx_v4.1.geojson"),
    "de": ("Delaware", "DelDOT", (38.4, -75.8, 39.9, -74.9),
           "https://wzdx.e-dot.com/del_dot_feed_wzdx_v4.1.geojson"),
    "txa": ("Texas (Austin)", "City of Austin", (30.0, -98.2, 30.7, -97.4),
            "https://data.austintexas.gov/download/d9mm-cjw9"),
    # The app_key below is published in the public FHWA registry entry
    # (FDOT's one.network WZDx distribution), not a private secret.
    "flw": ("Florida", "FDOT (WZDx)", (24.3, -87.7, 31.1, -79.8),
            "https://us-datacloud.one.network/fdot/feed.json?app_key="
            "c4090b04-26de-c9ee-873b2bd9a38c"),
}


# Per-feed marker caps where the default (2000) misfits: Austin is one
# metro whose permit feed would otherwise outweigh entire states.
WZDX_CAPS = {"txa": 400}


async def _fetch_wzdx(client, url: str, src: str, cap: int = 2000) -> dict:
    resp = await client.get(url, headers=UA, timeout=45.0)
    resp.raise_for_status()
    return {"markers": _parse_ia_wzdx(resp.json(), src, cap=cap)}


_TAG_RE = re.compile(r"<[^>]+>")


def _f_to_c(raw: str) -> float | None:
    m = re.match(r"(-?\d+)\s*F", raw or "")
    return round((int(m.group(1)) - 32) * 5 / 9, 1) if m else None


def _mph(raw: str) -> float | None:
    m = re.match(r"(\d+)\s*MPH", raw or "", re.IGNORECASE)
    return float(m.group(1)) if m else None


async def _fetch_md(client) -> dict:
    """Maryland CHART: live events, message signs, road weather."""
    base = "https://chartexp1.sha.maryland.gov/CHARTExportClientService"
    ev = (await client.get(f"{base}/getEventMapDataJSON.do", headers=UA,
                           timeout=30.0)).json().get("data") or []
    dms = (await client.get(f"{base}/getDMSMapDataJSON.do", headers=UA,
                            timeout=30.0)).json().get("data") or []
    wx = (await client.get(f"{base}/getRWISMapDataJSON.do", headers=UA,
                           timeout=30.0)).json().get("data") or []
    markers: list[dict] = []
    for e in ev:
        lat, lon = e.get("lat"), e.get("lon")
        if not lat or not lon or str(e.get("closed")).lower() == "true":
            continue
        markers.append({
            "kind": "incident", "lat": float(lat), "lon": float(lon),
            "type": e.get("incidentType") or "Incident",
            "location": (e.get("description") or "")[:160],
            "area": "", "src": "MDOT CHART",
            "dir": e.get("direction") or None, "reported": None,
        })
    for s in dms:
        lat, lon = s.get("lat"), s.get("lon")
        if not lat or not lon or (s.get("commMode") or "") != "ONLINE":
            continue
        # msgHTML arrives entity-ESCAPED (&lt;table&gt;...): unescape
        # first or the tag stripper sees no tags and popups render soup.
        raw = _html.unescape(_html.unescape(s.get("msgHTML") or ""))
        text = _TAG_RE.sub(" / ", raw).replace("\xa0", " ")
        lines = [ln.strip() for ln in text.split("/")
                 if ln.strip() and ln.strip() != "&"][:6]
        marker = {
            "kind": "sign", "lat": float(lat), "lon": float(lon),
            "route": None, "direction": None,
            "near": s.get("description") or "",
            "message": " / ".join(lines), "lines": lines,
            "src": "MDOT CHART",
        }
        if not lines:
            marker["blank"] = True
        markers.append(marker)
    for w in wx:
        lat, lon = w.get("lat"), w.get("lon")
        if not lat or not lon:
            continue
        markers.append({
            "kind": "rwis", "lat": float(lat), "lon": float(lon),
            "station": w.get("description") or "Weather station",
            "route": None, "src": "MDOT CHART",
            "air_c": _f_to_c(w.get("airTemp") or ""),
            "pave_c": _f_to_c(w.get("surfaceTemp") or ""),
            "wind": _mph(w.get("windSpeed") or ""),
            "gust": _mph(w.get("gustSpeed") or ""), "vis_m": None,
        })
    return {"markers": markers}


async def _fetch_il(client) -> dict:
    """Illinois TravelMidwest: incident and camera CSVs (attribution
    required; polled well within their reuse-policy caps)."""
    import csv
    import io
    inc_txt = (await client.get(
        "https://travelmidwest.com/lmiga/incidentInfo.csv",
        headers=UA, timeout=30.0)).text
    cam_txt = (await client.get(
        "https://travelmidwest.com/lmiga/cameraInfo.csv",
        headers=UA, timeout=30.0)).text
    markers: list[dict] = []
    for row in csv.DictReader(io.StringIO(inc_txt)):
        try:
            lat, lon = float(row.get("y") or 0), float(row.get("x") or 0)
        except ValueError:
            continue
        if not lat or not lon:
            continue
        where = _TAG_RE.sub("", row.get("Location") or "")[:160]
        markers.append({
            "kind": "incident", "lat": lat, "lon": lon,
            "type": row.get("Description") or "Incident",
            "location": where, "area": "", "src": "TravelMidwest (IDOT)",
            "dir": None, "reported": None,
            "detail": (row.get("ClosureDetails") or "")[:250] or None,
        })
    for row in csv.DictReader(io.StringIO(cam_txt)):
        snap = (row.get("SnapShot") or "").strip()
        try:
            lat, lon = float(row.get("y") or 0), float(row.get("x") or 0)
        except ValueError:
            continue
        if not lat or not lon or not snap.startswith("https://"):
            continue
        if str(row.get("TooOld")).strip().lower() == "true":
            continue
        markers.append({
            "kind": "camera", "lat": lat, "lon": lon,
            "name": row.get("CameraLocation") or "Camera",
            "route": None, "direction": row.get("CameraDirection") or None,
            "near": row.get("CameraLocation"),
            "src": "TravelMidwest (IDOT)", "image": snap, "stream": None,
        })
    return {"markers": markers}


async def _fetch_al(client) -> dict:
    """Alabama ALGO Traffic cameras (snapshots + camera pages)."""
    cams = (await client.get("https://api.algotraffic.com/v4.0/cameras",
                             headers=UA, timeout=30.0)).json()
    markers: list[dict] = []
    for c in cams or []:
        loc = c.get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        snap = c.get("snapshotImageUrl")
        if not lat or not lon or not snap:
            continue
        name = " ".join(x for x in (
            loc.get("displayRouteDesignator"),
            "at " + loc["displayCrossStreet"]
            if loc.get("displayCrossStreet") else None,
        ) if x) or "Camera"
        if loc.get("city"):
            name = f"{name}, {loc['city']}"
        markers.append({
            "kind": "camera", "lat": lat, "lon": lon,
            "name": name[:90],
            "route": loc.get("routeDesignator"),
            "direction": loc.get("direction"),
            "near": loc.get("city"),
            "src": "ALGO Traffic (ALDOT)",
            "image": snap, "stream": c.get("permLink"),
        })
    return {"markers": markers}


async def _fetch_mo_dms(client) -> dict:
    """Missouri message signs (keyless MoDOT feed)."""
    dms = (await client.get(
        "https://traveler.modot.org/timconfig/feed/desktop/MsgBrdV1.json",
        headers=UA, timeout=30.0)).json()
    markers: list[dict] = []
    for s in dms or []:
        try:
            lat, lon = float(s.get("y") or 0), float(s.get("x") or 0)
        except ValueError:
            continue
        if not lat or not lon:
            continue
        # The feed embeds literal <br /> tags between lines.
        lines = [ln.strip()
                 for ln in re.split(r"(?:<[^>]+>|[\n|])+", s.get("msg") or "")
                 if ln.strip() and re.search(r"[A-Za-z0-9]", ln)][:6]
        marker = {
            "kind": "sign", "lat": lat, "lon": lon,
            "route": None, "direction": None,
            "near": s.get("dev") or "Message sign",
            "message": " / ".join(lines), "lines": lines, "src": "MoDOT",
        }
        if not lines:
            marker["blank"] = True
        markers.append(marker)
    return {"markers": markers}


async def _fetch_mi(client) -> dict:
    """Michigan MiDrive (keyless MDOT JSON): incidents plus roadwork
    with real road geometry. Cameras carry no still URL and signs no
    message text in the list feeds, so those wait for detail-call
    support rather than shipping empty markers."""
    base = "https://mdotjboss.state.mi.us/MiDrive"
    inc = (await client.get(f"{base}/incidents/AllForMap/", headers=UA,
                            timeout=30.0)).json()
    con = (await client.get(f"{base}/construction/AllForMap/", headers=UA,
                            timeout=30.0)).json()
    markers: list[dict] = []
    for e in inc or []:
        lat, lon = e.get("latitude"), e.get("longitude")
        if not lat or not lon:
            continue
        text = re.sub(r"\s+", " ",
                      _TAG_RE.sub(" ", e.get("message") or "")).strip()
        markers.append({
            "kind": "incident", "lat": lat, "lon": lon,
            "type": e.get("title") or "Incident",
            "label": text[:220] or e.get("title") or "Incident",
            "src": "MDOT MiDrive",
        })
    for c in con or []:
        lat, lon = c.get("latitude"), c.get("longitude")
        if not lat or not lon:
            continue
        title = (c.get("title") or "Roadwork").strip()
        cls = ("full-roadway"
               if re.search(r"total closure|closed", title, re.I) else "lane")
        m = {"kind": "lane_closure", "lat": lat, "lon": lon, "cls": cls,
             "label": title, "src": "MDOT MiDrive"}
        pts = c.get("coordinatePoints") or []
        if isinstance(pts, list) and len(pts) > 1:
            step = max(1, len(pts) // 150)
            path = [[p[1], p[0]] for p in pts[::step]
                    if isinstance(p, list) and len(p) >= 2]
            if len(path) > 1:
                m["path"] = path
                m["end"] = path[-1]
        markers.append(m)
    return {"markers": markers}


async def _fetch_de_tmc(client) -> dict:
    """Delaware TMC (keyless DelDOT JSON): advisories (incidents and
    construction with coordinates), live message signs, and weather
    stations. Cameras are HLS streams with no still URL, so they wait
    for stream support."""
    base = "https://tmc.deldot.gov/json"
    adv = (await client.get(f"{base}/advisory.json", headers=UA,
                            timeout=30.0)).json().get("advisories") or []
    vms = (await client.get(f"{base}/vmsg-vms.json", headers=UA,
                            timeout=30.0)).json().get("signTypes") or []
    wx = (await client.get(f"{base}/weatherstation.json", headers=UA,
                           timeout=30.0)).json().get("stations") or []
    markers: list[dict] = []
    for a in adv:
        w = a.get("where") or {}
        lat, lon = w.get("lat"), w.get("lon")
        if not lat or not lon:
            continue
        typ = a.get("type") or {}
        name = typ.get("name") or "Advisory"
        loc = re.sub(r"\s+", " ", (w.get("location") or "")).strip()
        if (typ.get("code") or "").upper() == "C":
            markers.append({
                "kind": "lane_closure", "lat": lat, "lon": lon,
                "cls": "lane", "label": loc or name, "src": "DelDOT"})
        else:
            markers.append({
                "kind": "incident", "lat": lat, "lon": lon, "type": name,
                "label": loc or name, "src": "DelDOT"})
    for group in vms:
        for s in group.get("signs") or []:
            lat, lon = s.get("lat"), s.get("lon")
            if not lat or not lon:
                continue
            lines = [ln.strip()
                     for ln in re.split(r"<[^>]+>", s.get("message") or "")
                     if ln.strip() and re.search(r"[A-Za-z0-9]", ln)][:6]
            m = {"kind": "sign", "lat": lat, "lon": lon,
                 "route": None, "direction": None,
                 "near": s.get("title") or "Message sign",
                 "message": " / ".join(lines), "lines": lines,
                 "src": "DelDOT"}
            if not lines or not s.get("enable", True):
                m["blank"] = True
            markers.append(m)
    for s in wx:
        lat, lon = s.get("lat"), s.get("lon")
        if not lat or not lon:
            continue
        markers.append({
            "kind": "rwis", "lat": lat, "lon": lon,
            "name": s.get("title") or "Weather station", "src": "DelDOT"})
    return {"markers": markers}


TN_EVENTS_URL = (
    "https://spatial.tdot.tn.gov/ArcGIS/rest/services/Smartway/"
    "Smartway_Events/FeatureServer/0/query"
)


async def _fetch_tn(client) -> dict:
    """Tennessee SmartWay events from TDOT's keyless ArcGIS layer.
    Fields mirror WZDx closure details; date-window filtered the same
    way."""
    resp = await client.get(TN_EVENTS_URL, headers=UA, timeout=30.0, params={
        "where": "1=1",
        "outFields": "CD_EVENT_TYPE,CD_ROAD_NAMES,CD_DIRECTION,"
                     "VEHICLE_IMPACT,START_DATE,END_DATE",
        "returnGeometry": "true", "outSR": 4326, "f": "json",
    })
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise RuntimeError(f"TDOT: {payload['error']}")
    now_ms = time.time() * 1000
    markers: list[dict] = []
    for feat in payload.get("features") or []:
        geom, attrs = feat.get("geometry") or {}, feat.get("attributes") or {}
        lat, lon = geom.get("y"), geom.get("x")
        if not lat or not lon:
            continue
        start, end = attrs.get("START_DATE"), attrs.get("END_DATE")
        if isinstance(start, (int, float)) and start > now_ms:
            continue
        if isinstance(end, (int, float)) and end < now_ms:
            continue
        etype = (attrs.get("CD_EVENT_TYPE") or "").replace("-", " ").strip()
        road = (attrs.get("CD_ROAD_NAMES") or "").strip()
        direction = (attrs.get("CD_DIRECTION") or "").strip()
        impact = (attrs.get("VEHICLE_IMPACT") or "").lower()
        label = " ".join(x for x in (road, direction, etype or "roadwork")
                         if x)
        if re.search(r"incident|crash|obstruct|debris", etype, re.I):
            # "Hazard" prefix keeps the client's classifier honest for
            # obstruction and debris reports.
            typ = (f"Hazard - {etype}"
                   if re.search(r"obstruct|debris", etype, re.I) else etype)
            markers.append({
                "kind": "incident", "lat": lat, "lon": lon,
                "type": typ or "Incident", "label": label,
                "src": "TDOT SmartWay"})
        else:
            cls = ("full-roadway" if "all-lanes-closed" in impact
                   else "lane")
            markers.append({
                "kind": "lane_closure", "lat": lat, "lon": lon,
                "cls": cls, "label": label, "route": road or None,
                "src": "TDOT SmartWay"})
    return {"markers": markers}


async def _fetch_ms(client) -> dict:
    """Mississippi MDOT Traffic alerts (keyless WebMethod POST):
    construction and incident markers with human tooltips."""
    resp = await client.post(
        "https://www.mdottraffic.com/default.aspx/LoadAlertData",
        headers={**UA, "Content-Type": "application/json; charset=utf-8"},
        content="{}", timeout=30.0)
    resp.raise_for_status()
    markers: list[dict] = []
    for a in resp.json().get("d") or []:
        lat, lon = a.get("lat"), a.get("lon")
        if not lat or not lon:
            continue
        tip = re.sub(r"\s+", " ", (a.get("tooltip") or "")).strip()
        itype = (a.get("icontype") or "").lower()
        if "construction" in itype or "construction" in (
                a.get("markergroup") or ""):
            markers.append({
                "kind": "lane_closure", "lat": lat, "lon": lon,
                "cls": "lane", "label": tip or "Roadwork",
                "src": "MDOT Traffic (MS)"})
        else:
            markers.append({
                "kind": "incident", "lat": lat, "lon": lon,
                "type": itype.title() or "Incident",
                "label": tip or "Traffic alert",
                "src": "MDOT Traffic (MS)"})
    return {"markers": markers}


FL_BOUNDS = (24.3, -87.7, 31.1, -79.8)
FL_DIVAS_BASE = "https://gis.fdot.gov/arcgis/rest/services"


async def _fl_layer(client, service: str, cap: int = 6000) -> list[dict]:
    """One DIVAS FeatureServer layer, paged (server max is below the
    camera count)."""
    out: list[dict] = []
    for offset in range(0, cap, 2000):
        resp = await client.get(
            f"{FL_DIVAS_BASE}/{service}/FeatureServer/0/query",
            headers=UA, timeout=30.0, params={
                "where": "1=1", "outFields": "*", "returnGeometry": "true",
                "outSR": 4326, "f": "json",
                "resultRecordCount": 2000, "resultOffset": offset,
            })
        resp.raise_for_status()
        payload = resp.json()
        if "error" in payload:
            raise RuntimeError(f"DIVAS {service}: {payload['error']}")
        feats = payload.get("features") or []
        out.extend(feats)
        if len(feats) < 2000:
            break
    return out


async def _fetch_fl(client) -> dict:
    """Florida via FDOT's keyless DIVAS ArcGIS layers: the same live
    events FL511 shows, 4,900+ cameras with still images, and message
    boards. FL511's own API is agreement-gated; this is FDOT's public
    distribution of the same SunGuide data."""
    events, cams, dms = await asyncio.gather(
        _fl_layer(client, "DIVAS_GetEvent", cap=2000),
        _fl_layer(client, "DIVAS_Cameras"),
        _fl_layer(client, "DIVAS_MessageBoard", cap=2000))
    markers: list[dict] = []
    for f in events:
        geom, a = f.get("geometry") or {}, f.get("attributes") or {}
        lat, lon = geom.get("y"), geom.get("x")
        if not lat or not lon:
            continue
        if (a.get("status") or "").lower() == "resolved":
            continue
        desc = re.sub(r"\s+", " ", (a.get("descriptionen") or "")).strip()
        etype = (a.get("eventtypesae") or a.get("eventtypedesc")
                 or "").strip()
        lanes = (a.get("affectedlanes") or "").strip()
        if re.search(r"construction|road work|maintenance", etype, re.I):
            cls = ("full-roadway"
                   if re.search(r"all lanes|closed to traffic", lanes, re.I)
                   else "lane")
            markers.append({
                "kind": "lane_closure", "lat": lat, "lon": lon,
                "cls": cls, "label": (desc or etype)[:220],
                "route": a.get("highway"), "src": "FDOT"})
        else:
            markers.append({
                "kind": "incident", "lat": lat, "lon": lon,
                "type": etype or "Incident",
                "label": (desc or etype or "Incident")[:220],
                "src": "FDOT"})
    for f in cams:
        geom, a = f.get("geometry") or {}, f.get("attributes") or {}
        lat, lon = geom.get("y"), geom.get("x")
        url = (a.get("imagefilename") or "").strip()
        if not lat or not lon or not url.startswith("https://"):
            continue
        if (a.get("blockedimage") or "").lower() == "true":
            continue
        markers.append({
            "kind": "camera", "lat": lat, "lon": lon,
            "name": a.get("description") or a.get("highway"),
            "route": a.get("highway"), "direction": a.get("direction"),
            "near": a.get("description"), "image": url, "src": "FDOT"})
    for f in dms:
        geom, a = f.get("geometry") or {}, f.get("attributes") or {}
        lat, lon = geom.get("y"), geom.get("x")
        if not lat or not lon:
            continue
        lines = [ln.strip() for ln in
                 re.split(r"\n|<[^>]+>|\[nl\]|\[np\]",
                          a.get("message") or "")
                 if ln.strip() and re.search(r"[A-Za-z0-9]", ln)][:6]
        m = {"kind": "sign", "lat": lat, "lon": lon,
             "route": a.get("highway"), "direction": a.get("direction"),
             "near": a.get("description") or "Message sign",
             "message": " / ".join(lines), "lines": lines, "src": "FDOT"}
        if not lines:
            m["blank"] = True
        markers.append(m)
    return {"markers": markers}


WFIGS_QUERY_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Incident_Locations_Current/FeatureServer/0/query"
)
WFIGS_PERIM_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Interagency_Perimeters_YearToDate/FeatureServer/0/query"
)
US_BOUNDS = (18.0, -170.0, 72.0, -60.0)


def _norm_fire(name: str) -> str:
    """Same normalization the CA pipeline uses to join the incident and
    perimeter layers: drop a trailing 'Fire', keep alphanumerics."""
    cleaned = re.sub(r"\s+fire\s*$", "", (name or "").strip(), flags=re.I)
    return re.sub(r"[^A-Z0-9]", "", cleaned.upper())


def _ring_area(ring: list) -> float:
    """Signed shoelace area of a (lat, lon) ring in squared degrees.
    Sign encodes winding, which is how ArcGIS marks outer rings vs
    holes."""
    a = 0.0
    for i in range(len(ring)):
        y1, x1 = ring[i - 1]
        y2, x2 = ring[i]
        a += x1 * y2 - x2 * y1
    return a / 2


def fire_rings(rings: list, max_rings: int = 12,
               pts_per_ring: int = 120) -> list[list[list[float]]]:
    """Perimeter rings as a decimated MultiPolygon (list of rings of
    [lat, lon]).

    A large fire's perimeter arrives as MANY rings: separate burn
    lobes, spot fires, and unburned holes. Flattening them into one
    point list draws a single thread through all of them (the
    spaghetti-polygon bug), so each ring stays its own polygon.
    Hole rings (opposite winding from the biggest ring) are dropped:
    unburned islands are not worth double-drawn patches."""
    converted = []
    for ring in rings or []:
        pts = [(pt[1], pt[0]) for pt in ring
               if isinstance(pt, list) and len(pt) >= 2]
        if len(pts) >= 4:
            converted.append((pts, _ring_area(pts)))
    if not converted:
        return []
    converted.sort(key=lambda t: abs(t[1]), reverse=True)
    outer_sign = converted[0][1] >= 0
    out = []
    for pts, area in converted[:max_rings]:
        if (area >= 0) != outer_sign:
            continue
        step = max(1, len(pts) // pts_per_ring)
        dec = [[round(a, 4), round(b, 4)] for a, b in pts[::step]]
        if len(dec) >= 4:
            out.append(dec)
    return out


async def _fetch_us_fires(client) -> dict:
    """Active wildfires OUTSIDE California from the same national WFIGS
    layer the CA feed queries (CA fires keep their richer pipeline with
    CAL FIRE merge, so exclude them here to avoid duplicates). Mapped
    burn footprints join from the YearToDate perimeter layer by
    normalized name; fires without a perimeter record stay dots and the
    popup says so."""
    resp = await client.get(WFIGS_QUERY_URL, headers=UA, timeout=25.0, params={
        "where": "POOState<>'US-CA' AND IncidentTypeCategory='WF' "
                 "AND ActiveFireCandidate=1",
        "outFields": "IncidentName,IncidentSize,PercentContained,"
                     "FireDiscoveryDateTime",
        "returnGeometry": "true", "outSR": "4326", "f": "json",
    })
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise RuntimeError(f"WFIGS: {payload['error']}")
    markers: list[dict] = []
    for feat in payload.get("features") or []:
        geom, attrs = feat.get("geometry") or {}, feat.get("attributes") or {}
        lat, lon = geom.get("y"), geom.get("x")
        if not lat or not lon:
            continue
        disc = attrs.get("FireDiscoveryDateTime")
        markers.append({
            "kind": "wildfire", "lat": lat, "lon": lon,
            "name": attrs.get("IncidentName"),
            "acres": attrs.get("IncidentSize"),
            "contained": attrs.get("PercentContained"),
            "discovered": (datetime.fromtimestamp(disc / 1000).isoformat()
                           if isinstance(disc, (int, float)) else None),
            "src": "WFIGS",
        })
    with contextlib.suppress(Exception):
        # Perimeters refine the picture but never gate the dots. One
        # nationwide query, server-simplified (~200m) and decimated to
        # keep the cached mapdata payload phone-friendly.
        presp = await client.get(
            WFIGS_PERIM_URL, headers=UA, timeout=25.0, params={
                # Not-out fires only: YearToDate otherwise carries every
                # perimeter since January. Biggest first so the record
                # cap sheds the least visible footprints.
                "where": "attr_POOState<>'US-CA' "
                         "AND attr_FireOutDateTime IS NULL "
                         "AND attr_IncidentTypeCategory='WF'",
                "outFields": "poly_IncidentName",
                "orderByFields": "poly_GISAcres DESC",
                "resultRecordCount": 1000,
                "maxAllowableOffset": 0.002,
                "returnGeometry": "true", "outSR": "4326", "f": "json",
            })
        presp.raise_for_status()
        ppay = presp.json()
        if "error" in ppay:
            raise RuntimeError(f"WFIGS perimeters: {ppay['error']}")
        by_name: dict[str, list] = {}
        sizes: dict[str, int] = {}
        for feat in ppay.get("features") or []:
            attrs = feat.get("attributes") or {}
            key = _norm_fire(attrs.get("poly_IncidentName") or "")
            shaped = fire_rings((feat.get("geometry") or {}).get("rings"))
            n = sum(len(r) for r in shaped)
            # Keep the largest footprint when a name repeats
            # (YearToDate holds successive uploads).
            if key and shaped and n > sizes.get(key, 0):
                by_name[key] = shaped
                sizes[key] = n
        for m in markers:
            shaped = by_name.get(_norm_fire(m["name"] or ""))
            if shaped:
                m["poly"] = shaped
    return {"markers": markers}


KEYLESS_STATES = {
    # code: (display state, bounds, fetcher)
    "md": ("Maryland", MD_BOUNDS, _fetch_md),
    "il": ("Illinois", IL_BOUNDS, _fetch_il),
    "al": ("Alabama", AL_BOUNDS, _fetch_al),
    "mod": ("Missouri", MO_BOUNDS, _fetch_mo_dms),
    "mi": ("Michigan", MI_BOUNDS, _fetch_mi),
    "det": ("Delaware", DE_BOUNDS, _fetch_de_tmc),
    "tn": ("Tennessee", TN_BOUNDS, _fetch_tn),
    "ms": ("Mississippi", MS_BOUNDS, _fetch_ms),
    "fl": ("Florida", FL_BOUNDS, _fetch_fl),
    "usf": ("Nationwide", US_BOUNDS, _fetch_us_fires),
}


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

    lookups = []
    for code, (_net, _agency, bounds) in NEC_STATES.items():
        if not _overlaps(box, bounds):
            continue
        lookups.append(_cache.get(
            f"nec:{code}", TTL, MAX_SERVE,
            lambda c=code: _fetch_nec(client, c)))
        if "camera" in want:
            lookups.append(_cache.get(
                f"neccam:{code}", CAM_TTL, MAX_SERVE,
                lambda c=code: _fetch_nec_cameras(client, c)))
    for code, (_st, src, bounds, url) in WZDX_FEEDS.items():
        if _overlaps(box, bounds) and not _wzdx_superseded(code):
            cap = WZDX_CAPS.get(code, 2000)
            lookups.append(_cache.get(
                f"wzdx:{code}", WZDX_TTL, MAX_SERVE,
                lambda u=url, s=src, k=cap:
                _fetch_wzdx(client, u, s, cap=k)))
    for code, (_st, bounds, fetcher) in KEYLESS_STATES.items():
        if _overlaps(box, bounds):
            lookups.append(_cache.get(
                f"{code}:all", TTL, MAX_SERVE, lambda f=fetcher: f(client)))
    for code, (_name, bounds, fetcher, ready) in KEYED_STATES.items():
        if not ready() or not _overlaps(box, bounds):
            continue
        lookups.append(_cache.get(
            f"{code}:all", TTL, MAX_SERVE, lambda f=fetcher: f(client)))
    # A nationwide viewport touches every state at once; fetch them
    # concurrently so cold latency is the slowest feed, not the sum.
    for outcome in await asyncio.gather(*lookups, return_exceptions=True):
        if not isinstance(outcome, BaseException):
            await add(outcome)
    return out


async def prewarm(client) -> None:
    """Warm every expansion-state cache at boot (called in the background
    from the demo's prewarm), so the first nationwide map request lands
    on hot caches. Failures are fine; the request path retries."""
    with contextlib.suppress(Exception):
        lookups = [
            _cache.get(f"nec:{c}", TTL, MAX_SERVE,
                       lambda cc=c: _fetch_nec(client, cc))
            for c in NEC_STATES
        ]
        for code, (_n, _b, fetcher) in KEYLESS_STATES.items():
            lookups.append(_cache.get(f"{code}:all", TTL, MAX_SERVE,
                                      lambda f=fetcher: f(client)))
        for code, (_n, _b, fetcher, ready) in KEYED_STATES.items():
            if ready():
                lookups.append(_cache.get(f"{code}:all", TTL, MAX_SERVE,
                                          lambda f=fetcher: f(client)))
        await asyncio.gather(*lookups, return_exceptions=True)
        # WZDx feeds run up to 16 MB each; warm them in small batches so
        # concurrent JSON parses cannot spike the container's memory.
        codes = [c for c in WZDX_FEEDS if not _wzdx_superseded(c)]
        for i in range(0, len(codes), 3):
            batch = [(c, WZDX_CAPS.get(c, 2000)) for c in codes[i:i + 3]]
            await asyncio.gather(*[
                _cache.get(f"wzdx:{c}", WZDX_TTL, MAX_SERVE,
                           lambda u=WZDX_FEEDS[c][3], s=WZDX_FEEDS[c][1],
                           k=cap:
                           _fetch_wzdx(client, u, s, cap=k))
                for c, cap in batch
            ], return_exceptions=True)
        # Camera bundles are ~20 MB each; warm them after the light feeds.
        await asyncio.gather(*[
            _cache.get(f"neccam:{c}", CAM_TTL, MAX_SERVE,
                       lambda cc=c: _fetch_nec_cameras(client, cc))
            for c in NEC_STATES
        ], return_exceptions=True)


_STATE_NAMES = {"me": "Maine", "nh": "New Hampshire", "vt": "Vermont"}


def _status_entry(key: str, name: str, agency: str, state: str) -> dict:
    entry = _cache._entries.get(key)  # noqa: SLF001 - read-only peek
    return {
        "name": name, "agency": agency, "state": state,
        "on_demand": entry is None,
        **({"ok": True, "stale": False,
            "count": len(entry.value["markers"]),
            "as_of": entry.fetched_at.isoformat()} if entry else {}),
    }


def stat_counts() -> dict:
    """Marker counts across every cached expansion feed, for the topbar
    KPIs. Reads caches only; never triggers a fetch."""
    kinds = {"incident": 0, "lane_closure": 0, "chain_control": 0,
             "wildfire": 0, "camera": 0, "sign": 0}
    for entry in list(_cache._entries.values()):  # noqa: SLF001 - read-only peek
        try:
            for m in entry.value["markers"]:
                if m.get("kind") in kinds:
                    kinds[m["kind"]] += 1
        except Exception:  # noqa: BLE001 - stats never break the page
            continue
    return kinds


def coverage_summary() -> dict:
    """How many sources and states are live right now (topbar text)."""
    entries = source_status()
    states_set = {e["state"] for e in entries if e.get("state")
                  not in (None, "Nationwide")}
    states_set.update({"California", "Nevada"})
    return {"sources": len(entries) + 7,   # + the CA core feeds
            "states": len(states_set)}


def source_status() -> list[dict]:
    """Entries for /api/sources describing the expansion states, grouped
    per state. Reports cache state without forcing a fetch."""
    out = []
    for code, (_net, agency, _bounds) in NEC_STATES.items():
        out.append(_status_entry(
            f"nec:{code}", "All feeds (NE Compass)", agency,
            _STATE_NAMES[code]))
    for code, (st, src, _b, _u) in WZDX_FEEDS.items():
        if _wzdx_superseded(code):
            continue
        out.append(_status_entry(f"wzdx:{code}", "Roadwork (WZDx)", src, st))
    for code, (st, _b, _f) in KEYLESS_STATES.items():
        out.append(_status_entry(f"{code}:all", "Live feeds",
                                 {"md": "MDOT CHART",
                                  "il": "TravelMidwest (IDOT)",
                                  "al": "ALGO Traffic (ALDOT)",
                                  "mod": "MoDOT",
                                  "mi": "MDOT MiDrive",
                                  "det": "DelDOT TMC",
                                  "tn": "TDOT SmartWay",
                                  "ms": "MDOT Traffic (MS)",
                                  "fl": "FDOT DIVAS",
                                  "usf": "WFIGS wildfires"}[code], st))
    for code, (name, _bounds, _fetcher, ready) in KEYED_STATES.items():
        if not ready():
            out.append({"name": "All feeds", "agency": name, "state": name,
                        "enabled": False})
            continue
        agency = {"wa": "WSDOT", "or": "Oregon DOT (TripCheck)",
                  "oh": "OHGO", "utk": "UDOT", "azk": "ADOT",
                  "akk": "Alaska DOT&PF", "cok": "CDOT"}.get(code, name)
        out.append(_status_entry(f"{code}:all", "All feeds", agency, name))
    return out
