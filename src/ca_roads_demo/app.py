"""Demo backend: a small Starlette app that answers road questions.

POST /api/ask runs Claude (claude-sonnet-5 by default, via DEMO_MODEL) in a
tool loop against the same six tool functions the MCP server exposes, and
streams the answer as SSE. Hard cost
guards: per-IP rate limit, per-IP daily question cap, and a global daily
dollar cap, all in process (single Cloud Run instance for v1).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    FileResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ca_roads.feeds import lcs as lcs_feed
from ca_roads.feeds import tomtom as tomtom_feed
from ca_roads.feeds import wildfire as wildfire_feed
from ca_roads_demo import watch
from ca_roads_mcp import server as tools
from ca_roads_mcp.geocode import gazetteer_suggest, geocode_candidates, photon_suggest
from ca_roads_mcp.ratelimit import (
    RateLimiter,
    RateLimitMiddleware,
    trusted_client_ip,
)
from ca_roads_mcp.telemetry import log_event, redact_coords, visitor_hash

try:
    VERSION = version("ca-roads-mcp")
except PackageNotFoundError:  # running from a bare checkout
    VERSION = "dev"

MODEL = os.environ.get("DEMO_MODEL", "claude-sonnet-5")
MAX_QUESTION_CHARS = 300
MAX_PRIOR_ANSWER_CHARS = 8000
MAX_TOOL_TURNS = 6
MAX_TOKENS_PER_TURN = 1024

# Cost guards. The dollar cap is computed from actual usage at list pricing
# (standard rates, not intro discounts, so the cap errs on the early side).
PER_IP_DAILY_QUESTIONS = int(os.environ.get("DEMO_PER_IP_DAILY", "20"))
GLOBAL_DAILY_DOLLARS = float(os.environ.get("DEMO_DAILY_DOLLARS", "3.0"))
# (input $/MTok, output $/MTok); unknown models assume Sonnet pricing.
PRICING_PER_MTOK = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-5": (3.00, 15.00),
}
INPUT_PER_MTOK, OUTPUT_PER_MTOK = PRICING_PER_MTOK.get(MODEL, (3.00, 15.00))

SYSTEM = """\
You are the CA Roads demo assistant. You answer questions about CURRENT
California road conditions using the tools provided (live CHP incidents,
Caltrans lane closures and chain controls, wildfires). Rules:
- Only answer California road-condition questions. Politely decline anything
  else in one sentence.
- Use check_route for trip questions between two places; check_region for
  area-scale questions (the Bay Area, SoCal, the Sierra); the filtered
  tools for single-road or single-place questions.
- For trips, pass from_coords ONLY for the user's own shared location or a
  major city. NEVER pass to_coords for street addresses, landmarks, or
  small places, even if you think you know where they are: street names
  repeat across California towns and your recall picks the wrong one. Pass
  the name exactly as the user gave it and let the server geocode it; it
  resolves exact house numbers. When the user's location is available, it
  is the default trip origin.
- check_route and check_region responses may carry weather_alerts (NWS),
  road_weather (notable pavement/wind/visibility readings), and earthquake
  notes. Weave them into the verdict when present; a storm warning changes
  the advice even when the road is currently clear.
- Broad or vague questions have a tool: "busiest routes", "worst traffic
  right now", "what should I avoid" -> rank_routes. Never refuse a vague
  question; rank_routes plus check_region can answer almost anything
  statewide.
- When check_route returns alternative_corridors, mention them in one
  sentence and offer to check one, especially if the main route looks bad.
- Cameras and signs are extra senses. When weather or a pass matters
  ("how's Donner right now"), call get_cameras so the user can SEE it,
  and get_road_signs to quote what the signs say. Sign text is the
  freshest local truth; quote it verbatim.
- If a tool response contains needs_clarification, do not answer and do
  not call more tools. Reply with one short sentence and then a fenced
  code block with language tag "options": first line is the question to
  ask, each following line is one option exactly as the tool listed it.
  The sentence before the block must not repeat that question; say
  something like "That street name exists in a few places." and stop.
- If check_route answers local_trip, do what it says: query get_incidents
  and get_lane_closures with the suggested_center. Short in-town trips have
  no highway corridor to check.
- Regional reports are capped to the most severe items with exact counts.
  Report the counts, lead with full closures and injury collisions, and
  group the rest ("plus 12 minor incidents") instead of listing everything.
- Closures are not all equal: only closure_class "full-roadway" means the
  road is closed. "ramp" means one ramp/connector is closed (say which),
  "one-way-traffic" means passable with flagging delays, "lane" means some
  of the lanes (the lanes field says how many of how many). Never call a
  ramp closure a highway closure.
- First answers are for a driver in a hurry: verdict first, then only what
  changes their plans. When the user asks to "tell me more", switch modes:
  go through the tool data thoroughly - every relevant event with its
  location, direction, lanes, delay, and timing - grouped under short
  headings, still in plain language. Re-query tools if you need detail you
  didn't fetch the first time.
- For a question about a town or place (not a specific highway), use your
  own knowledge of California geography to pass center="lat,lon" with
  radius_km 15-30 to get_incidents AND get_lane_closures (plus
  get_chain_controls in the mountains and get_wildfires in fire season).
  A circle covers every road around the place; a single highway filter or
  the CHP area filter does not.
- Directions matter. When the user asks about one direction ("northbound
  101", "westbound 80"), scope the answer to it: closures and chain
  controls carry a direction field, and incidents carry direction_hint
  parsed from the CHP location text. Say which direction each event
  affects; if an event's direction is unknown, include it but say so.
- When the user's current location is provided in the context, use it as
  the center for "near me" and ambiguous questions, and as the trip origin
  when they name only a destination.
- Be concise and practical for a driver. Lead with the answer.
- Simple markdown is fine (bold, short lists). Plain punctuation: never use
  em dashes. Write like a person: no "not X, but Y" constructions, no
  "it's not just about X", no rule-of-three flourishes.
- State how fresh the data is (data_as_of) and mention any feed problems.
- You report current status, not forecasts.
- End with: "Verify before you drive: 511 or quickmap.dot.ca.gov."
"""

TOOL_DEFS = [
    {
        "name": "check_route",
        "description": (
            "Current conditions along a major California corridor between two "
            "places: incidents, closures, chain controls, and wildfires near "
            "the route, ordered by miles from the start. ALWAYS pass "
            "from_coords and to_coords ('lat,lon' from your own knowledge of "
            "where the places are): they snap landmarks and small places onto "
            "the right corridor AND clip the route/events to the stretch "
            "actually driven, instead of the whole corridor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_place": {"type": "string"},
                "to_place": {"type": "string"},
                "from_coords": {"type": "string"},
                "to_coords": {"type": "string"},
            },
            "required": ["from_place", "to_place"],
        },
    },
    {
        "name": "check_region",
        "description": (
            "Full current-conditions report for a whole California region in "
            "one call: incidents (severity-sorted), lane closures, chain "
            "controls, wildfires. USE THIS for area-scale questions like "
            "'how is the Bay Area' or 'what's happening in SoCal'. Regions: "
            "bay area, sacramento area, sierra/tahoe, central valley, socal, "
            "san diego, central coast, north state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"region": {"type": "string"}},
            "required": ["region"],
        },
    },
    {
        "name": "get_incidents",
        "description": (
            "Live CHP incidents statewide. Filters: highway (e.g. 'I-80', "
            "'17'); center 'lat,lon' with radius_km - USE THIS for a town or "
            "place name (you know the coordinates), it catches every road "
            "around it; area matches CHP dispatch-area names like 'Hollister "
            "Gilroy' or 'East Sac', NOT town names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "highway": {"type": "string"},
                "area": {"type": "string"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_lane_closures",
        "description": (
            "Caltrans lane/road closures physically in place right now. "
            "Filters: route; district (1-12); center 'lat,lon' with "
            "radius_km for all closures around a place, on any road."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "route": {"type": "string"},
                "district": {"type": "integer"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_chain_controls",
        "description": (
            "Current chain-control levels (R-1/R-2/R-3) on mountain highways. "
            "Filters: route; center 'lat,lon' with radius_km for all "
            "checkpoints around a place."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "route": {"type": "string"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_wildfires",
        "description": (
            "Active California wildfires with size and containment, flagged "
            "when within ~10 miles of major highways. Filters: near_route; "
            "center 'lat,lon' with radius_km for fires around a place. Note: "
            "brand-new local fires often show in get_incidents (CHP 'FIRE-"
            "Report of Fire') before this interagency feed lists them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "near_route": {"type": "string"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
    {
        "name": "get_cameras",
        "description": (
            "Live Caltrans roadside camera snapshots, verified live (offline "
            "cameras filtered). Use when seeing conditions helps: weather on "
            "a pass, traffic density, fog. Filters: center 'lat,lon' with "
            "radius_km, route. Returned image_url values are shown to the "
            "user on the map automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "center": {"type": "string"},
                "route": {"type": "string"},
                "radius_km": {"type": "number"},
                "limit": {"type": "number"},
            },
        },
    },
    {
        "name": "rank_routes",
        "description": (
            "Ranks all 17 tracked corridors by what is happening on them "
            "right now. Use for broad questions: busiest routes, worst "
            "traffic, which highways to avoid. by='activity' (events) or "
            "by='congestion' (measured speeds). Each entry has counts and "
            "a reason - explain WHY routes rank, not just list them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "by": {"type": "string", "enum": ["activity", "congestion"]},
                "limit": {"type": "number"},
            },
        },
    },
    {
        "name": "get_road_signs",
        "description": (
            "What Caltrans changeable message signs are displaying right "
            "now (blank signs filtered). Signs often carry the freshest "
            "local truth: chain requirements, closures, delays. Quote sign "
            "text verbatim. Filters: route, center 'lat,lon' with radius_km."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "route": {"type": "string"},
                "center": {"type": "string"},
                "radius_km": {"type": "number"},
            },
        },
    },
]

TOOL_FUNCS = {
    "check_region": tools.check_region,
    "check_route": tools.check_route,
    "get_incidents": tools.get_incidents,
    "get_lane_closures": tools.get_lane_closures,
    "get_chain_controls": tools.get_chain_controls,
    "get_wildfires": tools.get_wildfires,
    "get_cameras": tools.get_cameras,
    "get_road_signs": tools.get_road_signs,
    "rank_routes": tools.rank_routes,
}

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


class DailyGuards:
    """Per-IP daily question counts and the global daily dollar counter.

    In-process: resets on instance restart, which only ever makes the caps
    more generous. Good enough to keep the worst case at a few dollars.
    """

    def __init__(self) -> None:
        self.day = ""
        self.questions: dict[str, int] = {}
        self.dollars = 0.0

    def _roll(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        if today != self.day:
            self.day = today
            self.questions = {}
            self.dollars = 0.0

    def try_start_question(self, ip: str) -> str | None:
        """Returns an error message when a cap blocks the question."""
        self._roll()
        if self.dollars >= GLOBAL_DAILY_DOLLARS:
            return "The demo hit its daily budget. Try again tomorrow."
        if self.questions.get(ip, 0) >= PER_IP_DAILY_QUESTIONS:
            return "Daily question limit reached for your address. Try again tomorrow."
        self.questions[ip] = self.questions.get(ip, 0) + 1
        return None

    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        self._roll()
        self.dollars += (
            input_tokens * INPUT_PER_MTOK + output_tokens * OUTPUT_PER_MTOK
        ) / 1_000_000


guards = DailyGuards()


def client_ip(request: Request) -> str:
    return trusted_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def extract_geo(tool: str, result: dict) -> dict | None:
    """Pull mappable geometry out of a tool result for the page's map panel."""
    markers: list[dict] = []

    def add(kind: str, lat, lon, label: str, cls: str | None = None) -> None:
        if isinstance(lat, int | float) and isinstance(lon, int | float) and lat:
            marker = {"kind": kind, "lat": lat, "lon": lon, "label": label}
            if cls:
                marker["cls"] = cls
            markers.append(marker)

    if tool == "check_route":
        for event in result.get("events", []):
            d = event.get("detail", {})
            kind = event.get("kind", "incident")
            label = event.get("summary", "")
            if kind == "lane_closure":
                begin = d.get("begin", {})
                add(kind, begin.get("lat"), begin.get("lon"), label,
                    d.get("closure_class"))
            else:
                add(kind, d.get("lat"), d.get("lon"), label)
                if kind == "wildfire" and d.get("perimeter") and markers:
                    markers[-1]["poly"] = d["perimeter"]
    for item in result.get("incidents", []):
        add("incident", item.get("lat"), item.get("lon"),
            f"{item.get('type', '')} @ {item.get('location', '')}")
    for item in result.get("closures", []):
        begin = item.get("begin", {})
        add("lane_closure", begin.get("lat"), begin.get("lon"),
            item.get("summary", ""), item.get("closure_class"))
    for item in result.get("chain_controls", []):
        add("chain_control", item.get("lat"), item.get("lon"),
            item.get("summary", ""))
    wildfires = result.get("wildfires", [])
    filters = result.get("filters") or {}
    scoped = filters.get("near_route") or filters.get("center") or filters.get("region")
    if wildfires and not scoped:
        # Unfiltered statewide fire list: only map fires near a major highway,
        # otherwise the map zooms out to the whole state.
        wildfires = [f for f in wildfires if f.get("near_highways")]
    for item in wildfires:
        add("wildfire", item.get("lat"), item.get("lon"), item.get("summary", ""))
        if item.get("perimeter") and markers:
            markers[-1]["poly"] = item["perimeter"]

    for item in result.get("cameras", []):
        if isinstance(item.get("lat"), int | float) and item.get("lat"):
            markers.append({
                "kind": "camera", "lat": item["lat"], "lon": item["lon"],
                "label": item.get("name", "camera"),
                "image": item.get("image_url"),
            })

    for item in result.get("signs", []):
        if isinstance(item.get("lat"), int | float) and item.get("lat"):
            markers.append({
                "kind": "sign", "lat": item["lat"], "lon": item["lon"],
                "label": f"Sign: {item.get('message', '')}",
                "route": item.get("route"), "direction": item.get("direction"),
                "near": item.get("near"), "message": item.get("message"),
            })

    payload: dict = {}
    if markers:
        payload["markers"] = markers
    if result.get("route_geometry"):
        payload["route"] = result["route_geometry"]
        if result.get("origin"):
            payload["origin"] = result["origin"]
        if result.get("destination"):
            payload["destination"] = result["destination"]
    return payload or None


def _safe_zone(name) -> ZoneInfo:
    """The browser-reported IANA zone, or Pacific: this is a California
    road service, so PT is the right default when the header is absent or
    garbage."""
    try:
        return ZoneInfo(str(name)[:64])
    except Exception:  # noqa: BLE001
        return ZoneInfo("America/Los_Angeles")


async def answer_stream(
    question: str,
    location: tuple[float, float] | None = None,
    prior: dict | None = None,
    visitor: str = "",
    tz: str | None = None,
):
    client = get_client()
    started = time.monotonic()
    tool_calls: list[dict] = []
    tokens = {"in": 0, "out": 0}
    answer_chars = 0
    content = question
    if location:
        content += (
            f"\n\n(Context: the user's current location is "
            f"{location[0]:.4f},{location[1]:.4f}.)"
        )
        yield _sse({"map": {"user": [location[0], location[1]]}})
    messages = []
    if prior:
        # Stateless follow-up: the page sends back the previous exchange so
        # "tell me more" has context without server-side sessions.
        messages.append({"role": "user", "content": prior["question"]})
        messages.append({"role": "assistant", "content": prior["answer"]})
    messages.append({"role": "user", "content": content})
    zone = _safe_zone(tz or "America/Los_Angeles")
    now_local = datetime.now(zone)
    system = SYSTEM + (
        f"\n\nThe user's local time zone is {zone.key} and it is "
        f"{now_local:%A, %B %d at %I:%M %p} there right now. Express every "
        "time in the user's zone in plain 12-hour form ('4:55 AM'); never "
        "show UTC or raw ISO timestamps. Tool data_as_of values are UTC - "
        "convert them."
    )
    for _ in range(MAX_TOOL_TURNS):
        async with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS_PER_TURN,
            system=system,
            tools=TOOL_DEFS,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield _sse({"text": text})
            response = await stream.get_final_message()
        guards.add_usage(response.usage.input_tokens, response.usage.output_tokens)
        tokens["in"] += response.usage.input_tokens
        tokens["out"] += response.usage.output_tokens
        answer_chars += sum(
            len(b.text) for b in response.content if b.type == "text"
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            _log_question(visitor, question, location, prior, tool_calls,
                          tokens, answer_chars, started, True)
            yield _sse({"done": True})
            return
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            func = TOOL_FUNCS.get(block.name)
            geo = None
            tool_started = time.monotonic()
            try:
                result = await func(**block.input) if func else {"error": "unknown tool"}
                content = json.dumps(result, default=str)
                is_error = False
                if isinstance(result, dict):
                    geo = extract_geo(block.name, result)
            except Exception as exc:  # noqa: BLE001 - surface tool failure to the model
                content = f"tool failed: {type(exc).__name__}: {exc}"
                is_error = True
            tool_calls.append({
                "tool": block.name,
                "args": redact_coords(block.input),
                "ms": round((time.monotonic() - tool_started) * 1000),
                "error": is_error,
            })
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                }
            )
            yield _sse({"tool": block.name})
            if geo:
                yield _sse({"map": geo})
        messages.append({"role": "user", "content": results})
    _log_question(visitor, question, location, prior, tool_calls, tokens,
                  answer_chars, started, False)
    yield _sse({"text": "\n(Stopped: too many lookups for one question.)"})
    yield _sse({"done": True})


def _log_question(visitor, question, location, prior, tool_calls, tokens,
                  answer_chars, started, completed):
    log_event(
        "question",
        visitor=visitor,
        question=question,
        followup=bool(prior),
        location_shared=bool(location),
        tools=tool_calls,
        input_tokens=tokens["in"],
        output_tokens=tokens["out"],
        est_cost_usd=round(
            (tokens["in"] * INPUT_PER_MTOK + tokens["out"] * OUTPUT_PER_MTOK)
            / 1_000_000, 5,
        ),
        answer_chars=answer_chars,
        duration_ms=round((time.monotonic() - started) * 1000),
        completed=completed,
        model=MODEL,
    )


async def ask(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    question = (body.get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "question is required"}, status_code=400)
    if len(question) > MAX_QUESTION_CHARS:
        return JSONResponse(
            {"error": f"question too long (max {MAX_QUESTION_CHARS} chars)"},
            status_code=400,
        )
    location = None
    raw_loc = body.get("location")
    if isinstance(raw_loc, dict):
        try:
            lat, lon = float(raw_loc["lat"]), float(raw_loc["lon"])
        except (KeyError, TypeError, ValueError):
            return JSONResponse(
                {"error": "location must be {lat, lon}"}, status_code=400
            )
        if not (32.0 <= lat <= 42.5 and -125.0 <= lon <= -113.5):
            return JSONResponse(
                {"error": "location looks outside California"}, status_code=400
            )
        location = (lat, lon)
    prior = None
    raw_prior = body.get("prior")
    if isinstance(raw_prior, dict):
        prior_q = str(raw_prior.get("question") or "")[:MAX_QUESTION_CHARS]
        prior_a = str(raw_prior.get("answer") or "")[:MAX_PRIOR_ANSWER_CHARS]
        if prior_q and prior_a:
            prior = {"question": prior_q, "answer": prior_a}
    blocked = guards.try_start_question(client_ip(request))
    if blocked:
        return JSONResponse({"error": blocked}, status_code=429)
    tz = body.get("tz")
    return StreamingResponse(
        answer_stream(question, location, prior,
                      visitor_hash(client_ip(request)), tz=tz),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


_PERIM_CACHE: dict[tuple, tuple[float, list]] = {}


async def api_suggest(request: Request):
    """Search-as-you-type suggestions for the route planner.

    The Google-style recipe: instant offline matches from the CA place
    gazetteer, merged with Photon (built for autocomplete: typo-tolerant,
    biased toward the caller's position, restricted to a California
    bounding box). Nominatim never sees keystrokes - its policy forbids
    autocomplete - and stays the precision backstop when a freeform entry
    is validated on selection."""
    q = (request.query_params.get("q") or "").strip()
    if len(q) < 2 or len(q) > 120:
        return JSONResponse({"suggestions": []})
    try:
        bias_lat = float(request.query_params.get("lat", 37.4))
        bias_lon = float(request.query_params.get("lon", -120.9))
    except ValueError:
        bias_lat, bias_lon = 37.4, -120.9

    local = gazetteer_suggest(q, limit=3)
    remote = await photon_suggest(
        tools.get_road().client, q, bias_lat, bias_lon, limit=6
    )
    merged: list[dict] = []
    for cand in local + remote:
        dup = any(
            abs(cand["lat"] - m["lat"]) < 0.02
            and abs(cand["lon"] - m["lon"]) < 0.02
            and cand["name"].split(",")[0].lower() == m["name"].split(",")[0].lower()
            for m in merged
        )
        if not dup:
            merged.append(cand)
    return JSONResponse({"suggestions": merged[:7]})


async def api_flow(request: Request):
    """Per-point traffic flow for coloring a planned route. Returns one
    entry per requested point: {ratio, current, freeflow} or null. Without
    a traffic key every entry is null and the page keeps its default
    route color."""
    raw = (request.query_params.get("pts") or "").strip()
    pairs = []
    for chunk in raw.split("|")[:12]:
        try:
            lat, lon = (float(x) for x in chunk.split(","))
            pairs.append((lat, lon))
        except ValueError:
            continue
    if not pairs:
        return JSONResponse({"error": "pts=lat,lon|lat,lon required"},
                            status_code=400)
    road = tools.get_road()
    samples = await asyncio.gather(*(
        tomtom_feed.flow_at_point(road.client, lat, lon) for lat, lon in pairs
    ))
    out = []
    for s in samples:
        if s and s.get("current_mph") and s.get("freeflow_mph"):
            out.append({
                "ratio": round(s["current_mph"] / s["freeflow_mph"], 3),
                "current": s["current_mph"],
                "freeflow": s["freeflow_mph"],
            })
        else:
            out.append(None)
    return JSONResponse({"flow": out})


_TILE_CACHE: dict[str, tuple[float, bytes]] = {}
_TILE_TTL = 90.0
_TILE_MAX = 600


async def api_traffic_tile(request: Request):
    """Proxy TomTom's traffic-flow raster tiles so the key stays server
    side. Cached briefly; the layer is off by default and 404s cleanly
    when no key is configured."""
    key = tomtom_feed.api_key()
    if not key:
        return Response(status_code=404)
    try:
        z = int(request.path_params["z"])
        x = int(request.path_params["x"])
        y = int(request.path_params["y"])
    except (KeyError, ValueError):
        return Response(status_code=400)
    if not (3 <= z <= 16):
        return Response(status_code=404)
    cache_key = f"{z}/{x}/{y}"
    now = time.monotonic()
    hit = _TILE_CACHE.get(cache_key)
    if hit and now - hit[0] < _TILE_TTL:
        return Response(hit[1], media_type="image/png",
                        headers={"Cache-Control": "public, max-age=60"})
    road = tools.get_road()
    try:
        resp = await road.client.get(
            f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/"
            f"{z}/{x}/{y}.png",
            params={"key": key},
            timeout=8,
        )
        if resp.status_code != 200:
            return Response(status_code=404)
    except Exception:  # noqa: BLE001
        return Response(status_code=404)
    if len(_TILE_CACHE) > _TILE_MAX:
        oldest = sorted(_TILE_CACHE.items(), key=lambda kv: kv[1][0])
        for k, _ in oldest[: _TILE_MAX // 3]:
            _TILE_CACHE.pop(k, None)
    _TILE_CACHE[cache_key] = (now, resp.content)
    return Response(resp.content, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=60"})


async def api_geocode(request: Request):
    """Address validation for the route planner. Returns the resolved
    candidates so the page can confirm one address or offer a choice when
    the name exists in several places."""
    q = (request.query_params.get("q") or "").strip()
    if not q or len(q) > 200:
        return JSONResponse({"error": "provide q (max 200 chars)"}, status_code=400)
    road = tools.get_road()
    cands = await geocode_candidates(road.client, q)
    return JSONResponse({
        "query": q,
        "candidates": [
            {"lat": lat, "lon": lon, "name": ", ".join(name.split(", ")[:4])}
            for lat, lon, name in cands[:4]
        ],
    })


def _bbox_params(request: Request):
    try:
        parts = [float(x) for x in (request.query_params.get("bbox") or "").split(",")]
        if len(parts) != 4:
            return None
        lat_min, lon_min, lat_max, lon_max = parts
        if lat_min >= lat_max or lon_min >= lon_max:
            return None
        return lat_min, lon_min, lat_max, lon_max
    except ValueError:
        return None


async def api_mapdata(request: Request):
    """Everything in the viewport, no AI involved: the map is a product
    on its own. Dense layers (cameras, signs) only ship when the client
    asks for them (it gates them by zoom)."""
    box = _bbox_params(request)
    if box is None:
        return JSONResponse(
            {"error": "bbox=lat_min,lon_min,lat_max,lon_max required"},
            status_code=400,
        )
    lat_min, lon_min, lat_max, lon_max = box
    want = set((request.query_params.get("kinds") or
                "incident,closure,chain,fire").split(","))
    road = tools.get_road()

    def inside(lat, lon):
        return (lat and lon and lat_min <= lat <= lat_max
                and lon_min <= lon <= lon_max)

    markers = []
    chp, lcs, cc, wf = await asyncio.gather(
        road.incidents(), road.lane_closures(), road.chain_controls(),
        road.wildfires(),
    )
    if "incident" in want:
        for i in chp.records:
            if inside(i.lat, i.lon):
                markers.append({
                    "kind": "incident", "lat": i.lat, "lon": i.lon,
                    "type": i.log_type, "location": i.location,
                    "area": i.area,
                })
    if "closure" in want:
        for c in lcs.records:
            if inside(c.begin_lat, c.begin_lon):
                markers.append({
                    "kind": "lane_closure", "lat": c.begin_lat,
                    "lon": c.begin_lon,
                    "label": lcs_feed.describe(c),
                    "cls": lcs_feed.closure_class(c),
                    "route": c.route, "county": c.county,
                    "lanes": lcs_feed.lanes_summary(c),
                })
    if "chain" in want:
        for c in cc.records:
            if inside(c.lat, c.lon):
                markers.append({
                    "kind": "chain_control", "lat": c.lat, "lon": c.lon,
                    "status": c.status, "route": c.route,
                    "label": c.description,
                })
    fire_markers = []
    if "fire" in want:
        for f in wf.records:
            if inside(f.lat, f.lon):
                fire_markers.append({
                    "kind": "wildfire", "lat": f.lat, "lon": f.lon,
                    "name": f.name, "acres": f.size_acres,
                    "contained": f.percent_contained,
                })
        # Footprints for a modest number of fires; cached per bbox tile.
        if 0 < len(fire_markers) <= 12:
            key = (round(lat_min, 1), round(lon_min, 1),
                   round(lat_max, 1), round(lon_max, 1))
            cached = _PERIM_CACHE.get(key)
            if cached and time.monotonic() - cached[0] < 600:
                perims = cached[1]
            else:
                perims = await wildfire_feed.perimeters_in_bbox(
                    road.client, lat_min - 0.2, lon_min - 0.2,
                    lat_max + 0.2, lon_max + 0.2)
                _PERIM_CACHE[key] = (time.monotonic(), perims)
            by_name = {p["name"]: p for p in perims if p["name"]}
            for m in fire_markers:
                perim = by_name.get((m["name"] or "").upper())
                if perim:
                    pts = perim["points"]
                    step = max(1, len(pts) // 120)
                    m["poly"] = [[round(a, 4), round(b, 4)]
                                 for a, b in pts[::step]]
    markers.extend(fire_markers)

    if "camera" in want:
        cams = await road.cameras()
        for c in cams.records:
            if inside(c.lat, c.lon):
                markers.append({
                    "kind": "camera", "lat": c.lat, "lon": c.lon,
                    "name": c.location_name or c.nearby_place,
                    "route": c.route, "direction": c.direction,
                    "near": c.nearby_place,
                    "image": c.image_url,
                    "stream": c.stream_url or None,
                })
    if "rwis" in want:
        wx = await road.road_weather()
        for w in wx.records:
            if inside(w.lat, w.lon):
                markers.append({
                    "kind": "rwis", "lat": w.lat, "lon": w.lon,
                    "station": w.location_name, "route": w.route,
                    "air_c": w.air_temp_c, "pave_c": w.surface_temp_c,
                    "wind": w.wind_avg_mph, "gust": w.wind_gust_mph,
                    "vis_m": w.visibility_m,
                })

    if "sign" in want:
        signs = await road.message_signs()
        for s in signs.records:
            if inside(s.lat, s.lon):
                marker = {
                    "kind": "sign", "lat": s.lat, "lon": s.lon,
                    "route": s.route, "direction": s.direction,
                    "near": s.nearby_place or s.county,
                    "message": s.text,
                }
                if not s.text:
                    marker["blank"] = True
                markers.append(marker)

    # Everything, gzipped: the whole state is ~4k markers and compresses
    # roughly 10:1. No caps - the map IS the product.
    body = json.dumps({"markers": markers}).encode()
    if "gzip" in (request.headers.get("accept-encoding") or ""):
        import gzip as _gzip

        return Response(
            _gzip.compress(body, 6),
            media_type="application/json",
            headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"},
        )
    return Response(body, media_type="application/json")


async def stats(request: Request):
    """Statewide counts for the header KPI strip. Every feed involved is
    TTL-cached, so this is cheap after the first hit."""
    road = tools.get_road()
    chp, lcs, cc, wf, cams = await asyncio.gather(
        road.incidents(), road.lane_closures(), road.chain_controls(),
        road.wildfires(), road.cameras(),
    )
    return JSONResponse({
        "incidents": len(chp.records),
        "closures": len(lcs.records),
        "chain_controls": len(cc.records),
        "wildfires": len(wf.records),
        "cameras": len(cams.records),
    })


EVENT_ALLOWLIST = {
    "pageview", "example_click", "location_on", "tell_more",
    "feedback_up", "feedback_down",
}


async def track(request: Request):
    """No-cookie interaction beacon from the page. Logs an event name and a
    daily-rotating visitor hash; nothing else."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    event = body.get("event")
    if event not in EVENT_ALLOWLIST:
        return JSONResponse({"error": "unknown event"}, status_code=400)
    fields = {"visitor": visitor_hash(client_ip(request))}
    if event.startswith("feedback"):
        fields["question"] = str(body.get("question") or "")[:MAX_QUESTION_CHARS]
    log_event(event, **fields)
    return JSONResponse({"ok": True})


STATIC_DIR = Path(__file__).parent / "static"


async def index(_: Request):
    return FileResponse(STATIC_DIR / "index.html")


async def logo(_: Request):
    return FileResponse(STATIC_DIR / "logo.svg")


async def watch_page(_: Request):
    return FileResponse(STATIC_DIR / "watch.html")


async def admin_page(_: Request):
    return FileResponse(STATIC_DIR / "admin.html")


async def sw_js(_: Request):
    # Served from the root so the service worker scope covers /watch.
    return FileResponse(STATIC_DIR / "sw.js",
                        headers={"Service-Worker-Allowed": "/"})


async def manifest_file(_: Request):
    return FileResponse(STATIC_DIR / "manifest.webmanifest",
                        media_type="application/manifest+json")


async def health(_: Request):
    return JSONResponse({"ok": True, "version": VERSION, "model": MODEL})


async def _prewarm() -> None:
    """Fill the feed caches in the background the moment a cold instance
    boots. The static page serves immediately either way; this makes the
    first map-data request land on warm caches instead of paying for all
    thirteen feeds itself. Failures are fine - the request path retries."""
    road = tools.get_road()
    with contextlib.suppress(Exception):
        await asyncio.gather(
            road.incidents(), road.lane_closures(), road.chain_controls(),
            road.wildfires(), road.cameras(), road.message_signs(),
            road.road_weather(),
            return_exceptions=True,
        )


@contextlib.asynccontextmanager
async def _lifespan(app_):
    task = asyncio.create_task(_prewarm())
    yield
    task.cancel()


app = Starlette(
    lifespan=_lifespan,
    routes=[
        Route("/", index),
        Route("/logo.svg", logo),
        # /healthz is intercepted by Google's frontend on Cloud Run and never
        # reaches the container; /health gets through.
        Route("/health", health),
        Route("/api/ask", ask, methods=["POST"]),
        Route("/api/event", track, methods=["POST"]),
        Route("/api/stats", stats, methods=["GET"]),
        Route("/api/geocode", api_geocode, methods=["GET"]),
        Route("/api/suggest", api_suggest, methods=["GET"]),
        Route("/api/flow", api_flow, methods=["GET"]),
        Route("/api/traffictile/{z:int}/{x:int}/{y:int}.png", api_traffic_tile,
              methods=["GET"]),
        Route("/api/mapdata", api_mapdata, methods=["GET"]),
        Route("/watch", watch_page),
        Route("/admin", admin_page),
        Route("/sw.js", sw_js),
        Route("/manifest.webmanifest", manifest_file),
        Route("/api/watch/config", watch.api_watch_config, methods=["GET"]),
        Route("/api/watch/me", watch.api_watch_me, methods=["GET"]),
        Route("/api/watch/redeem", watch.api_watch_redeem, methods=["POST"]),
        Route("/api/watch/create", watch.api_watch_create, methods=["POST"]),
        Route("/api/watch/push", watch.api_push_subscribe, methods=["POST"]),
        Route("/api/watch/test", watch.api_watch_test, methods=["POST"]),
        Route("/api/watch/{watch_id}", watch.api_watch_delete,
              methods=["DELETE"]),
        Route("/api/admin/overview", watch.api_admin_overview,
              methods=["GET"]),
        Route("/api/admin/user", watch.api_admin_user, methods=["POST"]),
        Route("/api/admin/code", watch.api_admin_code, methods=["POST"]),
        Route("/api/check-watches", watch.api_check_watches,
              methods=["POST"]),
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]
)
# Request-level limiter on top of the daily caps (burst 5, ~6/min sustained).
app = RateLimitMiddleware(
    app,
    RateLimiter(capacity=5, refill_per_second=0.1),
    # The bucket protects the model-spending path (/api/ask) and event
    # spam. Data-plane GETs are cheap, feed-cached, and the standalone map
    # legitimately calls them on every pan - throttling them starves
    # address validation behind map browsing.
    exempt_prefixes=("/static/", "/logo.svg", "/health", "/favicon",
                     "/api/mapdata", "/api/stats", "/api/geocode",
                     "/api/suggest", "/api/flow", "/api/traffictile"),
)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8081)))


if __name__ == "__main__":
    main()
