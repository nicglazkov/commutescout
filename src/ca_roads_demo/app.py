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

from ca_roads.feeds import calfire as calfire_feed
from ca_roads.feeds import lcs as lcs_feed
from ca_roads.feeds import tomtom as tomtom_feed
from ca_roads.feeds import wildfire as wildfire_feed
from ca_roads_demo import analytics, states, trips, watch
from ca_roads_demo.prompt import SYSTEM, TOOL_DEFS, TOOL_FUNCS  # noqa: F401
from ca_roads_mcp import server as tools
from ca_roads_mcp.geocode import gazetteer_suggest, geocode_candidates, photon_suggest
from ca_roads_mcp.ratelimit import (
    RateLimiter,
    RateLimitMiddleware,
    trusted_client_ip,
)
from ca_roads_mcp.serialize import direction_hint
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
            except Exception as exc:  # noqa: BLE001 - surface only the class
                # Only the exception type reaches the model, never its
                # message, which could carry an internal URL or path.
                content = f"tool failed ({type(exc).__name__})"
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


async def _capped_json(request: Request):
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_REQUEST_BYTES:
            return None
    try:
        return json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        return None


async def ask(request: Request):
    body = await _capped_json(request)
    if body is None:
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


_FLOW_CACHE: dict[tuple, tuple[float, dict | None]] = {}


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

    async def cached_flow(lat, lon):
        key = (round(lat, 3), round(lon, 3))
        hit = _FLOW_CACHE.get(key)
        if hit and time.monotonic() - hit[0] < 90:
            return hit[1]
        sample = await tomtom_feed.flow_at_point(road.client, lat, lon)
        if len(_FLOW_CACHE) > 800:
            _FLOW_CACHE.clear()
        _FLOW_CACHE[key] = (time.monotonic(), sample)
        return sample

    samples = await asyncio.gather(*(
        cached_flow(lat, lon) for lat, lon in pairs
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


_STATICMAP_CACHE: dict[tuple, tuple[float, bytes]] = {}
_STATICMAP_TTL = 6 * 3600.0
_STATICMAP_MAX = 200
_STATICMAP_W, _STATICMAP_H = 560, 300
_STATICMAP_COLORS = {
    "incident": (201, 97, 26), "closure": (160, 44, 44),
    "chain": (43, 108, 176), "fire": (217, 119, 6),
}


async def api_staticmap(request: Request):
    """Small server-composed map image for alert emails: the same CARTO
    raster tiles the site uses, with the event marked. Email clients
    cannot run Leaflet, so the server does the compositing; results are
    cached because Gmail's image proxy refetches per open."""
    try:
        z = int(request.query_params.get("z", "11"))
        lat = float(request.query_params["lat"])
        lon = float(request.query_params["lon"])
    except (KeyError, ValueError):
        return JSONResponse({"error": "lat and lon required"}, status_code=400)
    if not (5 <= z <= 15 and 31.0 <= lat <= 43.5 and -126.5 <= lon <= -112.5):
        return Response(status_code=404)
    kind = request.query_params.get("k", "incident")
    color = _STATICMAP_COLORS.get(kind, _STATICMAP_COLORS["incident"])

    key = (z, round(lat, 3), round(lon, 3), kind)
    now = time.monotonic()
    hit = _STATICMAP_CACHE.get(key)
    if hit and now - hit[0] < _STATICMAP_TTL:
        return Response(hit[1], media_type="image/png",
                        headers={"Cache-Control": "public, max-age=21600"})

    import io
    import math as m

    from PIL import Image, ImageDraw

    n = 2 ** z
    xf = (lon + 180.0) / 360.0 * n
    yf = ((1.0 - m.log(m.tan(m.radians(lat))
                       + 1.0 / m.cos(m.radians(lat))) / m.pi) / 2.0 * n)
    cx, cy = xf * 256.0, yf * 256.0
    left, top = cx - _STATICMAP_W / 2, cy - _STATICMAP_H / 2
    tx0, ty0 = int(left // 256), int(top // 256)
    tx1 = int((left + _STATICMAP_W) // 256)
    ty1 = int((top + _STATICMAP_H) // 256)

    road = tools.get_road()

    async def fetch_tile(tx, ty):
        if not (0 <= ty < n):
            return tx, ty, None
        try:
            resp = await road.client.get(
                f"https://a.basemaps.cartocdn.com/rastertiles/voyager/"
                f"{z}/{tx % n}/{ty}.png",
                headers={"User-Agent": "ca-roads-mcp staticmap"},
                timeout=10,
            )
            return tx, ty, resp.content if resp.status_code == 200 else None
        except Exception:  # noqa: BLE001
            return tx, ty, None

    tiles = await asyncio.gather(*(
        fetch_tile(tx, ty)
        for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)
    ))

    def compose() -> bytes:
        canvas = Image.new("RGB", (_STATICMAP_W, _STATICMAP_H),
                           (229, 227, 223))
        for tx, ty, blob in tiles:
            if not blob:
                continue
            try:
                tile = Image.open(io.BytesIO(blob)).convert("RGB")
            except Exception:  # noqa: BLE001
                continue
            canvas.paste(tile, (int(tx * 256 - left), int(ty * 256 - top)))
        draw = ImageDraw.Draw(canvas)
        mx, my = _STATICMAP_W / 2, _STATICMAP_H / 2
        draw.ellipse([mx - 11, my - 11, mx + 11, my + 11],
                     fill=(255, 255, 255))
        draw.ellipse([mx - 8, my - 8, mx + 8, my + 8], fill=color)
        note = "(c) OpenStreetMap (c) CARTO"
        tw = draw.textlength(note)
        draw.rectangle([_STATICMAP_W - tw - 10, _STATICMAP_H - 16,
                        _STATICMAP_W, _STATICMAP_H],
                       fill=(255, 255, 255))
        draw.text((_STATICMAP_W - tw - 5, _STATICMAP_H - 13), note,
                  fill=(90, 100, 110))
        out = io.BytesIO()
        canvas.save(out, format="PNG", optimize=True)
        return out.getvalue()

    png = await asyncio.to_thread(compose)
    if len(_STATICMAP_CACHE) >= _STATICMAP_MAX:
        oldest = sorted(_STATICMAP_CACHE.items(), key=lambda kv: kv[1][0])
        for k, _ in oldest[: _STATICMAP_MAX // 4]:
            _STATICMAP_CACHE.pop(k, None)
    _STATICMAP_CACHE[key] = (now, png)
    return Response(png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=21600"})


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
                    "kind": "incident", "id": i.id,
                    "lat": i.lat, "lon": i.lon,
                    "type": i.log_type, "location": i.location,
                    "area": i.area,
                    "dir": direction_hint(i.location),
                    "reported": (i.reported_at.isoformat()
                                 if i.reported_at else None),
                    # Lets the popup offer "Show dispatch log" only when
                    # the feed actually shared timeline entries.
                    "log_n": len(i.details) + len(i.units),
                })
    if "closure" in want:
        # One marker per stretch: Caltrans lists each scheduled window
        # of each closure separately, so the same spot can carry a full
        # closure and several lane-closure windows at once. Keep the
        # most severe class currently listed there and count the rest.
        cls_rank = {"full-roadway": 3, "one-way-traffic": 2,
                    "alternating-lanes": 2, "lane": 1, "other": 1,
                    "ramp": 0}
        strips: dict = {}
        for c in lcs.records:
            if not inside(c.begin_lat, c.begin_lon):
                continue
            cls = lcs_feed.closure_class(c)
            key = (c.route, c.direction,
                   round(c.begin_lat, 3), round(c.begin_lon, 3))
            rank = (cls_rank.get(cls, 1), c.end_epoch or 0)
            entry = strips.get(key)
            if entry and entry[0] >= rank:
                entry[2] += 1
                continue
            marker = {
                "kind": "lane_closure", "lat": c.begin_lat,
                "lon": c.begin_lon,
                "label": lcs_feed.describe(c),
                "cls": cls,
                "route": c.route, "county": c.county,
                "lanes": lcs_feed.lanes_summary(c),
                "work": c.type_of_work or None,
                "facility": c.facility or None,
                "delay_min": c.estimated_delay_minutes or None,
                "since": c.epoch_1097 or c.start_epoch or None,
                "until": None if c.indefinite_end else (c.end_epoch or None),
            }
            # A closure with a distinct endpoint (> ~200 m away)
            # ships both ends so the map can draw the stretch, not
            # just a dot at the beginning. When the background
            # snapper has road-following geometry, that ships too
            # and the client prefers it over the straight line.
            if _closure_has_stretch(c):
                marker["end"] = [round(c.end_lat, 5),
                                 round(c.end_lon, 5)]
                snapped = _CLOSURE_PATHS.get(_closure_key(c))
                if snapped:
                    marker["path"] = snapped
            strips[key] = [rank, marker, (entry[2] + 1) if entry else 1]
        for _, marker, count in strips.values():
            if count > 1:
                marker["windows"] = count
            markers.append(marker)
    if "chain" in want:
        for c in cc.records:
            if inside(c.lat, c.lon):
                markers.append({
                    "kind": "chain_control", "lat": c.lat, "lon": c.lon,
                    "status": c.status, "route": c.route,
                    "label": c.description,
                    "updated": (c.status_updated_at.isoformat()
                                if c.status_updated_at else None),
                })
    fire_markers = []
    if "fire" in want:
        for f in wf.records:
            if inside(f.lat, f.lon):
                fire_markers.append({
                    "kind": "wildfire", "lat": f.lat, "lon": f.lon,
                    "name": f.name, "acres": f.size_acres,
                    "contained": f.percent_contained,
                    "discovered": (f.discovered_at.isoformat()
                                   if f.discovered_at else None),
                })
        # Footprints ride along whenever fires match: it is one bbox
        # query with server-side simplification (~500m offset) however
        # many fires there are, cached per bbox tile. Most small fires
        # have no perimeter record; the ones that do get a polygon.
        if fire_markers:
            key = (round(lat_min, 1), round(lon_min, 1),
                   round(lat_max, 1), round(lon_max, 1))
            cached = _PERIM_CACHE.get(key)
            if cached and time.monotonic() - cached[0] < 600:
                perims = cached[1]
            else:
                # Fine offset (~80m) because the map draws these shapes;
                # the coarse default is for distance estimation only.
                perims = await wildfire_feed.perimeters_in_bbox(
                    road.client, lat_min - 0.2, lon_min - 0.2,
                    lat_max + 0.2, lon_max + 0.2, max_offset=0.0008)
                _PERIM_CACHE[key] = (time.monotonic(), perims)
            by_name = {calfire_feed.normalize_fire_name(p["name"]): p
                       for p in perims if p["name"]}
            for m in fire_markers:
                perim = by_name.get(
                    calfire_feed.normalize_fire_name(m["name"] or ""))
                if perim:
                    pts = perim["points"]
                    step = max(1, len(pts) // 400)
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
                    "lines": s.text.split(" / ") if s.text else [],
                }
                if not s.text:
                    marker["blank"] = True
                markers.append(marker)

    # Out-of-state expansion feeds ride along only when the viewport
    # actually touches those states, so California browsing pays nothing.
    with contextlib.suppress(Exception):  # expansion states never break CA
        markers.extend(await states.markers_for_bbox(road.client, box, want))

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


async def api_sources(request: Request):
    """Live health of every data source, for the topbar status panel.
    All feeds are cache-backed, so this is cheap to serve."""
    road = tools.get_road()
    chp, lcs, cc, wf, cams, signs, wx = await asyncio.gather(
        road.incidents(), road.lane_closures(), road.chain_controls(),
        road.wildfires(), road.cameras(), road.message_signs(),
        road.road_weather(),
    )

    def one(name: str, agency: str, r) -> dict:
        return {
            "name": name, "agency": agency, "state": "California",
            "ok": bool(r.ok), "stale": bool(getattr(r, "stale", False)),
            "as_of": r.data_as_of.isoformat() if r.data_as_of else None,
            "count": len(r.records),
            "error": (str(r.error)[:160] if r.error else None),
        }

    sources = [
        one("Incidents", "CHP", chp),
        one("Lane closures", "Caltrans LCS", lcs),
        one("Chain controls", "Caltrans", cc),
        one("Wildfires", "WFIGS + CAL FIRE", wf),
        one("Cameras", "Caltrans CCTV", cams),
        one("Message signs", "Caltrans CMS", signs),
        one("Road weather", "Caltrans RWIS", wx),
        {"name": "Weather alerts", "agency": "NWS", "state": "Nationwide",
         "on_demand": True},
        {"name": "Earthquakes", "agency": "USGS", "state": "Nationwide",
         "on_demand": True},
        {"name": "Traffic speeds", "agency": "TomTom", "state": "Nationwide",
         "enabled": bool(os.environ.get("TOMTOM_API_KEY"))},
        {"name": "Bay Area events", "agency": "511 SF Bay",
         "state": "California",
         "enabled": bool(os.environ.get("BAY511_API_KEY"))},
        {"name": "Nevada continuations", "agency": "NV DOT",
         "state": "Nevada",
         "enabled": bool(os.environ.get("NVROADS_API_KEY"))},
    ]
    sources.extend(states.source_status())
    return JSONResponse({
        "checked_at": datetime.now(UTC).isoformat(),
        "sources": sources,
    })


async def api_stcam(request: Request):
    """Snapshot frame for an expansion-state camera. NE Compass embeds
    JPEG bytes in its XML instead of hosting image URLs, so the map
    serves them from the in-process cache filled by the camera feed."""
    code = request.path_params.get("state", "")
    cam_id = request.path_params.get("cam_id", "")
    if code not in states.NEC_STATES or not (1 <= len(cam_id) <= 120):
        return JSONResponse({"error": "not found"}, status_code=404)
    frame = states.snapshot(code, cam_id)
    if frame is None:
        return JSONResponse({"error": "no current frame"}, status_code=404)
    return Response(frame, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=120"})


async def api_incident(request: Request):
    """Full dispatch log for one CHP incident, straight from the cached
    feed. Fetched lazily when someone opens 'Show dispatch log' in a
    popup, so the map payload stays light."""
    iid = request.path_params.get("incident_id", "")
    if not (iid.isascii() and iid.isalnum() and 4 <= len(iid) <= 32):
        return JSONResponse({"error": "bad id"}, status_code=400)
    chp = await tools.get_road().incidents()
    for i in chp.records:
        if i.id == iid:
            return JSONResponse({
                "id": i.id,
                "type": i.log_type,
                "location": i.location,
                "location_desc": i.location_desc,
                "area": i.area,
                "reported": (i.reported_at.isoformat()
                             if i.reported_at else None),
                "details": [list(d) for d in i.details],
                "units": [list(u) for u in i.units],
                "data_as_of": (chp.data_as_of.isoformat()
                               if chp.data_as_of else None),
            })
    return JSONResponse({"error": "not found"}, status_code=404)


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
    body = await _capped_json(request)
    if body is None:
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


# The admin page lives at a secret, unguessable path in production (ADMIN_PATH);
# /admin then simply 404s. This obscurity sits on top of the real gate: every
# admin API call is still verified server-side against ADMIN_EMAILS.
ADMIN_PAGE_PATH = "/" + os.environ.get("ADMIN_PATH", "admin").strip("/")


async def privacy_page(_: Request):
    return FileResponse(STATIC_DIR / "privacy.html")


async def terms_page(_: Request):
    return FileResponse(STATIC_DIR / "terms.html")


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
    fourteen feeds itself. Failures are fine - the request path retries."""
    road = tools.get_road()
    with contextlib.suppress(Exception):
        await asyncio.gather(
            road.incidents(), road.lane_closures(), road.chain_controls(),
            road.wildfires(), road.cameras(), road.message_signs(),
            road.road_weather(),
            return_exceptions=True,
        )
    # Expansion states warm after California so the default nationwide
    # view lands on hot caches for every region.
    with contextlib.suppress(Exception):
        await states.prewarm(road.client)


# Road-following geometry for closure stretches, keyed by rounded
# begin/end coordinates. Filled by a background loop at OSRM public-
# server pace (about one request per second) and shared by every
# visitor; a missing or None entry falls back to the straight line.
_CLOSURE_PATHS: dict[tuple, list | None] = {}
_SNAP_MIN_DELTA = 0.002  # same threshold mapdata uses for "has an end"


def _closure_key(c) -> tuple:
    return (round(c.begin_lat, 4), round(c.begin_lon, 4),
            round(c.end_lat, 4), round(c.end_lon, 4))


def _closure_has_stretch(c) -> bool:
    return bool(c.end_lat and c.end_lon
                and (abs(c.end_lat - c.begin_lat) > _SNAP_MIN_DELTA
                     or abs(c.end_lon - c.begin_lon) > _SNAP_MIN_DELTA))


def _snap_path(coords: list, straight_km: float,
               route_km: float) -> list | None:
    """Downsampled [lat, lon] path, or None when the route is suspect.

    A snapped route much longer than the crow-flies distance means OSRM
    had to wander (endpoints on different roads, one-way detours): the
    straight line misleads less than a tour of the county."""
    if len(coords) < 2 or straight_km <= 0:
        return None
    if route_km > max(3 * straight_km, straight_km + 8):
        return None
    step = max(1, len(coords) // 60)
    path = [[round(lat, 5), round(lon, 5)] for lon, lat in coords[::step]]
    last = [round(coords[-1][1], 5), round(coords[-1][0], 5)]
    if path[-1] != last:
        path.append(last)
    return path


async def _snap_closures_loop() -> None:
    """Every five minutes, fetch road geometry for closure stretches the
    cache does not know yet, then drop entries for closures that ended."""
    road = tools.get_road()
    while True:
        with contextlib.suppress(Exception):
            lcs = await road.lane_closures()
            fresh = [c for c in lcs.records if _closure_has_stretch(c)
                     and _closure_key(c) not in _CLOSURE_PATHS]
            for c in fresh[:120]:
                path = None
                with contextlib.suppress(Exception):
                    resp = await road.client.get(
                        "https://router.project-osrm.org/route/v1/driving/"
                        f"{c.begin_lon},{c.begin_lat};{c.end_lon},{c.end_lat}",
                        params={"overview": "full", "geometries": "geojson"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        routes = resp.json().get("routes") or []
                        if routes:
                            coords = (routes[0].get("geometry") or {}).get(
                                "coordinates") or []
                            straight = watch.haversine_km(
                                c.begin_lat, c.begin_lon,
                                c.end_lat, c.end_lon)
                            path = _snap_path(
                                coords, straight,
                                (routes[0].get("distance") or 0) / 1000)
                _CLOSURE_PATHS[_closure_key(c)] = path
                await asyncio.sleep(1.1)
            current = {_closure_key(c) for c in lcs.records
                       if _closure_has_stretch(c)}
            for key in list(_CLOSURE_PATHS):
                if key not in current:
                    _CLOSURE_PATHS.pop(key, None)
        await asyncio.sleep(300)


@contextlib.asynccontextmanager
async def _lifespan(app_):
    task = asyncio.create_task(_prewarm())
    snap_task = asyncio.create_task(_snap_closures_loop())
    yield
    task.cancel()
    snap_task.cancel()


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
        Route("/api/staticmap", api_staticmap, methods=["GET"]),
        Route("/api/mapdata", api_mapdata, methods=["GET"]),
        Route("/api/incident/{incident_id}", api_incident, methods=["GET"]),
        Route("/api/stcam/{state}/{cam_id:path}", api_stcam, methods=["GET"]),
        Route("/watch", watch_page),
        Route(ADMIN_PAGE_PATH, admin_page),
        Route("/api/admin/analytics", analytics.api_admin_analytics,
              methods=["GET"]),
        Route("/api/admin/feedback", analytics.api_admin_feedback,
              methods=["GET"]),
        Route("/api/sources", api_sources, methods=["GET"]),
        Route("/privacy", privacy_page),
        Route("/terms", terms_page),
        Route("/trip/{trip_id}", trips.trip_page),
        Route("/api/trip", trips.api_trip_create, methods=["POST"]),
        Route("/api/trip/{trip_id}", trips.api_trip_get),
        Route("/sw.js", sw_js),
        Route("/manifest.webmanifest", manifest_file),
        Route("/api/watch/config", watch.api_watch_config, methods=["GET"]),
        Route("/api/watch/me", watch.api_watch_me, methods=["GET"]),
        Route("/api/watch/redeem", watch.api_watch_redeem, methods=["POST"]),
        Route("/api/watch/create", watch.api_watch_create, methods=["POST"]),
        Route("/api/watch/push", watch.api_push_subscribe, methods=["POST"]),
        Route("/api/watch/account", watch.api_account_delete,
              methods=["DELETE"]),
        Route("/api/watch/test", watch.api_watch_test, methods=["POST"]),
        Route("/api/watch/{watch_id}", watch.api_watch_delete,
              methods=["DELETE"]),
        Route("/api/watch/{watch_id}", watch.api_watch_update,
              methods=["PATCH"]),
        Route("/api/admin/overview", watch.api_admin_overview,
              methods=["GET"]),
        Route("/api/admin/user", watch.api_admin_user, methods=["POST"]),
        Route("/api/admin/code", watch.api_admin_code, methods=["POST"]),
        Route("/api/check-watches", watch.api_check_watches,
              methods=["POST"]),
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]
)
# Request-level limiter on top of the daily caps (burst 20, ~30/min
# sustained): normal browsing fires event beacons and watch-API calls
# from the same per-IP bucket, and burst-5 tuning rate-limited real
# users mid-session. Dollar protection lives in the daily caps.
MAX_REQUEST_BYTES = 256 * 1024


class BodyLimit:
    """Reject oversized request bodies at the door so a single 512 MiB
    instance cannot be OOM'd by a large POST."""

    def __init__(self, app_):
        self.app = app_

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") in ("POST", "PUT",
                                                                "PATCH"):
            cl = dict(scope.get("headers") or {}).get(b"content-length")
            if cl and cl.isdigit() and int(cl) > MAX_REQUEST_BYTES:
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type",
                                         b"application/json")]})
                await send({"type": "http.response.body",
                            "body": b'{"error": "request too large"}'})
                return
        await self.app(scope, receive, send)


class SecurityHeaders:
    """Baseline hardening headers on every response: no MIME sniffing,
    no framing (clickjacking), tight referrers, and geolocation only
    for this origin. No cookies exist, so there is no CSRF surface."""

    # Content-Security-Policy: the pages use inline scripts, so
    # script-src keeps 'unsafe-inline' - but everything an injected
    # payload would want (loading external code, framing us, exfil to
    # an arbitrary host, rewriting <base>, posting a form elsewhere) is
    # locked to a fixed allowlist of the hosts we actually use.
    CSP = (
        "default-src 'self'; "
        "base-uri 'none'; "
        "object-src 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "script-src 'self' 'unsafe-inline' https://www.gstatic.com "
        "https://apis.google.com https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        # cwwp2.dot.ca.gov serves the Caltrans camera snapshots; without it
        # here the browser blocks every popup image and cameras all read
        # "snapshot unavailable".
        "img-src 'self' data: https://*.basemaps.cartocdn.com "
        "https://*.cartocdn.com https://cwwp2.dot.ca.gov "
        # Expansion-state camera hosts (WSDOT, TripCheck, OHGO).
        "https://images.wsdot.wa.gov https://*.tripcheck.com "
        "https://itscameras.dot.state.oh.us "
        "https://cctv.travelmidwest.com https://api.algotraffic.com "
        # TravelMidwest aggregates cameras from neighboring states' hosts.
        "https://*.lakecountypassage.com https://content.trafficwise.org "
        "https://511wi.gov https://*.trimarc.org "
        "https://atmsqf.iowadot.gov; "
        "connect-src 'self' https://router.project-osrm.org "
        "https://valhalla1.openstreetmap.de https://*.googleapis.com "
        "https://*.google.com https://cloudflareinsights.com "
        "https://*.gstatic.com; "
        "frame-src https://ca-roads-mcp.firebaseapp.com "
        "https://accounts.google.com https://apis.google.com; "
        "worker-src 'self'; manifest-src 'self'"
    )
    HEADERS = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy",
         b"geolocation=(self), camera=(), microphone=(), payment=()"),
        (b"content-security-policy", CSP.encode()),
        (b"strict-transport-security",
         b"max-age=31536000; includeSubDomains"),
        (b"cross-origin-opener-policy", b"same-origin-allow-popups"),
    ]

    def __init__(self, app_):
        self.app = app_

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_secure(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend(self.HEADERS)
            await send(message)

        await self.app(scope, receive, send_secure)


class SoftLimit:
    """A second, roomier bucket for endpoints exempt from the strict
    limiter because normal browsing hits them constantly - but which
    still burn upstream quota (TomTom, CARTO, OSM geocoders) or CPU
    when scripted. Sixty-burst at two per second never touches a
    human; it stops a curl loop."""

    PREFIXES = ("/api/suggest", "/api/geocode", "/api/flow",
                "/api/staticmap", "/api/traffictile")

    def __init__(self, app_):
        self.app = app_
        self.limiter = RateLimiter(capacity=60, refill_per_second=2.0)

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http"
                and scope.get("path", "").startswith(self.PREFIXES)):
            headers = dict(scope.get("headers") or [])
            fwd = (headers.get(b"x-forwarded-for") or b"").decode() or None
            client = scope.get("client")
            ip = trusted_client_ip(fwd, client[0] if client else None)
            if not self.limiter.allow(ip):
                await send({"type": "http.response.start", "status": 429,
                            "headers": [(b"content-type",
                                         b"application/json")]})
                await send({"type": "http.response.body",
                            "body": b'{"error": "slow down"}'})
                return
        await self.app(scope, receive, send)


class StaticCacheHeaders:
    """Vendored assets (Leaflet, fonts, icons) almost never change:
    let browsers keep them for a week instead of revalidating every
    page view. HTML and API responses are untouched."""

    def __init__(self, app_):
        self.app = app_

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        cacheable = scope["type"] == "http" and (
            path.startswith(("/static/vendor/", "/static/fonts/"))
            or path.startswith("/static/icon-"))

        async def send_with_cache(message):
            if cacheable and message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"cache-control",
                                b"public, max-age=604800, immutable"))
            await send(message)

        await self.app(scope, receive, send_with_cache if cacheable else send)


app = BodyLimit(app)
app = SoftLimit(app)
app = StaticCacheHeaders(app)
app = RateLimitMiddleware(
    app,
    RateLimiter(capacity=20, refill_per_second=0.5),
    # The bucket protects the model-spending path (/api/ask) and event
    # spam. Data-plane GETs are cheap, feed-cached, and the standalone map
    # legitimately calls them on every pan - throttling them starves
    # address validation behind map browsing.
    exempt_prefixes=("/static/", "/logo.svg", "/health", "/favicon",
                     "/api/mapdata", "/api/stats", "/api/geocode",
                     "/api/incident/", "/api/sources", "/api/stcam/",
                     "/api/suggest", "/api/flow", "/api/traffictile",
                     # Watch pages + public bootstrap config are as cheap
                     # as static files; the mutating watch APIs stay
                     # inside the bucket (and are token-gated anyway).
                     "/watch", ADMIN_PAGE_PATH, "/sw.js", "/manifest.webmanifest",
                     "/privacy", "/terms", "/trip/", "/api/trip",
                     "/api/watch/config", "/api/staticmap"),
)
app = SecurityHeaders(app)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8081)))


if __name__ == "__main__":
    main()
