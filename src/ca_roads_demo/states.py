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


async def _fetch_wa(client) -> dict:
    key = _wa_key()
    base = "https://wsdot.wa.gov/Traffic/api"
    alerts, cams, passes = [
        (await client.get(u, headers=UA, timeout=30.0)).json()
        for u in (
            f"{base}/HighwayAlerts/HighwayAlertsREST.svc/GetAlertsAsJson?AccessCode={key}",
            f"{base}/HighwayCameras/HighwayCamerasREST.svc/GetCamerasAsJson?AccessCode={key}",
            f"{base}/MountainPassConditions/MountainPassConditionsREST.svc/GetMountainPassConditionsAsJson?AccessCode={key}",
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
            markers.append({
                "kind": "incident", "lat": lat, "lon": lon,
                "type": "Incident", "location": where or headline[:120],
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
                markers.append({
                    "kind": "lane_closure", "lat": lat, "lon": lon,
                    "label": desc, "cls": "full-roadway"
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


KEYED_STATES = {
    # code: (display state, bounds, fetcher, ready-check)
    "wa": ("Washington", WA_BOUNDS, _fetch_wa, _wa_key),
    "or": ("Oregon", OR_BOUNDS, _fetch_or, _or_key),
    "oh": ("Ohio", OH_BOUNDS, _fetch_oh, _oh_key),
}


# ── Wave 3: the WZDx registry + remaining keyless states ─────────────
# One WZDx parser covers roadwork/closures in a dozen states; feeds
# listed here are keyless (verified live 2026-07-19).

MD_BOUNDS = (37.9, -79.5, 39.8, -74.9)
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
}


async def _fetch_wzdx(client, url: str, src: str) -> dict:
    resp = await client.get(url, headers=UA, timeout=45.0)
    resp.raise_for_status()
    return {"markers": _parse_ia_wzdx(resp.json(), src)}


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
        text = _TAG_RE.sub(" / ", s.get("msgHTML") or "")
        lines = [ln.strip() for ln in text.split("/") if ln.strip()][:6]
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
        lines = [ln.strip() for ln in re.split(r"[\n|]+", s.get("msg") or "")
                 if ln.strip()][:6]
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


KEYLESS_STATES = {
    # code: (display state, bounds, fetcher)
    "md": ("Maryland", MD_BOUNDS, _fetch_md),
    "il": ("Illinois", IL_BOUNDS, _fetch_il),
    "al": ("Alabama", AL_BOUNDS, _fetch_al),
    "mod": ("Missouri", MO_BOUNDS, _fetch_mo_dms),
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
        if _overlaps(box, bounds):
            lookups.append(_cache.get(
                f"wzdx:{code}", WZDX_TTL, MAX_SERVE,
                lambda u=url, s=src: _fetch_wzdx(client, u, s)))
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
        codes = list(WZDX_FEEDS)
        for i in range(0, len(codes), 3):
            await asyncio.gather(*[
                _cache.get(f"wzdx:{c}", WZDX_TTL, MAX_SERVE,
                           lambda u=WZDX_FEEDS[c][3], s=WZDX_FEEDS[c][1]:
                           _fetch_wzdx(client, u, s))
                for c in codes[i:i + 3]
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


def source_status() -> list[dict]:
    """Entries for /api/sources describing the expansion states, grouped
    per state. Reports cache state without forcing a fetch."""
    out = []
    for code, (_net, agency, _bounds) in NEC_STATES.items():
        out.append(_status_entry(
            f"nec:{code}", "All feeds (NE Compass)", agency,
            _STATE_NAMES[code]))
    for code, (st, src, _b, _u) in WZDX_FEEDS.items():
        out.append(_status_entry(f"wzdx:{code}", "Roadwork (WZDx)", src, st))
    for code, (st, _b, _f) in KEYLESS_STATES.items():
        out.append(_status_entry(f"{code}:all", "Live feeds",
                                 {"md": "MDOT CHART",
                                  "il": "TravelMidwest (IDOT)",
                                  "al": "ALGO Traffic (ALDOT)",
                                  "mod": "MoDOT"}[code], st))
    for code, (name, _bounds, _fetcher, ready) in KEYED_STATES.items():
        if not ready():
            out.append({"name": "All feeds", "agency": name, "state": name,
                        "enabled": False})
            continue
        agency = {"wa": "WSDOT", "or": "Oregon DOT (TripCheck)",
                  "oh": "OHGO"}[code]
        out.append(_status_entry(f"{code}:all", "All feeds", agency, name))
    return out
