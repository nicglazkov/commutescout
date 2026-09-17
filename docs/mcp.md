# The MCP server

CommuteScout exposes its entire data layer as an MCP server, so Claude
(or any MCP client) can answer questions about US roads with live data
instead of guesses: California in the most depth, and live events
across every covered state.

## Connect to the hosted server

Add a custom connector with this URL (streamable HTTP):

```
https://mcp.commutescout.com/mcp
```

No key or account needed. It is the same server behind
[commutescout.com](https://commutescout.com), with the same live feeds.

## Plain HTTP, no MCP client

The full developer documentation (base URL, keys and limits, the error
envelope, conventions, every tool parameter by parameter, bulk snapshots
and what not to do) is at [commutescout.com/developers](https://commutescout.com/developers).
This section is the short version.

Every tool is also a `GET` on the same host, for scripts, dashboards and
anything that is not an MCP client:

```
https://mcp.commutescout.com/v1/tools/get_incidents?area=Redwood%20City
https://mcp.commutescout.com/v1/tools/check_route?from_place=Sacramento&to_place=Reno
```

Arguments are query parameters with the same names as the tool
parameters below; the body is the tool's JSON. The OpenAPI document is
generated from the tools' own schemas at
[`/v1/openapi.json`](https://mcp.commutescout.com/v1/openapi.json), with
a browsable reference at [`/v1/docs`](https://mcp.commutescout.com/v1/docs)
and an index at [`/v1`](https://mcp.commutescout.com/v1). Errors come back
as `{"error": {"code", "message", "hint"}}` with a 400, 404 or 429;
every response allows cross-origin reads. The same per-address rate limits
apply as on `/mcp`. Changes within `/v1` are additive.

### Keys

Without a key, both `/v1` and `/mcp` work at the per-address limits.
A key lifts a client onto its own limits and needs a signed-in account:
open the live map, choose Settings in the rail, sign in, and create a
key under API keys. Send it as `Authorization: Bearer cs_live_...` or
`X-API-Key`. Free keys get 2,000 requests a day and 30 in a burst; Pro
keys get 10,000 a day and 60 in a burst; ask through the contact page
for more. Every keyed response carries `RateLimit-Limit` and
`RateLimit-Remaining`; a spent day answers 429 with `Retry-After`. A
revoked or unknown key answers 401 rather than falling back to keyless.

## Run it locally (stdio)

The server is a single Python package with zero required keys. Config
for Claude Desktop or Claude Code:

```json
{
  "mcpServers": {
    "commutescout": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nicglazkov/commutescout", "ca-roads-mcp"]
    }
  }
}
```

From a checkout: `pip install .` then `ca-roads-mcp` for stdio, or
`ca-roads-mcp --transport http` for streamable HTTP on `$PORT`. The
http transport is tuned for Cloud Run (binds 0.0.0.0, host-header
checks off), so bind it to localhost when running it on your machine:
`ca-roads-mcp --transport http --host 127.0.0.1`.

## Tools

| Tool | What it answers |
|------|-----------------|
| `check_route(from_place, to_place, from_coords?, to_coords?)` | Everything active along a major corridor (17 curated corridors: I-80 Sacramento-Reno, US-50 to Tahoe, I-5, US-101, SR-17, SR-99, SR-1, I-15 to Vegas, Bay Area freeways, Tahoe locals), ordered by miles along the route |
| `check_region(region)` | One-call report for a whole region (Bay Area, SoCal, Sierra, Central Valley, and four more): exact counts, incidents severity-sorted, full closures first, capped lists that say when they truncate |
| `get_incidents(highway?, area?, center?, radius_km?)` | Live CHP incidents by route, dispatch area, or a point and radius |
| `get_lane_closures(route?, district?, center?, radius_km?)` | Closures in place right now, classified per the [closure taxonomy](data-sources.md#the-closure-taxonomy) |
| `get_chain_controls(route?, center?, radius_km?)` | Current chain requirements; says "none active" explicitly in the off-season |
| `get_wildfires(near_route?, center?, radius_km?)` | Active fires with size, containment, and mapped perimeter edges, flagged near major highways |
| `get_cameras(center?, route?, radius_km?, limit?)` | Roadside camera snapshots, each verified live before it is returned (offline placeholder frames are filtered by image freshness) |
| `get_road_signs(route?, center?, radius_km?)` | What changeable message signs are displaying right now, verbatim |
| `rank_routes(by?, limit?)` | All 17 corridors ranked by live events or measured congestion, with reasons; answers "what are the busiest routes right now" |
| `get_nearby_events(center, radius_km?, kinds?)` | Live road events near a point across every covered state, 37 states, not just California (California's own feeds are included); the tool for locations outside California or near a state border |

Parameter notes: `center` is `"lat,lon"`; `radius_km` caps at 160 on
`get_nearby_events`; `get_cameras` returns at most 10 verified cameras
per call; `get_lane_closures` returns at most 200 closures and says
when it truncates; pass `from_coords` and `to_coords` to `check_route`
whenever you have them (they skip geocoding). The hosted server allows
20 requests in a burst, 30 per minute sustained, and 2,000 per day per
client address.

Route and region reports also carry context that changes the advice:
weather alerts sampled along the trip, road-weather stations reporting
something notable, recent significant earthquakes, the signs and
cameras along the way, and live speeds when a TomTom key is set. Route
names are normalized ("17", "hwy 50", "I80" all work), and docstrings
are written for the LLM consumer: what the data is, its refresh
cadence, and its limits.

## How good are the answers?

An eval suite with recorded fixtures and 91 golden questions scores the
assistant. Runs are triggered manually rather than on every release,
and the scorecard is public. See [EVALS.md](../EVALS.md).

## Registry

The server is published as `io.github.nicglazkov/commutescout`
(see [server.json](../server.json) and [registry notes](registry.md)).
