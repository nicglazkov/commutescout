# The MCP server

CommuteScout exposes its entire data layer as an MCP server, so Claude
(or any MCP client) can answer questions about California roads with
live data instead of guesses.

## Connect to the hosted server

Add a custom connector with this URL (streamable HTTP):

```
https://mcp.commutescout.com/mcp
```

No key or account needed. It is the same server behind
[commutescout.com](https://commutescout.com), with the same live feeds.

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
| `check_route(from_place, to_place)` | Everything active along a major corridor (17 curated corridors: I-80 Sacramento-Reno, US-50 to Tahoe, I-5, US-101, SR-17, SR-99, SR-1, I-15 to Vegas, Bay Area freeways, Tahoe locals), ordered by miles along the route |
| `check_region(region)` | One-call report for a whole region (Bay Area, SoCal, Sierra, Central Valley, and four more): exact counts, incidents severity-sorted, full closures first, capped lists that say when they truncate |
| `get_incidents(highway?, area?, center?)` | Live CHP incidents by route, dispatch area, or a point and radius |
| `get_lane_closures(route?, district?, center?)` | Closures in place right now, classified per the [closure taxonomy](data-sources.md#the-closure-taxonomy) |
| `get_chain_controls(route?, center?)` | Current chain requirements; says "none active" explicitly in the off-season |
| `get_wildfires(near_route?, center?)` | Active fires with size, containment, and mapped perimeter edges, flagged near major highways |
| `get_cameras(center?, route?)` | Roadside camera snapshots, each verified live before it is returned (offline placeholder frames are filtered by image freshness) |
| `get_road_signs(route?, center?)` | What changeable message signs are displaying right now, verbatim |
| `rank_routes(by?, limit?)` | All 17 corridors ranked by live events or measured congestion, with reasons; answers "what are the busiest routes right now" |

Route and region reports also carry context that changes the advice:
weather alerts sampled along the trip, road-weather stations reporting
something notable, recent significant earthquakes, the signs and
cameras along the way, and live speeds when a TomTom key is set. Route
names are normalized ("17", "hwy 50", "I80" all work), and docstrings
are written for the LLM consumer: what the data is, its refresh
cadence, and its limits.

## How good are the answers?

An eval suite with recorded fixtures and 91 golden questions gates
every release; the scorecard is public. See [EVALS.md](../EVALS.md).

## Registry

The server is published as `io.github.nicglazkov/commutescout`
(see [server.json](../server.json) and [registry notes](registry.md)).
