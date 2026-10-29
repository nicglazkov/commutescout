"""Nationwide trip tools: real routes, travel times by departure hour,
weather, and history, for any two US addresses.

The California corridor tools in server.py answer "what is on this
highway right now". These answer the questions people actually bring
to an assistant: "how is the drive to X", "when should I leave", "is
it going to rain when I get there", "is this stretch usually bad at
5". Each one gathers every source CommuteScout has for the trip and
returns it in one payload:

- the route itself from the same closure-aware planner the map and
  the apps use (Stadia Valhalla, full closures excluded, candidates
  ranked by what lies on them), with TomTom as a fallback router;
- drive times for any departure from TomTom's historical speed
  profiles, plus live traffic for departures in the next hour or so;
- everything live along the line: incidents, closures, chain
  controls, wildfires, message signs, cameras, road-weather stations
  and tolls, in every covered state, ordered by mile;
- National Weather Service alerts along the route and the hourly
  forecast at both ends, in local time;
- what usually happens on that road by hour, from the event archive.

Plugin markers are per-user and never come through here: the MCP
server has no user.

Every source is optional. A missing key, a spent daily budget or an
outage drops that section and says so in ``notes``; the rest of the
answer still arrives.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import os
import re
import time
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from ca_roads.budget import UPSTREAM
from ca_roads.feeds import nws as nws_feed
from ca_roads.feeds import tomtom as tomtom_feed
from ca_roads.geo import haversine_meters
from ca_roads.stadia import auth_headers
from ca_roads_mcp import account, snapshots
from ca_roads_mcp import history as hist
from ca_roads_mcp.geocode import geocode_candidates, stadia_suggest

MILES_PER_METER = 1 / 1609.344
STADIA_ROUTE_URL = "https://api.stadiamaps.com/route/v1"
MCP_STADIA_ROUTE_DAILY = int(os.environ.get("MCP_STADIA_ROUTE_DAILY", "300"))
PLAN_TTL_SECONDS = 300.0
_PLAN_CACHE_MAX = 200
_plan_cache: dict[tuple, tuple[float, dict]] = {}

# How close to the line each kind must be to count as "on the route".
NEAR_M = {"incident": 250, "lane_closure": 250, "chain_control": 400,
          "sign": 300, "camera": 300, "rwis": 2_000, "toll": 400,
          "wildfire": 16_000, "enforcement": 60}
CAPS = {"incident": 40, "lane_closure": 40, "chain_control": 20,
        "sign": 20, "camera": 12, "rwis": 10, "toll": 12, "wildfire": 10,
        "enforcement": 30}
SECTION = {"incident": "incidents", "lane_closure": "closures",
           "chain_control": "chain_controls", "wildfire": "wildfires_nearby",
           "sign": "message_signs", "camera": "cameras",
           "rwis": "road_weather", "toll": "tolls",
           "enforcement": "speed_and_red_light_cameras"}
MAX_TRIP_KM = 2_500
MAX_SLOTS = 16


# ── Small pure helpers ───────────────────────────────────────────────────────

def parse_coords(text: str | None) -> tuple[float, float] | None:
    if not text:
        return None
    try:
        lat_s, lon_s = text.split(",")
        lat, lon = float(lat_s), float(lon_s)
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def guess_zone(lat: float, lon: float) -> str:
    """A US time zone from position alone, for when the weather service
    cannot say. Coarse on purpose (state lines bend); the NWS answer
    wins whenever there is one."""
    if lon < -154:
        return "Pacific/Honolulu"
    if lat > 51 and lon < -129:
        return "America/Anchorage"
    if lat < 19 and lon > -68:
        return "America/Puerto_Rico"
    if lon < -114.0:
        return "America/Los_Angeles"
    if lon < -102.0:
        return "America/Phoenix" if lat < 37 and lon < -109 else "America/Denver"
    if lon < -86.5:
        return "America/Chicago"
    return "America/New_York"


def zone(name: str | None, lat: float, lon: float) -> ZoneInfo:
    for candidate in (name, guess_zone(lat, lon)):
        if not candidate:
            continue
        with contextlib.suppress(Exception):
            return ZoneInfo(candidate)
    return ZoneInfo("UTC")


def clock(dt: datetime) -> str:
    """"5:30 PM", portable (strftime's %-I is not)."""
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def day_label(d: date, today: date) -> str:
    if d == today:
        return "today"
    if d == today + timedelta(days=1):
        return "tomorrow"
    return d.strftime("%A %b ") + str(d.day)


def parse_hhmm(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    raw = text.strip().lower().replace(".", "")
    pm = raw.endswith("pm")
    am = raw.endswith("am")
    raw = raw.removesuffix("pm").removesuffix("am").strip()
    try:
        if ":" in raw:
            h_s, m_s = raw.split(":", 1)
            h, m = int(h_s), int(m_s)
        else:
            h, m = int(raw), 0
    except ValueError:
        return None
    if pm and h < 12:
        h += 12
    if am and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h, m


def parse_day(text: str | None, today: date) -> date | None:
    if not text or text.strip().lower() in ("today", "now"):
        return today
    t = text.strip().lower()
    if t == "tomorrow":
        return today + timedelta(days=1)
    names = ["monday", "tuesday", "wednesday", "thursday", "friday",
             "saturday", "sunday"]
    if t in names:
        ahead = (names.index(t) - today.weekday()) % 7
        return today + timedelta(days=ahead or 7)
    with contextlib.suppress(ValueError):
        return date.fromisoformat(t)
    return None


def parse_local(text: str | None, tz: ZoneInfo, now: datetime) -> datetime | None:
    """"now", "2026-10-30T08:00", "tomorrow 8am", "17:30" -> aware local
    datetime, or None if unreadable."""
    if not text or text.strip().lower() == "now":
        return now
    t = text.strip()
    with contextlib.suppress(ValueError):
        dt = datetime.fromisoformat(t)
        return dt.astimezone(tz) if dt.tzinfo else dt.replace(tzinfo=tz)
    parts = t.split()
    day = parse_day(parts[0], now.date()) if len(parts) > 1 else now.date()
    hm = parse_hhmm(parts[-1] if len(parts) > 1 else parts[0])
    if day is None or hm is None:
        return None
    dt = datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=tz)
    if len(parts) == 1 and dt < now - timedelta(minutes=5):
        dt += timedelta(days=1)  # "8am" said in the evening means tomorrow
    return dt


def cumulative_m(pts: list) -> list[float]:
    out = [0.0]
    for a, b in zip(pts, pts[1:], strict=False):
        out.append(out[-1] + haversine_meters(a[0], a[1], b[0], b[1]))
    return out


def _seg_m(lat: float, lon: float, a, b) -> float:
    kx = 111_320.0 * math.cos(math.radians(lat))
    ky = 111_320.0
    ax, ay = (a[1] - lon) * kx, (a[0] - lat) * ky
    bx, by = (b[1] - lon) * kx, (b[0] - lat) * ky
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)


CELL_DEG = 0.05  # about 5.5 km of latitude, 3.5 km of longitude up north


def line_index(pts: list) -> dict[tuple[int, int], list[int]]:
    """Grid cell -> indices of the segments passing through it, so each
    marker tests only the few segments near it. A 2,500 km route has
    tens of thousands of vertices and a wide box thousands of markers;
    scanning every vertex per marker would stall the event loop."""
    index: dict[tuple[int, int], list[int]] = {}
    for j in range(len(pts) - 1):
        (la0, lo0), (la1, lo1) = pts[j][:2], pts[j + 1][:2]
        steps = max(1, int(max(abs(la1 - la0), abs(lo1 - lo0)) / (CELL_DEG / 2)))
        seen = set()
        for s in range(steps + 1):
            f = s / steps
            cell = (math.floor((la0 + (la1 - la0) * f) / CELL_DEG),
                    math.floor((lo0 + (lo1 - lo0) * f) / CELL_DEG))
            if cell not in seen:
                seen.add(cell)
                index.setdefault(cell, []).append(j)
    return index


def locate_on_line(lat: float, lon: float, pts: list, cum: list[float],
                   near_m: float, index: dict | None = None) -> float | None:
    """Meters along the line to the closest approach, if the point is
    within ``near_m`` of it, else None."""
    if len(pts) < 2:
        return None
    if index is None:
        index = line_index(pts)
    ci, cj = math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG)
    k_lat = math.ceil(near_m / (CELL_DEG * 111_320))
    k_lon = math.ceil(near_m / (CELL_DEG * 111_320
                                * max(0.2, math.cos(math.radians(lat)))))
    best: tuple[float, int] | None = None
    tested: set[int] = set()
    for di in range(-k_lat, k_lat + 1):
        for dj in range(-k_lon, k_lon + 1):
            for j in index.get((ci + di, cj + dj), ()):
                if j in tested:
                    continue
                tested.add(j)
                d = _seg_m(lat, lon, pts[j], pts[j + 1])
                if d <= near_m and (best is None or d < best[0]):
                    best = (d, j)
    if best is None:
        return None
    return cum[best[1]]


def downsample(pts: list, keep: int = 150) -> list[list[float]]:
    if len(pts) <= keep:
        return [[round(p[0], 5), round(p[1], 5)] for p in pts]
    step = (len(pts) - 1) / (keep - 1)
    return [[round(pts[round(i * step)][0], 5), round(pts[round(i * step)][1], 5)]
            for i in range(keep)]


def sample(pts: list, fractions=(0.0, 0.25, 0.5, 0.75, 1.0)) -> list[tuple]:
    if not pts:
        return []
    return [tuple(pts[min(len(pts) - 1, round(f * (len(pts) - 1)))])
            for f in fractions]


def bbox(pts: list, pad: float = 0.1) -> tuple[float, float, float, float]:
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    return (max(-90.0, min(lats) - pad), max(-180.0, min(lons) - pad),
            min(90.0, max(lats) + pad), min(180.0, max(lons) + pad))


def via_roads(trip: dict, top: int = 4) -> list[str]:
    """The roads that carry most of a Valhalla trip, longest first."""
    length: dict[str, float] = {}
    for leg in trip.get("legs") or []:
        for man in leg.get("maneuvers") or []:
            names = man.get("street_names") or []
            if names:
                length[names[0]] = length.get(names[0], 0.0) + float(
                    man.get("length") or 0)
    return [n for n, _ in sorted(length.items(), key=lambda kv: -kv[1])[:top]]


def event_view(m: dict, mile: float | None) -> dict:
    """One live marker, trimmed to what a driver (or a model) reads."""
    kind = m.get("kind")
    out: dict = {"kind": kind}
    if kind == "plugin":  # only public OSM enforcement cameras get here
        out["kind"] = "enforcement_camera"
        out["type"] = {"CAMERA_SPEED": "speed camera",
                       "CAMERA_RED_LIGHT": "red light camera"}.get(
            m.get("flare_kind"), "traffic camera")
        out["source"] = "OpenStreetMap"
    if mile is not None:
        out["mile"] = round(mile, 1)
    for src, dst in (("type", "type"), ("label", "summary"), ("name", "name"),
                     ("location", "location"), ("message", "message"),
                     ("route", "route"), ("dir", "direction"),
                     ("direction", "direction"), ("cls", "closure_class"),
                     ("lanes", "lanes"), ("status", "level"),
                     ("delay_min", "delay_minutes"), ("acres", "acres"),
                     ("contained", "percent_contained"), ("station", "station"),
                     ("air_c", "air_c"), ("pave_c", "pavement_c"),
                     ("gust", "gust_mph"), ("vis_m", "visibility_m"),
                     ("price", "price"), ("min", "price_min"),
                     ("max", "price_max"), ("pricing", "pricing"),
                     ("image", "image_url"), ("reported", "reported"),
                     ("src", "source")):
        value = m.get(src)
        if value not in (None, "", []) and dst not in out:
            out[dst] = value
    if kind == "incident" and "summary" not in out:
        bits = [m.get("type"), m.get("location")]
        out["summary"] = ": ".join(b for b in bits if b)
    out["lat"] = round(float(m["lat"]), 5)
    out["lon"] = round(float(m["lon"]), 5)
    return out


def minutes(seconds) -> int | None:
    return round(seconds / 60) if isinstance(seconds, int | float) else None


# ── Resolution ───────────────────────────────────────────────────────────────

# Businesses named after the landmark they sit beside: "Radisson JFK
# Airport", "Park SFO", "Holiday Inn LAX International Airport". The
# geocoder's text match ranks them level with the landmark itself.
_LODGING = re.compile(
    r"\b(hotel|inn|suites?|motel|hostel|lodge|radisson|sheraton|marriott|"
    r"hilton|hyatt|embassy suites|homestead|crashpad|parking|park (sfo|lax|"
    r"jfk)|car service|transportation|shuttle|limo|rental|cell phone|"
    r"waiting lot)\b", re.I)
# A famous match this close to the user beats a nearer namesake: "SFO"
# typed in San Jose is the airport, not a San Jose shop called SFOcloud.
LANDMARK_KM = 150


def _tidy(label: str) -> str:
    """"Springfield, Springfield, MO, USA" -> "Springfield, MO, USA"."""
    parts: list[str] = []
    for p in label.split(", "):
        if not parts or p.lower() != parts[-1].lower():
            parts.append(p)
    return ", ".join(parts)


def _rows(rows: list[dict]) -> list[tuple[float, float, str]]:
    return [(r["lat"], r["lon"], _tidy(r["name"] + ", USA"))
            for r in rows if not r.get("approx")]  # approx: a bare street


async def place_candidates(client, query: str, near, limit: int = 5
                           ) -> list[tuple[float, float, str]]:
    """Best matches for a typed place, best first.

    Autocomplete leads: it weighs popularity, so "SFO", "JFK" and "Red
    Rocks Amphitheatre" land on the landmark where plain search finds a
    hotel or a street of the same name. With a bias point the unbiased
    answer is asked too, and wins when it is within LANDMARK_KM: the
    bias then only breaks ties for generic names ("Starbucks"). Full
    search fills in behind (house numbers, the offline gazetteer when
    the network is down). Hotels and parking lots named after a landmark
    sink unless the query asks for one.
    """
    size = max(limit, 6)
    if near:
        biased, plain = await asyncio.gather(
            stadia_suggest(client, query, near[0], near[1], limit=size),
            stadia_suggest(client, query, None, None, limit=size))
        out = _rows(biased)
        top = _rows(plain)[:1]
        if top and haversine_meters(near[0], near[1], top[0][0],
                                    top[0][1]) <= LANDMARK_KM * 1000:
            out = top + out
    else:
        out = _rows(await stadia_suggest(client, query, None, None, limit=size))
    for c in await geocode_candidates(client, query, limit=limit, near=near,
                                      scope="us"):
        out.append((c[0], c[1], _tidy(c[2])))
    deduped: list[tuple[float, float, str]] = []
    for c in out:
        if all(haversine_meters(c[0], c[1], d[0], d[1]) > 300 for d in deduped):
            deduped.append(c)
    if not _LODGING.search(query):
        deduped.sort(key=lambda c: 1 if _LODGING.search(c[2].split(",")[0]) else 0)
    return deduped[:limit]


def _name_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.split(",")[0].lower()).strip()


async def resolve(client, place: str | None, coords: str | None,
                  near: tuple[float, float] | None, which: str) -> dict:
    """{"lat","lon","name"} for one trip end, or {"error": ...} /
    {"needs_clarification": ...} the tool returns as is."""
    if coords:
        point = parse_coords(coords)
        if point is None:
            return {"error": f"{which}_coords must be 'lat,lon', "
                             "e.g. '40.7128,-74.0060'"}
        name = (place or "").strip()[:120] or coords
        return {"lat": point[0], "lon": point[1], "name": name}
    if not place or not place.strip():
        if which in ("origin", "place"):
            # "When should I leave for the airport?" names no start: the
            # account's Home is the natural one.
            saved, source = await account.places()
            home = next((s for s in saved if s.get("kind") == "home"), None)
            if home:
                found = await _from_saved(client, home)
                if "lat" in found:
                    found["defaulted_to_home"] = True
                return found
            hint = (account.CONNECT_HINT if source == "none" else
                    "No Home is saved on this account.")
            return {"error": f"give {which} (an address or place) or "
                             f"{which}_coords, or ask the user. {hint}"}
        return {"error": f"give {which} (an address or place) or {which}_coords"}
    if account.wants_here(place):
        return {"needs_location": True, "which": which, "error": account.HERE_HINT}
    saved, source = await account.places()
    hit = account.match(place, saved)
    if hit:
        return await _from_saved(client, hit)
    kind = account.mentions_saved_kind(place)
    if kind:
        hint = (account.CONNECT_HINT if source == "none" else
                f"No {kind.title()} is saved on this account; ask the user for "
                "the address.")
        return {"needs_saved_place": kind, "which": which,
                "error": f"'{place}' means the user's saved {kind}. {hint}"}
    cands = await place_candidates(client, place, near, limit=4)
    if not cands:
        return {"error": (f"could not find '{place}'. Ask for a fuller "
                          "address (street, city, state), or pass "
                          f"{which}_coords.")}
    # Ask only when far-apart places share the top match's name
    # (Springfield, MO or IL); a lookalike ("Stafford Market Place" for
    # "Pike Place Market") is the geocoder padding its list.
    spread = [c for c in cands[1:]
              if haversine_meters(c[0], c[1], cands[0][0], cands[0][1]) > 25_000
              and _name_key(c[2]) == _name_key(cands[0][2])]
    town = len(cands[0][2].split(", ")) <= 3  # "Springfield, MO, USA"
    if spread and town and "," not in place and near is None:
        return {
            "needs_clarification": True, "which": which,
            "options": [", ".join(c[2].split(", ")[:4]) for c in cands[:4]],
            "error": (f"'{place}' matches places far apart. Do not guess: "
                      "ask the user which one they meant, offering these."),
        }
    lat, lon, label = cands[0]
    out = {"lat": lat, "lon": lon, "name": ", ".join(label.split(", ")[:4])}
    if spread and "," not in place:
        # A venue name with namesakes elsewhere: the popular one leads,
        # and the rest are named so the answer can say which it used.
        out["other_matches"] = [", ".join(c[2].split(", ")[:4]) for c in spread]
    return out


async def _from_saved(client, saved: dict) -> dict:
    """A trip end from one of the caller's saved places."""
    kind = saved.get("kind") or "saved"
    label = (saved.get("name") or "").strip()
    title = {"home": "Home", "work": "Work"}.get(kind)
    name = (f"{title} ({label})" if title and label and label.lower() != kind
            else title or label or kind)
    out = {"name": name[:160], "saved_place": kind}
    if isinstance(saved.get("lat"), int | float):
        return {"lat": saved["lat"], "lon": saved["lon"], **out}
    value = saved.get("value") or ""
    point = parse_coords(value)
    if point is None:
        cands = await place_candidates(client, value, None, limit=1)
        if not cands:
            return {"error": f"the server's {kind} ('{value}') could not be found"}
        point = cands[0][:2]
    return {"lat": point[0], "lon": point[1], **out}


async def my_places() -> dict:
    """The caller's saved places, for get_my_places."""
    saved, source = await account.places()
    if source == "none":
        return {"connected": False, "places": [], "message": account.CONNECT_HINT}
    if source == "account_unavailable":
        return {"connected": True, "places": [],
                "error": "saved places are unavailable right now; try again"}
    rows = []
    for s in saved:
        if s.get("kind") == "recent" and sum(
                r["kind"] == "recent" for r in rows) >= 8:
            continue
        row = {"kind": s.get("kind"), "name": s.get("name") or s.get("kind")}
        if isinstance(s.get("lat"), int | float):
            row["coords"] = f"{s['lat']:.5f},{s['lon']:.5f}"
        else:
            row["address"] = s.get("value")
        rows.append(row)
    return {"connected": True, "source": source, "places": rows,
            "note": "Pass a place's name, 'home' or 'work' as origin or "
                    "destination, or its coords as *_coords."}


async def find_place(client, query: str, near: str | None = None,
                     limit: int = 5) -> dict:
    query = (query or "").strip()
    if not query or len(query) > 200:
        return {"error": "query must be 1 to 200 characters"}
    focus = parse_coords(near) if near else None
    if near and focus is None:
        return {"error": "near must be 'lat,lon'"}
    limit = max(1, min(int(limit), 8))
    cands = await place_candidates(client, query, focus, limit=limit)
    out = []
    for lat, lon, label in cands:
        entry = {"name": ", ".join(label.split(", ")[:5]),
                 "lat": round(lat, 6), "lon": round(lon, 6),
                 "coords": f"{lat:.5f},{lon:.5f}"}
        if focus:
            entry["miles_from_near"] = round(
                haversine_meters(*focus, lat, lon) * MILES_PER_METER, 1)
        out.append(entry)
    payload: dict = {"query": query, "count": len(out), "places": out}
    if not out:
        payload["message"] = ("No match in the United States. Ask for a "
                              "fuller address (street, city, state).")
    elif len(out) > 1 and not focus:
        payload["note"] = ("Several matches: if they are far apart, confirm "
                           "with the user which one they mean.")
    return payload


# ── Live markers ─────────────────────────────────────────────────────────────

async def live_markers(client, box, kinds: set[str]
                       ) -> tuple[list[dict], list[str]]:
    """Every live marker in ``box`` for the kinds asked, nationwide and
    California alike: from the map's published snapshot when it is
    fresh, else through the exact builder the map uses."""
    snap = await snapshots.markers(client, box, kinds)
    if snap is not None:
        return snap[0], []
    from ca_roads_demo.app import build_markers  # noqa: PLC0415 - heavy, lazy

    notes: list[str] = []
    try:
        markers, ready, total, degraded = await build_markers(
            box, kinds - {"plugin", "enforcement"}, feed_budget=12.0)
    except Exception:  # noqa: BLE001 - one bad feed must not sink a trip
        return [], ["live road events could not be loaded just now"]
    if degraded or (total and ready < total):
        notes.append("some state feeds were still loading; a few live "
                     "events may be missing")
    return markers, notes


# ── Routing ──────────────────────────────────────────────────────────────────

async def _stadia_plan(client, markers, origin, destination, preference):
    from ca_roads_demo import routing  # noqa: PLC0415

    key = os.environ.get("STADIA_API_KEY", "").strip()
    if not key or not UPSTREAM.allow("stadia-route-mcp", MCP_STADIA_ROUTE_DAILY):
        return None

    async def fetch(body: dict):
        try:
            resp = await client.post(
                STADIA_ROUTE_URL, json=body,
                headers=auth_headers(key, "commutescout.com MCP trip planner"),
                timeout=25.0)
        except Exception:  # noqa: BLE001
            return None
        return resp.json() if resp.status_code < 400 else None

    locations = [{"lat": round(origin[0], 6), "lon": round(origin[1], 6)},
                 {"lat": round(destination[0], 6), "lon": round(destination[1], 6)}]
    try:
        out = await routing.plan(fetch, markers, locations, preference)
    except Exception:  # noqa: BLE001
        return None
    return out if out.get("routes") else None


async def plan_trip(client, origin: str | None, destination: str | None,
                    origin_coords: str | None = None,
                    destination_coords: str | None = None,
                    depart_at: str | None = None,
                    preference: str = "fastest") -> dict:
    from ca_roads_demo import routing  # noqa: PLC0415

    if preference not in routing.PRESETS:
        return {"error": "preference must be one of "
                         + ", ".join(sorted(routing.PRESETS))}
    o = await resolve(client, origin, origin_coords, None, "origin")
    if "lat" not in o:
        return o
    d = await resolve(client, destination, destination_coords,
                      (o["lat"], o["lon"]), "destination")
    if "lat" not in d:
        return d
    a, b = (o["lat"], o["lon"]), (d["lat"], d["lon"])
    straight_km = haversine_meters(*a, *b) / 1000
    if straight_km > MAX_TRIP_KM:
        return {"error": f"that is a {straight_km:,.0f} km trip; plan it in "
                         f"legs under {MAX_TRIP_KM:,} km"}
    if straight_km < 0.2:
        return {"error": "origin and destination are the same place"}

    info_o, info_d = await asyncio.gather(
        nws_feed.point_info(client, *a), nws_feed.point_info(client, *b))
    tz_o = zone((info_o or {}).get("time_zone"), *a)
    tz_d = zone((info_d or {}).get("time_zone"), *b)
    now_local = datetime.now(UTC).astimezone(tz_o)
    leave = parse_local(depart_at, tz_o, now_local)
    if leave is None:
        return {"error": "depart_at must be 'now', an ISO time like "
                         "'2026-10-30T08:00', or 'tomorrow 8am'"}
    if leave < now_local - timedelta(minutes=5):
        return {"error": "depart_at is in the past"}
    leaving_now = abs((leave - now_local).total_seconds()) < 600

    ck = (round(a[0], 4), round(a[1], 4), round(b[0], 4), round(b[1], 4),
          preference, leave.replace(second=0, microsecond=0).isoformat()
          if not leaving_now else "now", o["name"], d["name"],
          # A trip from someone's saved place is cached for them alone.
          account.current_uid() if (o.get("saved_place") or d.get("saved_place"))
          else None)
    hit = _plan_cache.get(ck)
    if hit and time.monotonic() - hit[0] < PLAN_TTL_SECONDS:
        return hit[1]

    notes: list[str] = []
    corridor_box = bbox([a, b], pad=0.3)
    route_markers, mnotes = await live_markers(
        client, corridor_box, {"incident", "closure", "chain"})
    notes += mnotes
    planned, tt = await asyncio.gather(
        _stadia_plan(client, route_markers, a, b, preference),
        tomtom_feed.route_times(client, a, b,
                                None if leaving_now else leave.isoformat(
                                    timespec="seconds"),
                                with_points=True),
    )
    routes = []
    if planned:
        for r in planned["routes"]:
            trip = r["trip"]
            pts = routing._trip_points(trip)
            summ = trip.get("summary") or {}
            routes.append({
                "pts": pts,
                "distance_miles": round(float(summ.get("length") or 0), 1),
                "minutes_no_traffic": minutes(summ.get("time")),
                "via": via_roads(trip),
                "hassles": [h["label"] for h in r.get("hassles") or []],
                "hassle_minutes": r.get("penalty_min"),
            })
        if planned.get("excluded"):
            notes.append(f"the route avoids {planned['excluded']} point(s) "
                         "on fully closed roads")
        if planned.get("note"):
            notes.append(planned["note"])
    elif tt and tt.get("points"):
        s = routing.score(tt["points"], route_markers)
        routes.append({
            "pts": tt["points"],
            "distance_miles": round((tt.get("length_m") or 0) * MILES_PER_METER, 1),
            "minutes_no_traffic": minutes(tt.get("no_traffic_s")),
            "via": [], "hassles": [h["label"] for h in s["hassles"]],
            "hassle_minutes": s["penalty_min"],
        })
        notes.append("routed by TomTom (the closure-aware planner was "
                     "unavailable), so known full closures were not avoided")
    if not routes:
        return {"error": "no drivable route found between those places",
                "origin": o, "destination": d}

    best = routes[0]
    pts = best["pts"]
    cum = cumulative_m(pts)
    index = line_index(pts)
    line_box = bbox(pts, pad=0.2)
    everything, mnotes = await live_markers(
        client, line_box, {"incident", "closure", "chain", "fire", "sign",
                           "camera", "rwis", "toll", "enforcement"})
    notes += [n for n in mnotes if n not in notes]
    on_route: dict[str, list] = {}
    for m in everything:
        kind = m.get("kind")
        if kind == "plugin":
            kind = "enforcement" if snapshots.group_of(m) else None
        near = NEAR_M.get(kind)
        lat, lon = m.get("lat"), m.get("lon")
        if near is None or not isinstance(lat, int | float) or not isinstance(
                lon, int | float):
            continue
        along = locate_on_line(lat, lon, pts, cum, near, index)
        if along is None:
            continue
        on_route.setdefault(SECTION[kind], []).append(
            (along, event_view(m, along * MILES_PER_METER)))
    sections = {}
    for name, items in on_route.items():
        items.sort(key=lambda t: t[0])
        kind = next(k for k, v in SECTION.items() if v == name)
        sections[name] = [v for _, v in items[:CAPS[kind]]]
        if len(items) > CAPS[kind]:
            notes.append(f"{name}: showing the first {CAPS[kind]} of "
                         f"{len(items)} along the route")

    alerts, forecast_d = await asyncio.gather(
        nws_feed.alerts_at_points(client, sample(pts)),
        nws_feed.hourly_forecast(client, *b, hours=160),
    )

    traffic = None
    arrive = None
    if tt:
        travel = tt.get("travel_s")
        traffic = {
            "minutes_with_traffic": minutes(travel),
            "typical_minutes_for_this_departure": minutes(tt.get("historic_s")),
            "minutes_no_traffic": minutes(tt.get("no_traffic_s")),
            "traffic_delay_minutes": max(0, (minutes(travel) or 0)
                                         - (minutes(tt.get("no_traffic_s")) or 0)),
            "basis": ("live traffic plus typical patterns" if leaving_now
                      or (leave - now_local) < timedelta(hours=1)
                      else "typical traffic for that weekday and hour"),
        }
        if isinstance(travel, int | float):
            arrive = leave + timedelta(seconds=travel)
    else:
        notes.append("traffic-aware drive times are unavailable right now; "
                     "the time shown assumes no traffic")
    if arrive is None and best["minutes_no_traffic"] is not None:
        arrive = leave + timedelta(minutes=best["minutes_no_traffic"])

    weather: dict = {}
    if alerts:
        weather["alerts_along_route"] = alerts
    if arrive is not None and forecast_d:
        arrive_d = arrive.astimezone(tz_d)
        slot = _period_at(forecast_d, arrive_d)
        if slot:
            weather["at_destination_on_arrival"] = slot
    if not weather:
        weather["note"] = "no weather alerts along the route"

    summary = _trip_summary(o, d, best, traffic, sections, alerts, leave,
                            arrive, tz_d, now_local)
    result = {
        "summary": summary,
        "origin": o, "destination": d,
        "departure_local": leave.isoformat(timespec="minutes"),
        "arrival_local": (arrive.astimezone(tz_d).isoformat(timespec="minutes")
                          if arrive else None),
        "route": {k: v for k, v in best.items() if k != "pts"},
        "traffic": traffic,
        "on_route": sections,
        "weather": weather,
        "alternatives": [
            {k: v for k, v in r.items() if k != "pts"} for r in routes[1:]],
        "geometry": downsample(pts),
        "notes": notes,
        "data_as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        "verify": "Conditions change: check 511 or the state DOT before driving.",
    }
    if len(_plan_cache) >= _PLAN_CACHE_MAX:
        _plan_cache.pop(next(iter(_plan_cache)))
    _plan_cache[ck] = (time.monotonic(), result)
    return result


def _period_at(periods: list[dict], when: datetime) -> dict | None:
    """The hourly forecast period covering ``when``."""
    for p in periods:
        with contextlib.suppress(Exception):
            start = datetime.fromisoformat(p["start"])
            if start <= when < start + timedelta(hours=1):
                out = {k: v for k, v in p.items() if v is not None}
                hazard = nws_feed.driving_hazard(p)
                if hazard:
                    out["driving_hazard"] = hazard
                return out
    return None


def _trip_summary(o, d, best, traffic, sections, alerts, leave, arrive, tz_d,
                  now_local) -> str:
    when = ("now" if abs((leave - now_local).total_seconds()) < 600 else
            f"{day_label(leave.date(), now_local.date())} at {clock(leave)}")
    mins = (traffic or {}).get("minutes_with_traffic") or best["minutes_no_traffic"]
    bits = [f"{o['name']} to {d['name']}: {best['distance_miles']} mi"]
    if best["via"]:
        bits[0] += " via " + ", ".join(best["via"][:3])
    if mins is not None:
        hrs, mm = divmod(int(mins), 60)
        span = f"{hrs} h {mm} min" if hrs else f"{mm} min"
        bits.append(f"about {span} leaving {when}")
        if arrive:
            bits[-1] += f", arriving around {clock(arrive.astimezone(tz_d))}"
    delay = (traffic or {}).get("traffic_delay_minutes")
    if delay and delay >= 5:
        bits.append(f"{delay} min of that is traffic")
    counts = []
    for name, label in (("closures", "closure"), ("incidents", "incident"),
                        ("chain_controls", "chain control"),
                        ("wildfires_nearby", "wildfire nearby")):
        n = len(sections.get(name, []))
        if n:
            counts.append(f"{n} {label}{'s' if n != 1 and label != 'wildfire nearby' else ''}")
    bits.append(("on the route right now: " + ", ".join(counts))
                if counts else "nothing reported on the route right now")
    if alerts:
        bits.append("weather alerts: " + ", ".join(
            sorted({a.get("event") or "alert" for a in alerts})))
    return "; ".join(bits) + "."


# ── Best time to go ──────────────────────────────────────────────────────────

async def best_time_to_go(client, origin: str | None, destination: str | None,
                          origin_coords: str | None = None,
                          destination_coords: str | None = None,
                          day: str | None = None, earliest: str | None = None,
                          latest: str | None = None,
                          arrive_by: str | None = None,
                          step_minutes: int | None = None,
                          ctx=None) -> dict:
    o = await resolve(client, origin, origin_coords, None, "origin")
    if "lat" not in o:
        return o
    d = await resolve(client, destination, destination_coords,
                      (o["lat"], o["lon"]), "destination")
    if "lat" not in d:
        return d
    a, b = (o["lat"], o["lon"]), (d["lat"], d["lon"])
    if haversine_meters(*a, *b) / 1000 > MAX_TRIP_KM:
        return {"error": f"plan trips over {MAX_TRIP_KM:,} km in legs"}
    if not tomtom_feed.api_key():
        return {"error": "time-of-day drive times are not configured on "
                         "this server"}

    info_o, info_d = await asyncio.gather(
        nws_feed.point_info(client, *a), nws_feed.point_info(client, *b))
    tz_o = zone((info_o or {}).get("time_zone"), *a)
    tz_d = zone((info_d or {}).get("time_zone"), *b)
    now = datetime.now(UTC).astimezone(tz_o)

    target_by: datetime | None = None
    if arrive_by:
        target_by = parse_local(arrive_by, tz_d, now.astimezone(tz_d))
        if target_by is None:
            return {"error": "arrive_by must be a time like '9:00', "
                             "'tomorrow 9am' or '2026-10-30T09:00'"}
        if target_by <= now:
            return {"error": "arrive_by is in the past"}
    the_day = parse_day(day, now.date())
    if the_day is None:
        return {"error": "day must be 'today', 'tomorrow', a weekday name or "
                         "YYYY-MM-DD"}
    if target_by is not None:
        the_day = target_by.astimezone(tz_o).date()
    if the_day > now.date() + timedelta(days=60):
        return {"error": "pick a day within the next 60 days"}

    e_hm = parse_hhmm(earliest) or (6, 0)
    l_hm = parse_hhmm(latest) or (21, 0)
    start = datetime(the_day.year, the_day.month, the_day.day, *e_hm, tzinfo=tz_o)
    end = datetime(the_day.year, the_day.month, the_day.day, *l_hm, tzinfo=tz_o)
    notes: list[str] = []

    # A probe at the free-flow hour sizes the drive (and fetches the
    # route line for history) before the sweep picks its slots.
    probe = await tomtom_feed.route_times(
        client, a, b, None, with_points=True)
    if not probe:
        return {"error": "drive times are unavailable right now (the "
                         "traffic provider did not answer, or today's "
                         "budget is spent); try again later"}
    base_s = probe.get("no_traffic_s") or probe.get("travel_s") or 0

    if target_by is not None:
        latest_leave = target_by.astimezone(tz_o) - timedelta(seconds=base_s)
        start = latest_leave - timedelta(seconds=max(1800, base_s * 1.2))
        end = latest_leave
    if day is None and target_by is None and end <= now + timedelta(minutes=30):
        start += timedelta(days=1)
        end += timedelta(days=1)
        notes.append("today's window has passed, so this looks at tomorrow")
    if end <= start:
        return {"error": "latest must be after earliest"}
    start = max(start, now + timedelta(minutes=2))
    if end <= start:
        return {"error": "that window is already over; pick a later day"}

    span_min = (end - start).total_seconds() / 60
    step = int(step_minutes) if step_minutes else 0
    if step <= 0:
        step = max(15, math.ceil(span_min / (MAX_SLOTS - 1) / 15) * 15)
    step = max(10, step)
    slots: list[datetime] = []
    t = start
    if t.minute % 5:
        t += timedelta(minutes=5 - t.minute % 5)
    t = t.replace(second=0, microsecond=0)
    while t <= end and len(slots) < MAX_SLOTS:
        slots.append(t)
        t += timedelta(minutes=step)
    if len(slots) == MAX_SLOTS and t <= end:
        notes.append(f"checked {MAX_SLOTS} departures; narrow earliest/latest "
                     "for a finer sweep")

    # TomTom's free tier takes a few requests a second: three at a time,
    # each holding its seat a moment, keeps a sweep under that.
    sem = asyncio.Semaphore(3)
    done = 0

    async def one(slot: datetime):
        nonlocal done
        async with sem:
            r = await tomtom_feed.route_times(
                client, a, b, slot.isoformat(timespec="seconds"))
            await asyncio.sleep(0.35)
        done += 1
        if ctx is not None:
            with contextlib.suppress(Exception):
                await ctx.report_progress(done, len(slots),
                                          f"checked {done} of {len(slots)}")
        return slot, r

    pts = probe.get("points") or [a, b]
    results, forecast_d, forecast_o, history = await asyncio.gather(
        asyncio.gather(*(one(s) for s in slots)),
        nws_feed.hourly_forecast(client, *b, hours=160),
        nws_feed.hourly_forecast(client, *a, hours=160),
        hist.history(pts, 300.0, 90, tz_o.key),
    )

    rows = []
    for slot, r in results:
        if not r or not isinstance(r.get("travel_s"), int | float):
            continue
        arrive = slot + timedelta(seconds=r["travel_s"])
        row = {
            "leave": clock(slot),
            "leave_local": slot.isoformat(timespec="minutes"),
            "arrive": clock(arrive.astimezone(tz_d)),
            "minutes": minutes(r["travel_s"]),
            "traffic_minutes": max(0, minutes(r["travel_s"])
                                   - (minutes(r.get("no_traffic_s"))
                                      or minutes(r["travel_s"]))),
        }
        wx = _period_at(forecast_d, arrive.astimezone(tz_d)) or _period_at(
            forecast_o, slot)
        if wx:
            row["weather"] = {k: wx[k] for k in ("forecast", "temp_f",
                                                 "precip_pct", "driving_hazard")
                              if k in wx}
        if history.get("available"):
            weekend = slot.weekday() >= 5
            rates = history["weekend_rate_by_hour" if weekend
                            else "weekday_rate_by_hour"]
            row["usual_incidents_that_hour"] = rates[slot.hour]
        rows.append(row)
    if target_by is not None:
        rows = [r for r in rows
                if datetime.fromisoformat(r["leave_local"])
                + timedelta(minutes=r["minutes"] + 5)
                <= target_by.astimezone(tz_o)]
        if not rows:
            return {"error": "no departure in the window arrives in time; "
                             "allow an earlier start",
                    "free_flow_minutes": minutes(base_s)}
    if not rows:
        return {"error": "drive times are unavailable right now; try again "
                         "later", "origin": o, "destination": d}

    def severe(r):
        hz = (r.get("weather") or {}).get("driving_hazard")
        return hz in ("blizzard", "freezing", "ice", "sleet", "snow")

    fastest = min(rows, key=lambda r: r["minutes"])
    candidates = [r for r in rows if not severe(r)] or rows
    if target_by is not None:
        # Latest departure that still arrives on time with a margin.
        best = max(candidates, key=lambda r: r["leave_local"])
    else:
        best = min(candidates, key=lambda r: (r["minutes"],
                                              r.get("usual_incidents_that_hour", 0)))
    worst = max(rows, key=lambda r: r["minutes"])
    good = [r["leave"] for r in rows if r["minutes"] <= best["minutes"] * 1.08]
    avoid = [r["leave"] for r in rows if r["minutes"] >= fastest["minutes"] * 1.25]

    when = day_label(datetime.fromisoformat(best["leave_local"]).date(), now.date())
    summary = (f"Best time to leave {when}: {best['leave']} (about "
               f"{best['minutes']} min, arriving {best['arrive']}).")
    if worst["minutes"] - best["minutes"] >= 5:
        summary += (f" Worst: {worst['leave']} at about {worst['minutes']} "
                    "min.")
    if avoid:
        summary += " Traffic is heaviest leaving " + _ranges(avoid, rows) + "."
    if severe(best) or any(severe(r) for r in rows):
        summary += " Snow or ice is in the forecast for part of the window."
    if target_by is not None:
        summary = (f"To arrive by {clock(target_by)}, leave by {best['leave']} "
                   f"(about {best['minutes']} min).")

    out = {
        "summary": summary,
        "origin": o, "destination": d,
        "time_zone": tz_o.key,
        "recommended": best,
        "fastest": fastest,
        "slowest": worst,
        "good_departures": good,
        "departures": rows,
        "free_flow_minutes": minutes(base_s),
        "distance_miles": round((probe.get("length_m") or 0) * MILES_PER_METER, 1),
        "basis": ("TomTom drive times from historical speed profiles for that "
                  "weekday and hour (live traffic too for the next hour), NWS "
                  "hourly forecast, and incident history along the route"),
        "notes": notes,
    }
    if history.get("available"):
        out["route_history"] = {
            k: history[k] for k in ("window_days", "since", "incidents",
                                    "incidents_per_week", "busiest_hours",
                                    "common_incident_types",
                                    "median_incident_minutes")}
    else:
        notes.append("incident history: " + history.get("reason", "unavailable"))
    return out


def _ranges(labels: list[str], rows: list[dict]) -> str:
    """"7:30 AM to 9:00 AM and 4:30 PM to 6:00 PM" from slot labels."""
    order = [r["leave"] for r in rows]
    idx = sorted(order.index(x) for x in labels)
    groups: list[list[int]] = []
    for i in idx:
        if groups and i == groups[-1][-1] + 1:
            groups[-1].append(i)
        else:
            groups.append([i])
    parts = [order[g[0]] if len(g) == 1 else f"{order[g[0]]} to {order[g[-1]]}"
             for g in groups]
    return " and ".join(parts[:3])


# ── Weather, history, traffic, coverage ──────────────────────────────────────

async def point_from(client, place: str | None, center: str | None) -> dict:
    if center:
        p = parse_coords(center)
        if p is None:
            return {"error": "center must be 'lat,lon'"}
        return {"lat": p[0], "lon": p[1], "name": place or center}
    return await resolve(client, place, None, None, "place")


async def get_weather(client, place: str | None = None,
                      center: str | None = None, hours: int = 24) -> dict:
    p = await point_from(client, place, center)
    if "lat" not in p:
        return p
    hours = max(1, min(int(hours), 156))
    lat, lon = p["lat"], p["lon"]
    info, periods, alerts, (markers, _) = await asyncio.gather(
        nws_feed.point_info(client, lat, lon),
        nws_feed.hourly_forecast(client, lat, lon, hours=hours),
        nws_feed.alerts_at_points(client, [(lat, lon)]),
        live_markers(client, (lat - 0.3, lon - 0.4, lat + 0.3, lon + 0.4), {"rwis"}),
    )
    stations = sorted(
        ((haversine_meters(lat, lon, m["lat"], m["lon"]), m) for m in markers
         if m.get("kind") == "rwis"), key=lambda t: t[0])[:5]
    hazards = [(q["start"], nws_feed.driving_hazard(q)) for q in periods]
    hazards = [(s, h) for s, h in hazards if h]
    out = {
        "place": p,
        "time_zone": (info or {}).get("time_zone") or guess_zone(lat, lon),
        "forecast_office_place": (info or {}).get("place"),
        "alerts": alerts,
        "hourly": periods,
        "road_weather_stations": [
            {**event_view(m, None),
             "miles_away": round(dist * MILES_PER_METER, 1)}
            for dist, m in stations],
        "source": "National Weather Service (api.weather.gov); road weather "
                  "from state DOT stations",
    }
    if hazards:
        out["driving_hazards"] = [{"start": s, "hazard": h} for s, h in hazards[:12]]
    if not periods:
        out["note"] = "no NWS forecast for this point (outside NWS coverage, " \
                      "or the service is down)"
    return out


async def get_area_history(client, place: str | None = None,
                           center: str | None = None, radius_km: float = 3.0,
                           days: int = 90) -> dict:
    p = await point_from(client, place, center)
    if "lat" not in p:
        return p
    radius_km = max(0.2, min(float(radius_km), 25.0))
    info = await nws_feed.point_info(client, p["lat"], p["lon"])
    tz = zone((info or {}).get("time_zone"), p["lat"], p["lon"])
    h = await hist.history([(p["lat"], p["lon"])], radius_km * 1000, days, tz.key)
    return {"place": p, "radius_km": radius_km, "time_zone": tz.key, **h,
            "note": ("Counts are incidents and closures CommuteScout saw "
                     "start inside the circle, by local hour. Coverage "
                     "follows each state's feeds; history began 2026-07-12.")}


async def get_traffic(client, points: str | None = None, place: str | None = None,
                      center: str | None = None) -> dict:
    pairs: list[tuple[float, float]] = []
    if points:
        for chunk in points.split("|")[:10]:
            p = parse_coords(chunk)
            if p is None:
                return {"error": f"bad point '{chunk}': use 'lat,lon|lat,lon'"}
            pairs.append(p)
    else:
        p = await point_from(client, place, center)
        if "lat" not in p:
            return p
        pairs = [(p["lat"], p["lon"])]
    if not tomtom_feed.api_key():
        return {"error": "live traffic speeds are not configured on this server"}
    samples = await asyncio.gather(*(tomtom_feed.flow_at_point(client, *q)
                                     for q in pairs))
    out = []
    for q, s in zip(pairs, samples, strict=True):
        row = {"point": f"{q[0]:.5f},{q[1]:.5f}"}
        if s and s.get("current_mph") and s.get("freeflow_mph"):
            ratio = s["current_mph"] / s["freeflow_mph"]
            row.update(current_mph=s["current_mph"], freeflow_mph=s["freeflow_mph"],
                       percent_of_freeflow=round(ratio * 100),
                       condition=("closed" if s.get("closed") else
                                  "free-flowing" if ratio > 0.85 else
                                  "slow" if ratio > 0.55 else "heavy"))
        else:
            row["condition"] = "no reading"
        out.append(row)
    return {"readings": out, "source": "TomTom traffic flow (nearest road "
            "segment to each point)",
            "data_as_of": datetime.now(UTC).isoformat(timespec="seconds")}


def get_coverage() -> dict:
    from ca_roads_demo import states  # noqa: PLC0415

    entries = states.source_status()
    by_state: dict[str, list[str]] = {}
    for e in entries:
        st = e.get("state")
        if not st or e.get("enabled") is False:
            continue
        by_state.setdefault(st, []).append(
            f"{e.get('agency')}: {e.get('name')}"
            + (" (stale)" if e.get("stale") else ""))
    california = ["CHP incidents (with dispatch logs)", "Caltrans lane closures",
                  "Caltrans chain controls", "Caltrans cameras and message signs",
                  "Caltrans road weather", "511 SF Bay events and tolls",
                  "CAL FIRE and WFIGS wildfires"]
    by_state.setdefault("California", []).extend(california)
    by_state.setdefault("Nevada", []).append("NDOT (nvroads)")
    return {
        "states_covered": len([s for s in by_state if s != "Nationwide"]),
        "summary": states.coverage_summary(),
        "by_state": dict(sorted(by_state.items())),
        "nationwide": ["NWS weather alerts and hourly forecasts",
                       "WFIGS wildfires and perimeters", "USGS earthquakes",
                       "TomTom traffic flow and time-of-day drive times",
                       "Stadia Maps routing and geocoding",
                       "CommuteScout event history (since 2026-07-12)"],
        "note": "States publish different things: some publish roadwork "
                "only, so a quiet answer there can be normal.",
    }
