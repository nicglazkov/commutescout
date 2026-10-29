"""What became of an event someone was alerted about.

A watch alert names one event at one moment. By the time the person
taps it, that event can still be live, can have changed (a chain
control stepped from R-1 to R-2, which the watch checker sees as a new
event id), or can have cleared. The phone asks here and says which,
instead of opening on an empty map or on a different event nearby.

The watch checker hands every cycle's events to `note_cycle`, which
keeps the live set and remembers what cleared for a day. The service
runs as one instance, so this memory is the whole truth until a
restart; after one, an id the checker has not seen is answered from the
map data alone (live if a matching marker is still there, gone if not).

Also here: the CHP dispatch-log shorthand translator, mirrored from the
web map (`static/map-app.js`, CHP_TERMS and explainLine) so the phone
apps show the same plain-English lines without carrying the table
themselves.
"""

from __future__ import annotations

import math
import re
import time

# How long a cleared event is remembered: alerts older than this are
# answered from the map data alone.
CLEARED_KEEP_SECONDS = 24 * 3600
CLEARED_MAX = 20_000

# Watch event kinds to the map's marker kinds (the names the apps and
# /api/mapdata use) and to the kinds build_markers is asked for.
MARKER_KIND = {"incident": "incident", "closure": "lane_closure",
               "chain": "chain_control", "fire": "wildfire"}
WANT_KIND = {"incident": "incident", "closure": "closure",
             "chain": "chain", "fire": "fire"}
# A marker this close to where the event was reported is the same event.
MATCH_METERS = 300

_live: dict[str, dict] = {}
_cleared: dict[str, tuple[dict, float]] = {}
_cycles = 0


def _brief(e: dict) -> dict:
    """The fields an alert carried, without the archive payload."""
    return {k: e.get(k) for k in ("id", "kind", "lat", "lon", "title", "body", "meta")}


def note_cycle(events: list[dict], now: float | None = None) -> None:
    """Record one watch-checker cycle: what is live now, and what was
    live last cycle and is not any more (cleared, at this moment)."""
    global _cycles
    now = time.time() if now is None else now
    fresh = {e["id"]: _brief(e) for e in events if e.get("id")}
    if _cycles:
        for eid, e in _live.items():
            if eid not in fresh:
                _cleared[eid] = (e, now)
    for eid in fresh:
        _cleared.pop(eid, None)
    # Forget old clears, and cap the memory on a bad day.
    cutoff = now - CLEARED_KEEP_SECONDS
    for eid in [k for k, (_, t) in _cleared.items() if t < cutoff]:
        del _cleared[eid]
    if len(_cleared) > CLEARED_MAX:
        oldest = sorted(_cleared.items(), key=lambda kv: kv[1][1])
        for eid, _ in oldest[: len(_cleared) - CLEARED_MAX]:
            del _cleared[eid]
    _live.clear()
    _live.update(fresh)
    _cycles += 1


def reset() -> None:
    """Tests only."""
    global _cycles
    _live.clear()
    _cleared.clear()
    _cycles = 0


def meters(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def lookup(event_id: str) -> dict:
    """What the checker knows about one event id.

    state is "active", "changed" (a chain control at the same checkpoint
    under another level), "cleared" (with cleared_at), or "unknown"
    (never seen since the last restart)."""
    if event_id in _live:
        return {"state": "active", "event": _live[event_id]}
    if event_id.startswith("chain:"):
        # chain:<index>:<status>: the same checkpoint at another level.
        stem = event_id.rsplit(":", 1)[0] + ":"
        for eid, e in _live.items():
            if eid.startswith(stem):
                return {"state": "changed", "event": e}
    if event_id in _cleared:
        e, t = _cleared[event_id]
        return {"state": "cleared", "event": e, "cleared_at": t}
    return {"state": "unknown"}


def nearest_marker(markers: list[dict], kind: str, lat: float, lon: float,
                   chp_id: str | None = None) -> dict | None:
    """The map marker for an event: the same CHP id when there is one,
    else the nearest marker of that kind within MATCH_METERS."""
    if chp_id:
        for m in markers:
            if m.get("kind") == "incident" and m.get("id") == chp_id:
                return m
    best, best_d = None, float(MATCH_METERS)
    for m in markers:
        if m.get("kind") != kind or m.get("lat") is None or m.get("lon") is None:
            continue
        d = meters(lat, lon, m["lat"], m["lon"])
        if d <= best_d:
            best, best_d = m, d
    return best


# ------------------------------------------------- CHP shorthand

# Mirrors CHP_TERMS in static/map-app.js, in the same order (the order
# matters: phrases first, then hyphenated codes and callsigns, then bare
# codes, then word tokens). Change both together.
_NB = r"(?<![-\d])"
_NA = r"(?![-\d])"
CHP_TERMS: list[tuple[str, str]] = [
    (r"\bNEG 180\b", "no major injuries"),
    (r"\bNEG 144\b", "no fatalities"),
    (r"\bCODE 4\b", "no further help needed"),
    (r"\bCODE 3\b", "running lights and siren"),
    (r"\bVERBAL 415\b", "verbal dispute"),
    (r"\bSOLO VEH\b", "single vehicle"),
    (r"\bO/TURNED\b", "overturned"),
    (r"\bI/S\b", "intersection"),
    (r"\b11-10\b", "take a report"),
    (r"\b11-24\b", "abandoned vehicle"),
    (r"\b11-25\b", "traffic hazard"),
    (r"\b11-41\b", "ambulance requested"),
    (r"\b11-44\b", "fatality"),
    (r"\b11-79\b", "collision, ambulance en route"),
    (r"\b11-80\b", "collision with major injuries"),
    (r"\b11-81\b", "collision with minor injuries"),
    (r"\b11-82\b", "collision, property damage only"),
    (r"\b11-83\b", "collision, injuries unknown"),
    (r"\b11-85\b", "tow truck requested"),
    (r"\b11-98\b", "meet the officer"),
    (r"\b([A-Z]\d{2,3}-\d{2,4}[A-Z]?|\d{2,3}-R?\d{1,3}[A-Z]?)\b(?!-)", r"unit \1"),
    (_NB + r"1185R" + _NA, "rotation tow requested"),
    (_NB + r"1185S" + _NA, "tow trucks"),
    (_NB + r"1185(?![-\dA-Z])", "tow truck"),
    (_NB + r"1186" + _NA, "operator alerted"),
    (_NB + r"1179" + _NA, "collision, ambulance en route"),
    (_NB + r"1180" + _NA, "collision with major injuries"),
    (_NB + r"1181" + _NA, "collision with minor injuries"),
    (_NB + r"1182" + _NA, "collision, property damage only"),
    (_NB + r"1183" + _NA, "collision, injuries unknown"),
    (_NB + r"1141" + _NA, "ambulance requested"),
    (_NB + r"1144" + _NA, "fatal collision"),
    (_NB + r"1124" + _NA, "abandoned vehicle"),
    (_NB + r"1125A" + _NA, "animal on the road"),
    (_NB + r"1125(?![-\dA])", "traffic hazard"),
    (_NB + r"1166" + _NA, "defective signal"),
    (_NB + r"1097" + _NA, "unit on scene"),
    (_NB + r"1098" + _NA, "assignment complete"),
    (_NB + r"1022" + _NA, "disregard"),
    (_NB + r"1023" + _NA, "stand by"),
    (_NB + r"1039" + _NA, "notified"),
    (_NB + r"1021" + _NA, "phone call"),
    (_NB + r"23103" + _NA, "reckless driving"),
    (_NB + r"23114" + _NA, "spilled load"),
    (_NB + r"20001" + _NA, "felony hit and run"),
    (_NB + r"20002" + _NA, "hit and run, property damage"),
    (_NB + r"23152" + _NA, "possible DUI"),
    (_NB + r"22350" + _NA, "unsafe speed"),
    (_NB + r"5150" + _NA, "mental health hold"),
    (_NB + r"\b180\b" + _NA, "major injuries"),
    (_NB + r"\b144\b" + _NA, "fatality"),
    (_NB + r"\b415\b" + _NA, "a dispute"),
    (r"\b97\b", "on scene"),
    (r"\bTC\b", "collision"), (r"\bVEHS\b", "vehicles"), (r"\bVEH\b", "vehicle"),
    (r"\bPED\b", "pedestrian"), (r"\bMC\b", "motorcycle"),
    (r"\bTRLR\b", "trailer"), (r"\bBLKG\b", "blocking"),
    (r"\bENRT\b", "en route"),
    (r"\bNEG\b", "no"), (r"\bPOSS\b", "possible"), (r"\bUNKN?\b", "unknown"),
    (r"\bRHS\b", "right-hand shoulder"), (r"\bLHS\b", "left-hand shoulder"),
    (r"\bCD\b", "center divider"), (r"\bOFR\b", "off-ramp"),
    (r"\bONR\b", "on-ramp"), (r"\bJSO\b", "just south of"),
    (r"\bJNO\b", "just north of"), (r"\bJEO\b", "just east of"),
    (r"\bJWO\b", "just west of"), (r"\bIFO\b", "in front of"),
    (r"\bNB\b", "northbound"),
    (r"\bSB\b", "southbound"), (r"\bEB\b", "eastbound"),
    (r"\bWB\b", "westbound"), (r"\bLNS\b", "lanes"), (r"\bLN\b", "lane"),
    (r"\bPK\b", "pickup"), (r"\bTK\b", "truck"), (r"\bTRK\b", "truck"),
    (r"\bSD\b", "sedan"), (r"\bSEMI\b", "semi-truck"),
    (r"\bFSP\b", "Freeway Service Patrol"),
    (r"\bXFER\b", "transferred to"),
    (r"\bADVSD\b", "advised"), (r"\bADVD\b", "advised"),
    (r"\bADV\b", "advised"), (r"\bLL\b", "landline call"),
    (r"\bREQ\b", "requesting"), (r"\bRESP\b", "respond"),
    (r"\bINJS\b", "injuries"), (r"\bINJ\b", "injuries"),
    (r"\bDMG\b", "damage"), (r"\bCONT\b", "continued"),
    (r"\bRDWY\b", "road"), (r"\bDRVR\b", "driver"),
    (r"\bDESC\b", "description"), (r"\bVICT\b", "victim"),
    (r"\bSUSP\b", "suspect"), (r"\bINVLVD\b", "involved"),
    (r"\bINVLD\b", "involved"),
    (r"\bSV\b", "the subject vehicle"), (r"\bVV\b", "the victim vehicle"),
    (r"\bWW\b", "the wrong way"), (r"\bXRAY\b", "a female"),
    (r"\bOO\b", "out of"),
    (r"\bUTL\b", "unable to locate"), (r"\bGOA\b", "gone on arrival"),
    (r"\bHBD\b", "had been drinking"), (r"\bCDF\b", "CAL FIRE"),
    (r"\bFB\b", "flatbed"), (r"\bCR ?(\d+)\b", r"County Road \1"),
    (r"\bW/", "with "), (r"\bFRM\b", "from"),
    (r"\bRPS\b", "the caller's"), (r"\bRP\b", "the caller"),
    (r"\bTT\b", "tow truck"), (r"\bPLS\b", "please"),
    (r"\bAPPRO[XZ]\b", "approximately"),
    (r"\bPTYS\b", "people"), (r"\bPRTYS\b", "people"),
    (r"\bPTY\b", "person"), (r"\bPRTY\b", "person"),
    (r"\bRD\b", "Road"),
    (r"\bTOYT\b", "Toyota"), (r"\bHOND\b", "Honda"), (r"\bCHEV\b", "Chevrolet"),
    (r"\bNISS\b", "Nissan"), (r"\bFORD\b", "Ford"), (r"\bDODG\b", "Dodge"),
    (r"\bSUBA\b", "Subaru"), (r"\bHYUN\b", "Hyundai"), (r"\bVOLK\b", "Volkswagen"),
    (r"\bMERZ\b", "Mercedes"), (r"\bTESL\b", "Tesla"), (r"\bMAZD\b", "Mazda"),
    (r"\bLEXS\b", "Lexus"), (r"\bTOYO\b", "Toyota"), (r"\bVOLV\b", "Volvo"),
    (r"\bToyota TAC\b", "Toyota Tacoma"), (r"\bToyota CAM\b", "Toyota Camry"),
    (r"\bWHI\b", "white"), (r"\bBLK\b", "black"), (r"\bGRY\b", "gray"),
    (r"\bSIL\b", "silver"), (r"\bBLU\b", "blue"), (r"\bGRN\b", "green"),
    (r"\bYEL\b", "yellow"), (r"\bORG\b", "orange"), (r"\bBRO\b", "brown"),
]
_TERMS = [(re.compile(p), r) for p, r in CHP_TERMS]
# Official hyphenated labels ("1179-Trfc Collision-1141 Enrt") stay verbatim.
_LABEL = re.compile(r"\d{4}[A-Z]?-\S[^,\[\]]*")


def explain_line(text: str) -> str | None:
    """A dispatch-log line in plain English, or None when nothing in it
    is shorthand we are sure about."""
    keep: list[str] = []

    def mask(m: re.Match) -> str:
        keep.append(m.group(0))
        return f"\x01{len(keep) - 1}\x01"

    masked = _LABEL.sub(mask, text or "")
    out = masked
    for rx, plain in _TERMS:
        out = rx.sub(plain, out)
    if out == masked:
        return None
    return re.sub(r"\x01(\d+)\x01", lambda m: keep[int(m.group(1))], out)


_SEQ = re.compile(r"^\[(\d+)\]")
_CLOCK = re.compile(r"(\d{1,2}:\d{2})\s*(AM|PM)", re.I)
_UNIT_STATUS = {"assigned": "assigned", "enroute": "en route",
                "at scene": "on scene", "cleared": "cleared to leave"}


def clock(stamp: str) -> str:
    """CHP's "Jul 29 2026 12:51AM" as "12:51 AM"."""
    m = _CLOCK.search(stamp or "")
    return f"{m.group(1)} {m.group(2).upper()}" if m else (stamp or "")


def dispatch_log(details: list, units: list) -> dict:
    """The dispatch log newest first, each line with its translation,
    and one story per unit, the way the web map's popup tells it."""
    rows = []
    for i, en in enumerate(details or []):
        stamp, text = (list(en) + ["", ""])[:2]
        m = _SEQ.match(text or "")
        rows.append((int(m.group(1)) if m else i, {
            "time": clock(stamp), "text": text or "", "plain": explain_line(text or "")}))
    rows.sort(key=lambda r: -r[0])
    # The units feed is a flat pile of status flips, newest first, each
    # unit's run ending at its "Unit Assigned" row.
    groups, cur = [], []
    for en in units or []:
        cur.append(list(en) + ["", ""])
        if re.search("assigned", cur[-1][1] or "", re.I):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    story = []
    for n, grp in enumerate(groups, 1):
        steps = []
        for en in reversed(grp):
            key = re.sub(r"^Unit\s*", "", en[1] or "", flags=re.I).lower()
            steps.append({"status": _UNIT_STATUS.get(key, key), "time": clock(en[0])})
        story.append({"unit": n, "steps": steps,
                      "done": bool(re.search("cleared", grp[0][1] or "", re.I))})
    return {"log": [r for _, r in rows], "units": story}
