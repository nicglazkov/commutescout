"""Generate site/lib/api-reference.json, the tool reference the
Developers page renders.

Parameter names and which are required come from the tools' own JSON
schemas (the same source the OpenAPI document uses), so the page cannot
drift from the server; the prose per tool and per parameter is curated
here, in one place. tests/test_api_reference.py fails when the committed
JSON no longer matches this script's output.

    .venv/Scripts/python scripts/gen_api_reference.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "lib" / "api-reference.json"

# What each parameter means, in the words a developer needs. Keys are
# tool name, then parameter name. Every schema parameter must appear.
PARAM_DOCS: dict[str, dict[str, str]] = {
    "check_route": {
        "from_place": "Start of the drive: a city, town or landmark name.",
        "to_place": "End of the drive.",
        "from_coords": "Start as \"lat,lon\". Pass it whenever you know it: it lets "
                       "small towns and landmarks resolve, and it clips the corridor to "
                       "the stretch actually driven.",
        "to_coords": "End as \"lat,lon\". Same rules as from_coords.",
    },
    "check_region": {
        "region": "One of: Bay Area, Sacramento metro, Tahoe/Sierra, Central Valley, "
                  "Southern California, San Diego, Central Coast, North State. Any "
                  "other value returns the list.",
    },
    "get_incidents": {
        "highway": "A route as people write it: \"I-80\", \"US 50\", \"17\", \"Hwy 99\". "
                   "Matches incidents whose location text names that route.",
        "area": "Substring of a CHP dispatch-area name (\"Golden Gate\", \"East Sac\"). "
                "These are communication-center names, not towns; for a town use center.",
        "center": "\"lat,lon\". With radius_km, incidents inside that circle. The right "
                  "filter for a town or place.",
        "radius_km": "Radius around center in kilometers. 15 to 30 covers a town.",
    },
    "get_lane_closures": {
        "route": "A route: \"I-80\", \"US 101\", \"1\".",
        "district": "Caltrans district, 1 to 12 (3 Sacramento and Tahoe, 4 Bay Area, "
                    "7 Los Angeles).",
        "center": "\"lat,lon\". Closures whose begin or end point is inside the circle.",
        "radius_km": "Radius around center in kilometers.",
    },
    "get_chain_controls": {
        "route": "A mountain route: \"80\", \"US-50\", \"SR-88\".",
        "center": "\"lat,lon\" for every checkpoint around a place, whatever highway.",
        "radius_km": "Radius around center in kilometers.",
    },
    "get_wildfires": {
        "near_route": "Only fires within about 10 miles of that highway's corridor "
                      "(\"I-5\", \"101\").",
        "center": "\"lat,lon\" for fires around a place, regardless of highway.",
        "radius_km": "Radius around center in kilometers.",
    },
    "rank_routes": {
        "by": "\"activity\" (live events: full closures weigh most, then incidents, "
              "lane closures, chain controls) or \"congestion\" (measured speed against "
              "free flow at each corridor's midpoint; falls back to activity when the "
              "traffic feed is off).",
        "limit": "How many corridors to return. Default 5, of 17.",
    },
    "get_cameras": {
        "center": "\"lat,lon\". Required unless route is given. Results sort nearest first.",
        "route": "Narrow to one highway: \"I-80\", \"50\".",
        "radius_km": "Radius around center in kilometers.",
        "limit": "At most 10 verified cameras per call.",
    },
    "get_road_signs": {
        "route": "A route: \"I-80\".",
        "center": "\"lat,lon\" with radius_km.",
        "radius_km": "Radius around center in kilometers.",
    },
    "get_nearby_events": {
        "center": "\"lat,lon\". Required.",
        "radius_km": "Radius in kilometers, capped at 160.",
        "kinds": "Comma list from incident, closure, chain, fire, sign, rwis, camera, "
                 "toll. Omit for everything.",
    },
}

# Per-tool facts a developer plans around: what it reads, how fresh it
# is, what it caps, and a working example query string.
TOOL_META: dict[str, dict] = {
    "check_route": {
        "title": "Check a route",
        "summary": "Everything active along one of 17 curated California corridors, "
                   "ordered by miles from the start, with a summary.",
        "reads": "CHP incidents, Caltrans lane closures in place, chain controls, "
                 "wildfires within about 10 miles, plus weather, road-weather stations, "
                 "recent earthquakes, signs and cameras along the way.",
        "refresh": "Incidents about once a minute; closures, chains and fires on a "
                   "five-minute cache.",
        "caps": "Not a general router. When no corridor matches, the response lists "
                "the covered corridors; use the filtered tools with center for "
                "anything else.",
        "poll_s": 60,
        "example": "check_route?from_place=Sacramento&to_place=Reno",
    },
    "check_region": {
        "title": "Check a region",
        "summary": "One-call report for a whole region: exact counts, incidents "
                   "severity first, full closures called out, chain controls, fires.",
        "reads": "Every California source over the region at once.",
        "refresh": "Incidents about once a minute; the rest on a five-minute cache.",
        "caps": "Large regions cap each list to the most severe items. Counts are "
                "always exact and the response says when a list was truncated.",
        "poll_s": 60,
        "example": "check_region?region=Bay%20Area",
    },
    "get_incidents": {
        "title": "Live incidents",
        "summary": "CHP dispatch incidents statewide: collisions, hazards, disabled "
                   "vehicles, closures as CHP logs them.",
        "reads": "The California Highway Patrol computer-aided dispatch feed, fetched "
                 "live on every call.",
        "refresh": "About once a minute; an incident disappears when CHP closes the log.",
        "caps": "Locations are dispatcher free text; a few incidents lack usable "
                "coordinates and are omitted. Current logs only, no history.",
        "poll_s": 60,
        "example": "get_incidents?center=37.48,-122.14&radius_km=20",
    },
    "get_lane_closures": {
        "title": "Lane closures",
        "summary": "Caltrans closures physically in place right now, classified by "
                   "what they mean for through traffic.",
        "reads": "The Caltrans Lane Closure System. Only closures crews have "
                 "established (CHP code 1097) and not yet picked up; scheduled work "
                 "that has not started is excluded, and shoulder-only work too.",
        "refresh": "Five-minute cache over the per-district feeds.",
        "caps": "At most 200 closures per call; total and truncated say when there "
                "were more. Read closure_class: full-roadway is the only class that "
                "means you cannot drive through.",
        "poll_s": 300,
        "example": "get_lane_closures?route=I-80&district=3",
    },
    "get_chain_controls": {
        "title": "Chain controls",
        "summary": "Current chain requirements at Caltrans checkpoints on mountain "
                   "routes.",
        "reads": "Caltrans chain-control status. R-1: chains or snow tires. R-2: "
                 "chains except 4WD/AWD with snow tires. R-3: chains on every vehicle.",
        "refresh": "Five-minute cache. Requirements change hour to hour in storms.",
        "caps": "Off season (roughly May to October) the response says no controls "
                "are active instead of returning an empty list.",
        "poll_s": 300,
        "example": "get_chain_controls?route=80",
    },
    "get_wildfires": {
        "title": "Wildfires",
        "summary": "Active California fires with size, containment and the major "
                   "highways within about 10 miles.",
        "reads": "The interagency WFIGS current-wildfire feed. Points are each fire's "
                 "origin, not its perimeter.",
        "refresh": "Five-minute cache; size and containment update once or twice a day.",
        "caps": "Knows nothing about road closures caused by a fire; cross-check "
                "incidents and lane closures for the area.",
        "poll_s": 300,
        "example": "get_wildfires?near_route=I-5",
    },
    "rank_routes": {
        "title": "Rank busiest routes",
        "summary": "All 17 corridors ranked by live events or measured congestion, "
                   "each with counts and a one-line reason.",
        "reads": "The same events as check_route, across every corridor.",
        "refresh": "Same as the underlying feeds.",
        "caps": "Congestion ranking needs the traffic feed; without it the ranking "
                "silently falls back to activity.",
        "poll_s": 60,
        "example": "rank_routes?by=activity&limit=5",
    },
    "get_cameras": {
        "title": "Highway cameras",
        "summary": "Roadside camera snapshots near a point or along a route, each "
                   "verified live before it is returned.",
        "reads": "About 3,000 in-service Caltrans cameras. Offline cameras that serve a "
                 "placeholder frame are filtered by image freshness.",
        "refresh": "Snapshots about once a minute; stream_url, when present, is HLS.",
        "caps": "At most 10 cameras per call. center is required unless route is given.",
        "poll_s": 60,
        "example": "get_cameras?center=39.32,-120.34&radius_km=15&limit=5",
    },
    "get_road_signs": {
        "title": "Message signs",
        "summary": "What changeable message signs are displaying right now, verbatim.",
        "reads": "Statewide Caltrans CMS text, blank and out-of-service signs already "
                 "filtered.",
        "refresh": "About two minutes.",
        "caps": "Quote sign text verbatim; it is the most current and most local "
                "signal there is.",
        "poll_s": 120,
        "example": "get_road_signs?route=I-80",
    },
    "get_nearby_events": {
        "title": "Nearby events, nationwide",
        "summary": "Live road events near a point across every covered state, "
                   "including California.",
        "reads": "State DOT incidents, roadwork and closures, chain and traction "
                 "advisories, nationwide wildfires, signs, road weather, cameras and "
                 "toll prices where agencies publish them. Each event names its "
                 "publishing agency.",
        "refresh": "Per source; each response lists every source with its data_as_of.",
        "caps": "radius_km caps at 160. Coverage varies by state; the data-sources "
                "page has the matrix. For California, the dedicated tools carry more "
                "detail.",
        "poll_s": 60,
        "example": "get_nearby_events?center=39.53,-119.81&radius_km=40&kinds=incident,closure",
    },
}


def build() -> dict:
    from ca_roads_mcp.rest import PREFIX, PUBLIC_BASE, tool_specs
    from ca_roads_mcp.server import mcp

    tools = []
    for spec in tool_specs(mcp):
        name = spec["name"]
        meta = TOOL_META[name]
        docs = PARAM_DOCS[name]
        missing = set(spec["properties"]) - set(docs)
        extra = set(docs) - set(spec["properties"])
        if missing or extra:
            raise SystemExit(f"{name}: undocumented {sorted(missing)}, stale {sorted(extra)}")
        params = [{"name": p, "required": p in spec["required"], "doc": docs[p]}
                  for p in spec["properties"]]
        tools.append({"name": name, "path": f"{PREFIX}/tools/{name}", "params": params, **meta})
    return {"base": PUBLIC_BASE, "prefix": PREFIX, "tools": tools}


def main() -> int:
    data = build()
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("site/lib/api-reference.json is stale; run scripts/gen_api_reference.py")
            return 1
        print("api-reference.json is current")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(data['tools'])} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
