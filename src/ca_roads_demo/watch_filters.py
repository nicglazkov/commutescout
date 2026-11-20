"""What a watch area alerts about, at three depths.

1. Kinds: incidents, closures, chain controls, wildfires, weather alerts.
   A watch with only ``kinds`` (every watch made before this module)
   gets every event of those kinds, exactly as before.
2. Report types: one normalized taxonomy per kind ("Crashes", "Full
   closures", "R-2", "Winter storms, snow and ice"), the same words in
   every state, so "only crashes" means the same thing in Ohio and in
   California.
3. Source types: the words a source itself uses ("1182-Trfc
   Collision-No Inj" from CHP, a state's own incident categories, the
   National Weather Service's product names), for people who want one
   exact report and nothing else.

A watch stores its choice as an optional ``filters`` map, kind ->
{"subtypes": [...], "raw": ["<source>|<source type>", ...]}. A kind
with no entry means everything of that kind. An event passes a filtered
kind when its report type is picked, or its exact source type is.

Which report and source types a person is offered depends on where the
shape is: ``area_options`` works out the states the shape touches and
lists only what their sources provide. California's sources are known
up front; every other state's own categories are learned from the live
feeds by ``observe`` (the watch checker calls it every cycle) and kept,
so the list fills in with what those agencies actually publish.
"""

from __future__ import annotations

import math
import re
import time

# ---------------------------------------------------------------- kinds

# (id, label, hint). The order is the order the pages list them in.
KINDS: tuple[tuple[str, str, str], ...] = (
    ("incident", "Incidents", "Crashes, hazards, stalled vehicles and other reports"),
    ("closure", "Closures", "Full and lane closures, ramps and roadwork"),
    ("chain", "Chain controls", "Chain and traction requirements"),
    ("fire", "Wildfires", "Fires reported by wildfire agencies"),
    ("weather", "Weather alerts", "National Weather Service warnings and advisories"),
)
KIND_IDS: tuple[str, ...] = tuple(k for k, _, _ in KINDS)

# ---------------------------------------------------------------- report types

# kind -> ordered (id, label). Every kind with report types ends in a
# catch-all, so nothing a source reports is ever unreachable.
SUBTYPES: dict[str, tuple[tuple[str, str], ...]] = {
    "incident": (
        ("crash", "Crashes"),
        ("stall", "Stalled vehicles"),
        ("hazard", "Hazards and debris"),
        ("vehicle_fire", "Vehicle and roadside fires"),
        ("conditions", "Weather and road conditions"),
        ("closed", "Road closures and SigAlerts"),
        ("police", "Police activity and escorts"),
        ("work", "Roadwork and maintenance"),
        ("advisory", "Traffic advisories and events"),
        ("other", "Other reports"),
    ),
    "closure": (
        ("full", "Full closures"),
        ("lanes", "Lane closures"),
        ("moving", "Moving work and traffic breaks"),
        ("ramp", "Ramp and connector closures"),
        ("other", "Other closures"),
    ),
    "chain": (
        ("r1", "R-1: chains, or snow tires on cars and light trucks"),
        ("r2", "R-2: chains unless 4WD with snow tires"),
        ("r3", "R-3: chains on every vehicle"),
        ("trucks", "Truck chain requirements"),
        ("closed", "Closed at a chain checkpoint"),
        ("advisory", "Traction advisories"),
    ),
    "fire": (),
    "weather": (
        ("winter", "Winter storms, snow and ice"),
        ("storm", "Severe storms, tornadoes and hurricanes"),
        ("flood", "Floods"),
        ("wind", "High wind and dust"),
        ("fog", "Dense fog"),
        ("fire_weather", "Fire weather and smoke"),
        ("temperature", "Extreme heat and cold"),
        ("other", "Other emergencies"),
    ),
}
SUBTYPE_IDS: dict[str, frozenset[str]] = {
    k: frozenset(s for s, _ in v) for k, v in SUBTYPES.items()}

# Incident classifier. Order matters: the first rule that matches wins,
# so "CFIRE-Car Fire" is a fire before it is anything else and "ESCORT
# for Road Conditions" is an escort, not a condition.
_INCIDENT_RULES: tuple[tuple[str, re.Pattern], ...] = tuple(
    (sid, re.compile(rx, re.I)) for sid, rx in (
        ("crash", r"collision|crash|accident|hit and run|hit & run|\bwreck|"
                  r"property damage|personal injury|\binjur|spin ?out|"
                  r"roll ?over|overturn|\b118[0-3]\b|\b1179\b|\b2000[12]\b|"
                  r"\bfatal"),
        ("vehicle_fire", r"fire|smoke"),
        ("closed", r"closure|closed|sig ?alert|road block|blocked"),
        ("police", r"police|law enforcement|escort|traffic break|pursuit|"
                   r"emergency|investigation|security|\bmedical"),
        ("conditions", r"weather|\bsnow|\bice\b|\bicy\b|\bfog|\bwind|flood|"
                       r"slide|mud|rock|chain|visibility|\brain|condition|"
                       r"\bdust|\bwater"),
        ("work", r"construction|maintenance|road ?work|work ?zone|"
                 r"\bassist ct\b|\bczp\b|\bmzp\b|utility|paving|striping|"
                 r"bridge work|mowing"),
        ("stall", r"disabled|stall|break ?down|broken down|abandon|\btow\b|"
                  r"flat tire|out of gas|vehicle off"),
        ("hazard", r"hazard|debris|object|animal|pedestrian|\bped\b|"
                   r"wrong ?way|obstruct|spill|pot ?hole|signal|downed|"
                   r"\btree|power line|fallen|load|cattle|livestock|deer"),
        ("advisory", r"advisory|\btadv\b|special event|\bevent|congestion|"
                     r"delay|parade|traffic|queue"),
    ))

_WEATHER_RULES: tuple[tuple[str, re.Pattern], ...] = tuple(
    (sid, re.compile(rx, re.I)) for sid, rx in (
        ("fire_weather", r"red flag|fire weather|smoke|ashfall|\bash\b"),
        ("winter", r"winter|snow|blizzard|\bice\b|freez|frost|sleet|lake effect"),
        ("storm", r"thunderstorm|tornado|hurricane|tropical|typhoon|storm surge"),
        ("flood", r"flood"),
        ("wind", r"wind|dust"),
        ("fog", r"fog"),
        ("temperature", r"heat|cold|chill"),
    ))

# Caltrans LCS closure classes (lcs_feed.closure_class) and the "cls" the
# out-of-state feeds set, to closure report types.
_CLOSURE_CLASS = {
    "full-roadway": "full",
    "lane": "lanes", "alternating-lanes": "lanes", "one-way-traffic": "lanes",
    "moving": "moving", "traffic-break": "moving",
    "ramp": "ramp",
    "other": "other",
}


def classify(kind: str, text: str | None = None, cls: str | None = None,
             status: str | None = None) -> str | None:
    """The report type of one event, from what its source said: the
    incident or alert type text, a closure class, or a chain status.
    None for kinds without report types (wildfires)."""
    if kind == "incident":
        t = text or ""
        for sid, rx in _INCIDENT_RULES:
            if rx.search(t):
                return sid
        return "other"
    if kind == "closure":
        return _CLOSURE_CLASS.get((cls or "").lower(), "lanes")
    if kind == "chain":
        # Caltrans statuses: R-1 to R-3 for every vehicle, MAX, MIN and
        # TS (trucks stop) for trucks, RC or ROAD CLOSED at a checkpoint.
        s = (status or "").upper().replace(" ", "")
        return {"R-1": "r1", "R1": "r1", "R-2": "r2", "R2": "r2",
                "R-3": "r3", "R3": "r3", "MAX": "trucks", "MIN": "trucks",
                "TS": "trucks", "RC": "closed",
                "ROADCLOSED": "closed"}.get(s, "advisory")
    if kind == "weather":
        t = text or ""
        for sid, rx in _WEATHER_RULES:
            if rx.search(t):
                return sid
        return "other"
    return None


# ---------------------------------------------------------------- sources

def source_id(label: str) -> str:
    """Stable slug for a source label ("MDOT CHART" -> "mdot-chart")."""
    slug = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    return slug[:40] or "source"


CHP = "chp"
NWS = "nws"
SOURCE_LABELS = {
    CHP: "California Highway Patrol",
    NWS: "National Weather Service",
}

# CHP's incident types, verbatim from the live statewide feed
# (read 2026-11-20). Other types CHP publishes
# join this list as the checker sees them (observe below).
CHP_TYPES: tuple[str, ...] = (
    "1179-Trfc Collision-1141 Enrt",
    "1182-Trfc Collision-No Inj",
    "1183-Trfc Collision-Unkn Inj",
    "1181-Trfc Collision-Minor Inj",
    "20002-Hit and Run No Injuries",
    "SPINOUT",
    "1125-Traffic Hazard",
    "ANIMAL-Live or Dead Animal",
    "1125A-Animal Hazard",
    "1166-Defective Traffic Signals",
    "CFIRE-Car Fire",
    "FIRE-Report of Fire",
    "CLOSURE of a Road",
    "CLOSURE-Closure of a Road",
    "SIG Alert",
    "1013-Road/Weather Conditions",
    "CHAINS-Chain Control",
    "FLOOD-Roadway Flooding",
    "FOG-Foggy Conditions",
    "SLIDE-Mud/Dirt/Rock",
    "SNOW Information",
    "WIND Advisory",
    "ESCORT for Road Conditions",
    "CZP-Assist with Construction",
    "MZP-Assist CT with Maintenance",
    "TADV-Traffic Advisory",
)

# National Weather Service products a road watch can carry: the ones
# nws.ROAD_EVENTS lets through. Nationwide, so offered everywhere.
NWS_TYPES: tuple[str, ...] = (
    "Winter Storm Warning", "Winter Storm Watch", "Winter Weather Advisory",
    "Blizzard Warning", "Ice Storm Warning", "Lake Effect Snow Warning",
    "Freeze Warning", "Frost Advisory",
    "Severe Thunderstorm Warning", "Tornado Warning", "Tornado Watch",
    "Hurricane Warning", "Tropical Storm Warning",
    "Flood Warning", "Flood Watch", "Flood Advisory", "Flash Flood Warning",
    "Flash Flood Watch", "Coastal Flood Warning",
    "High Wind Warning", "High Wind Watch", "Wind Advisory",
    "Dust Storm Warning", "Blowing Dust Advisory",
    "Dense Fog Advisory",
    "Red Flag Warning", "Fire Weather Watch", "Dense Smoke Advisory",
    "Extreme Heat Warning", "Heat Advisory", "Extreme Cold Warning",
    "Cold Weather Advisory",
    "Avalanche Warning", "Tsunami Warning", "Evacuation Immediate",
    "Civil Emergency Message",
)

CALIFORNIA = "California"
# Report types a state's sources provide before any of its events have
# been seen. California's are known: CHP for incidents, Caltrans lane
# closures (every class) and chain controls (R-1 to R-3).
_CA_CAPS = {
    "incident": SUBTYPE_IDS["incident"],
    "closure": SUBTYPE_IDS["closure"],
    "chain": frozenset({"r1", "r2", "r3", "trucks", "closed"}),
}
# Elsewhere: incidents and closures (full and lane) are what the state
# feeds carry; anything more is learned from what they publish.
_DEFAULT_CAPS = {
    "incident": SUBTYPE_IDS["incident"],
    "closure": frozenset({"full", "lanes"}),
}

# ---------------------------------------------------------------- learned catalog

# source id -> {"label", "states": {state}, "kinds": {kind}, "subtypes":
# {kind: {sid}}, "types": {kind: {raw: [count, last_seen]}}}
_CATALOG: dict[str, dict] = {}
MAX_TYPES_PER_SOURCE = 60
MAX_TYPE_LEN = 80
TYPE_KEEP_SECONDS = 45 * 86400
# A learned source type is offered once this many distinct events have
# carried it: some feeds put free text in their type field ("Cleared
# Crash on SB M-39"), and a one-off string is not a category.
MIN_EVENTS_TO_LIST = 2
_RECENT_IDS: dict[tuple, list] = {}
_dirty = False


def _state_of(lat: float, lon: float, areas: list[dict],
              in_california) -> list[str]:
    if in_california(lat, lon):
        return [CALIFORNIA]
    return [a["state"] for a in areas
            if a["bounds"][0] <= lat <= a["bounds"][2]
            and a["bounds"][1] <= lon <= a["bounds"][3]]


def observe(events: list[dict], areas: list[dict], in_california,
            now: float | None = None) -> None:
    """Learn, from one checker cycle, which sources report which kinds,
    report types and source types, and in which states. Never raises."""
    global _dirty
    now = time.time() if now is None else now
    if len(_RECENT_IDS) > 20_000:  # free-text type fields, bounded
        _RECENT_IDS.clear()
    try:
        for e in events:
            sid = e.get("src_id")
            kind = e.get("kind")
            if not sid or kind not in KIND_IDS or sid == NWS:
                continue
            lat, lon = e.get("lat"), e.get("lon")
            if not lat or not lon:
                continue
            entry = _CATALOG.setdefault(sid, {
                "label": e.get("src_label") or SOURCE_LABELS.get(sid, sid),
                "states": set(), "kinds": set(), "subtypes": {}, "types": {}})
            for st in _state_of(lat, lon, areas, in_california):
                if st not in entry["states"]:
                    entry["states"].add(st)
                    _dirty = True
            if kind not in entry["kinds"]:
                entry["kinds"].add(kind)
                _dirty = True
            sub = e.get("subtype")
            if sub:
                subs = entry["subtypes"].setdefault(kind, set())
                if sub not in subs:
                    subs.add(sub)
                    _dirty = True
            raw = clean_type(e.get("raw_type"))
            if raw:
                types = entry["types"].setdefault(kind, {})
                # Count distinct events, not cycles: one long-lived event
                # seen every 5 minutes is still one report of its type.
                ids = _RECENT_IDS.setdefault((sid, kind, raw), [])
                eid = str(e.get("id") or "")
                fresh = eid not in ids
                if fresh:
                    ids.append(eid)
                    del ids[:-8]
                if raw in types:
                    if fresh:
                        types[raw][0] += 1
                        if types[raw][0] == MIN_EVENTS_TO_LIST:
                            _dirty = True
                    types[raw][1] = now
                else:
                    types[raw] = [1, now]
                    if len(types) > MAX_TYPES_PER_SOURCE * 2:
                        _prune(types, now)
    except Exception:  # noqa: BLE001 - learning never breaks a cycle
        return


def _prune(types: dict, now: float) -> None:
    for raw in [r for r, (_, ts) in types.items()
                if now - ts > TYPE_KEEP_SECONDS]:
        del types[raw]
    if len(types) > MAX_TYPES_PER_SOURCE * 2:
        keep = sorted(types.items(), key=lambda kv: -kv[1][0])
        types.clear()
        types.update(dict(keep[:MAX_TYPES_PER_SOURCE * 2]))


def clean_type(value) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip('"').strip()
    if not text or len(text) > MAX_TYPE_LEN:
        return None
    if text.lower() in ("incident", "event", "reported event", "unknown"):
        return None
    return text


def catalog_snapshot() -> dict:
    """The learned catalog in a Firestore-safe shape (maps and lists of
    scalars only, no nested arrays)."""
    out = {}
    for sid, e in _CATALOG.items():
        out[sid] = {
            "label": e["label"],
            "states": sorted(e["states"]),
            "kinds": sorted(e["kinds"]),
            "subtypes": {k: sorted(v) for k, v in e["subtypes"].items()},
            "types": {k: {raw: {"n": c, "t": round(ts)}
                          for raw, (c, ts) in t.items()}
                      for k, t in e["types"].items()},
        }
    return out


def load_snapshot(data: dict | None) -> None:
    """Merge a stored catalog back in (after a restart). Bad rows are
    skipped; what this process learned since boot wins."""
    if not isinstance(data, dict):
        return
    for sid, row in data.items():
        if not isinstance(row, dict) or not isinstance(sid, str):
            continue
        entry = _CATALOG.setdefault(sid, {
            "label": str(row.get("label") or sid)[:80], "states": set(),
            "kinds": set(), "subtypes": {}, "types": {}})
        entry["states"].update(s for s in row.get("states") or []
                               if isinstance(s, str))
        entry["kinds"].update(k for k in row.get("kinds") or []
                              if k in KIND_IDS)
        for k, subs in (row.get("subtypes") or {}).items():
            if k in SUBTYPE_IDS:
                entry["subtypes"].setdefault(k, set()).update(
                    s for s in subs or [] if s in SUBTYPE_IDS[k])
        for k, types in (row.get("types") or {}).items():
            if k not in KIND_IDS or not isinstance(types, dict):
                continue
            mine = entry["types"].setdefault(k, {})
            for raw, v in types.items():
                raw = clean_type(raw)
                if raw and raw not in mine and isinstance(v, dict):
                    try:
                        mine[raw] = [int(v.get("n", 1)), float(v.get("t", 0))]
                    except (TypeError, ValueError):
                        continue


def take_dirty() -> bool:
    """True once after the catalog learned something new."""
    global _dirty
    was, _dirty = _dirty, False
    return was


def reset() -> None:
    """Tests only."""
    global _dirty
    _CATALOG.clear()
    _RECENT_IDS.clear()
    _dirty = False


# ---------------------------------------------------------------- area -> options

def shape_samples(shape: dict) -> list[tuple[float, float]]:
    """Points spread over a drawn shape, enough to tell which states it
    touches: the boundary and a grid inside for circles and polygons,
    the line itself for routes."""
    kind = shape.get("type")
    pts: list[tuple[float, float]] = []
    if kind == "circle":
        c = shape.get("center") or {}
        lat, lon = float(c["lat"]), float(c["lon"])
        r = float(shape.get("radius_km") or 1.0)
        pts.append((lat, lon))
        for frac in (0.5, 1.0):
            for i in range(16):
                a = 2 * math.pi * i / 16
                dlat = (r * frac / 110.57) * math.cos(a)
                dlon = (r * frac / (111.32 * max(0.2, math.cos(math.radians(lat))))) \
                    * math.sin(a)
                pts.append((lat + dlat, lon + dlon))
        return pts
    raw = shape.get("points") or []
    pairs = [(float(p["lat"]), float(p["lon"])) if isinstance(p, dict)
             else (float(p[0]), float(p[1])) for p in raw]
    if not pairs:
        return []
    if kind == "route":
        step = max(1, len(pairs) // 120)
        return pairs[::step] + [pairs[-1]]
    # Polygon: corners, edge points, and a grid of inside points.
    n = len(pairs)
    for i in range(n):
        a, b = pairs[i], pairs[(i + 1) % n]
        for t in (0.0, 0.25, 0.5, 0.75):
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    lats = [p[0] for p in pairs]
    lons = [p[1] for p in pairs]
    for i in range(1, 8):
        for j in range(1, 8):
            pts.append((min(lats) + (max(lats) - min(lats)) * i / 8,
                        min(lons) + (max(lons) - min(lons)) * j / 8))
    return pts


def states_for_shape(shape: dict, areas: list[dict], in_california,
                     point_in_polygon) -> list[str]:
    """Every covered state the shape reaches. Polygon grid points only
    count when they are inside the polygon."""
    samples = shape_samples(shape)
    poly = None
    if shape.get("type") == "polygon":
        poly = [[float(p["lat"]), float(p["lon"])] if isinstance(p, dict)
                else [float(p[0]), float(p[1])]
                for p in shape.get("points") or []]
    found: list[str] = []
    for i, (lat, lon) in enumerate(samples):
        # The first 4 * corners samples sit on the boundary itself.
        if poly and i >= 4 * len(poly) and not point_in_polygon(lat, lon, poly):
            continue
        for st in _state_of(lat, lon, areas, in_california):
            if st not in found:
                found.append(st)
    return found


def _type_rows(kind: str, sid: str, types: dict[str, list],
               min_events: int = MIN_EVENTS_TO_LIST) -> list[dict]:
    ranked = sorted(((raw, v) for raw, v in types.items() if v[0] >= min_events),
                    key=lambda kv: (-kv[1][0], kv[0].lower()))
    return [{"key": f"{sid}|{raw}", "label": raw,
             "subtype": classify(kind, raw)}
            for raw, _ in ranked[:MAX_TYPES_PER_SOURCE]]


def area_options(states: list[str]) -> dict:
    """What a watch over these states can be told about: every kind,
    whether the area has it, its report types the area's sources
    provide, and each report type's exact source types by source."""
    state_set = set(states)
    learned = {sid: e for sid, e in _CATALOG.items()
               if e["states"] & state_set}
    known_states = set()
    for e in learned.values():
        known_states |= e["states"] & state_set
    caps: dict[str, set[str]] = {k: set() for k in KIND_IDS}
    kinds_here = {"fire", "weather"}  # nationwide wildfire and NWS feeds
    for st in state_set:
        if st == CALIFORNIA:
            base = _CA_CAPS
        elif st in known_states:
            base = {}
        else:
            base = _DEFAULT_CAPS
        for k, subs in base.items():
            caps[k] |= subs
            kinds_here.add(k)
    for e in learned.values():
        for k in e["kinds"]:
            kinds_here.add(k)
            if k == "incident":
                caps[k] |= SUBTYPE_IDS["incident"]
        for k, subs in e["subtypes"].items():
            caps[k] |= subs
    caps["weather"] |= SUBTYPE_IDS["weather"]

    # Source types, per kind, per source.
    sources: dict[str, list[tuple[str, str, list[dict]]]] = {k: [] for k in KIND_IDS}
    if CALIFORNIA in state_set:
        chp = {t: [0, 0.0] for t in CHP_TYPES}
        if CHP in _CATALOG:
            for raw, v in (_CATALOG[CHP]["types"].get("incident") or {}).items():
                chp[raw] = v
        sources["incident"].append((CHP, SOURCE_LABELS[CHP],
                                    _type_rows("incident", CHP, chp, 0)))
    for sid, e in sorted(learned.items(), key=lambda kv: kv[1]["label"].lower()):
        if sid == CHP:
            continue
        for k, types in e["types"].items():
            if types and k in kinds_here:
                sources[k].append((sid, e["label"], _type_rows(k, sid, types)))
    sources["weather"].append((NWS, SOURCE_LABELS[NWS], [
        {"key": f"{NWS}|{t}", "label": t, "subtype": classify("weather", t)}
        for t in NWS_TYPES]))

    kinds_out = []
    for kid, label, hint in KINDS:
        subs = []
        for sid, slabel in SUBTYPES[kid]:
            if sid not in caps[kid]:
                continue
            by_source = []
            for src_id, src_label, rows in sources[kid]:
                mine = [{"key": r["key"], "label": r["label"]}
                        for r in rows if r["subtype"] == sid]
                if mine:
                    by_source.append({"id": src_id, "label": src_label,
                                      "types": mine})
            subs.append({"id": sid, "label": slabel, "sources": by_source})
        kinds_out.append({"id": kid, "label": label, "hint": hint,
                          "available": kid in kinds_here, "subtypes": subs})
    return {"states": sorted(state_set), "kinds": kinds_out}


# ---------------------------------------------------------------- validation + matching

MAX_RAW_PER_KIND = 60
_RAW_KEY = re.compile(r"^[a-z0-9-]{1,40}\|[^\x00-\x1f|]{1,80}$")


def clean_filters(raw, kinds: list[str]) -> tuple[dict | None, str | None]:
    """Validate a watch's ``filters`` against its kinds. Returns
    (filters, None) or (None, error). Entries for kinds the watch does
    not alert on are dropped; an entry that picks every report type is
    the same as no entry and is dropped too, so report types added later
    reach it."""
    if raw is None:
        return {}, None
    if not isinstance(raw, dict):
        return None, "filters must be an object of kind -> report types"
    out: dict = {}
    for kind, entry in raw.items():
        if kind not in KIND_IDS:
            return None, f"unknown alert kind {str(kind)[:20]!r}"
        if kind not in kinds or entry is None:
            continue
        if not isinstance(entry, dict):
            return None, f"filters for {kind} must be an object"
        subs_in = entry.get("subtypes") or []
        raws_in = entry.get("raw") or []
        if not isinstance(subs_in, list) or not isinstance(raws_in, list):
            return None, "subtypes and raw must be lists"
        if not SUBTYPES[kind] and (subs_in or raws_in):
            return None, f"{kind} has no report types to choose from"
        subs = []
        for s in subs_in:
            if s not in SUBTYPE_IDS[kind]:
                return None, f"unknown report type {str(s)[:30]!r} for {kind}"
            if s not in subs:
                subs.append(s)
        if len(raws_in) > MAX_RAW_PER_KIND:
            return None, (f"pick at most {MAX_RAW_PER_KIND} source types "
                          f"per kind")
        raws = []
        for r in raws_in:
            r = str(r)
            if not _RAW_KEY.match(r):
                return None, "source types must look like source|type"
            # Already covered by a picked report type: redundant.
            if classify(kind, r.split("|", 1)[1]) in subs:
                continue
            if r not in raws:
                raws.append(r)
        if not subs and not raws:
            return None, (f"pick at least one report type for "
                          f"{dict((k, lbl) for k, lbl, _ in KINDS)[kind].lower()},"
                          f" or turn it off")
        if set(subs) == SUBTYPE_IDS[kind]:
            continue
        out[kind] = {"subtypes": subs, "raw": raws}
    return out, None


def facets(event: dict) -> tuple[str | None, str | None]:
    """(report type, "source|type" key) for an event. Events built by the
    checker carry both; older or hand-made ones are classified here."""
    kind = event.get("kind")
    sub = event.get("subtype")
    payload = event.get("payload") or {}
    if not sub:
        if kind == "closure":
            sub = classify(kind, cls=payload.get("class"))
        elif kind == "chain":
            sub = classify(kind, status=payload.get("status"))
        else:
            sub = classify(kind, event.get("raw_type") or event.get("title"))
    raw = clean_type(event.get("raw_type"))
    sid = event.get("src_id")
    return sub, (f"{sid}|{raw}" if sid and raw else None)


def passes(watch: dict, event: dict) -> bool:
    """Whether a watch alerts on this event, judged by kind and the
    watch's report-type filters (location is watch_matches' job)."""
    kind = event.get("kind")
    if kind not in (watch.get("kinds") or []):
        return False
    f = (watch.get("filters") or {}).get(kind)
    if not f:
        return True
    sub, key = facets(event)
    return (sub in (f.get("subtypes") or [])
            or (key is not None and key in (f.get("raw") or [])))
