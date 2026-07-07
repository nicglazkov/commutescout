"""Demo backend: a small Starlette app that answers road questions.

POST /api/ask runs Claude (claude-sonnet-5 by default, via DEMO_MODEL) in a
tool loop against the same six tool functions the MCP server exposes, and
streams the answer as SSE. Hard cost
guards: per-IP rate limit, per-IP daily question cap, and a global daily
dollar cap, all in process (single Cloud Run instance for v1).
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import anthropic
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ca_roads_mcp import server as tools
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
- Trips to landmarks or small places ("up to Alice's", "out to Pescadero")
  work when you pass coordinates: give check_route from_coords/to_coords
  from your own geographic knowledge, and the route and events clip to the
  actual stretch driven. When the user's location is available, it is the
  default trip origin. The server geocodes the place names too and its
  result wins, so name places precisely ("Alice's Restaurant, Woodside").
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
]

TOOL_FUNCS = {
    "check_region": tools.check_region,
    "check_route": tools.check_route,
    "get_incidents": tools.get_incidents,
    "get_lane_closures": tools.get_lane_closures,
    "get_chain_controls": tools.get_chain_controls,
    "get_wildfires": tools.get_wildfires,
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


async def answer_stream(
    question: str,
    location: tuple[float, float] | None = None,
    prior: dict | None = None,
    visitor: str = "",
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
    for _ in range(MAX_TOOL_TURNS):
        async with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS_PER_TURN,
            system=SYSTEM,
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
    return StreamingResponse(
        answer_stream(question, location, prior, visitor_hash(client_ip(request))),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


async def health(_: Request):
    return JSONResponse({"ok": True, "version": VERSION, "model": MODEL})


app = Starlette(
    routes=[
        Route("/", index),
        Route("/logo.svg", logo),
        # /healthz is intercepted by Google's frontend on Cloud Run and never
        # reaches the container; /health gets through.
        Route("/health", health),
        Route("/api/ask", ask, methods=["POST"]),
        Route("/api/event", track, methods=["POST"]),
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]
)
# Request-level limiter on top of the daily caps (burst 5, ~6/min sustained).
app = RateLimitMiddleware(app, RateLimiter(capacity=5, refill_per_second=0.1))


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8081)))


if __name__ == "__main__":
    main()
