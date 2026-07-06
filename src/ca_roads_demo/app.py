"""Demo backend: a small Starlette app that answers road questions.

POST /api/ask runs Claude Haiku in a tool loop against the same five tool
functions the MCP server exposes, and streams the answer as SSE. Hard cost
guards: per-IP rate limit, per-IP daily question cap, and a global daily
dollar cap, all in process (single Cloud Run instance for v1).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import anthropic
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

from ca_roads_mcp import server as tools
from ca_roads_mcp.ratelimit import RateLimiter, RateLimitMiddleware

MODEL = os.environ.get("DEMO_MODEL", "claude-sonnet-5")
MAX_QUESTION_CHARS = 300
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
- Use check_route for trip questions between two places; use the filtered
  tools for single-road or single-area questions.
- Be concise and practical for a driver. Lead with the answer.
- State how fresh the data is (data_as_of) and mention any feed problems.
- You report current status, not forecasts.
- End with: "Verify before you drive: 511 or quickmap.dot.ca.gov."
"""

TOOL_DEFS = [
    {
        "name": "check_route",
        "description": (
            "Current conditions along a major California corridor between two "
            "places: incidents, lane closures in place, chain controls, and "
            "wildfires near the route, ordered along the route with a summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_place": {"type": "string"},
                "to_place": {"type": "string"},
            },
            "required": ["from_place", "to_place"],
        },
    },
    {
        "name": "get_incidents",
        "description": (
            "Live CHP incidents statewide. Optional filters: highway (e.g. "
            "'I-80', '17'), area (CHP dispatch area substring), center "
            "('lat,lon') with radius_km."
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
            "Optional filters: route, district (1-12)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "route": {"type": "string"},
                "district": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_chain_controls",
        "description": (
            "Current chain-control levels (R-1/R-2/R-3) on mountain highways. "
            "Optional filter: route."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"route": {"type": "string"}},
        },
    },
    {
        "name": "get_wildfires",
        "description": (
            "Active California wildfires with size and containment, flagged "
            "when within ~10 miles of major highways. Optional: near_route."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"near_route": {"type": "string"}},
        },
    },
]

TOOL_FUNCS = {
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
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def answer_stream(question: str):
    client = get_client()
    messages = [{"role": "user", "content": question}]
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

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            yield _sse({"done": True})
            return
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            func = TOOL_FUNCS.get(block.name)
            try:
                result = await func(**block.input) if func else {"error": "unknown tool"}
                content = json.dumps(result, default=str)
                is_error = False
            except Exception as exc:  # noqa: BLE001 - surface tool failure to the model
                content = f"tool failed: {type(exc).__name__}: {exc}"
                is_error = True
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                }
            )
            yield _sse({"tool": block.name})
        messages.append({"role": "user", "content": results})
    yield _sse({"text": "\n(Stopped: too many lookups for one question.)"})
    yield _sse({"done": True})


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
    blocked = guards.try_start_question(client_ip(request))
    if blocked:
        return JSONResponse({"error": blocked}, status_code=429)
    return StreamingResponse(
        answer_stream(question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


STATIC_DIR = Path(__file__).parent / "static"


async def index(_: Request):
    return FileResponse(STATIC_DIR / "index.html")


async def healthz(_: Request):
    return JSONResponse({"ok": True})


app = Starlette(
    routes=[
        Route("/", index),
        Route("/healthz", healthz),
        Route("/api/ask", ask, methods=["POST"]),
    ]
)
# Request-level limiter on top of the daily caps (burst 5, ~6/min sustained).
app = RateLimitMiddleware(app, RateLimiter(capacity=5, refill_per_second=0.1))


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8081)))


if __name__ == "__main__":
    main()
