# The MCP server

CommuteScout exposes its entire data layer as an MCP server, so Claude
(or any MCP client) can answer questions about US roads with live data
instead of guesses: the same trip, weather, traffic and live-event
tools in every covered state, plus extra California-only corridor
tools.

## Connect to the hosted server

The endpoint is streamable HTTP and stateless:

```
https://mcp.commutescout.com/mcp
```

Every request needs a CommuteScout API key. Keys are free: open
[the map](https://commutescout.com/map), choose Settings, sign in, and
create one under API keys (2,000 requests a day). Send it as
`Authorization: Bearer cs_live_...` or `X-API-Key: cs_live_...`. Without
one, the server answers HTTP 401 with a JSON-RPC error (code `-32001`,
`data.code` `missing_key`) that says where to get a key. It is the same
server behind [commutescout.com](https://commutescout.com), with the same
live feeds.

The easiest way, in any client, is your **personal link**: `https://mcp.commutescout.com/mcp/cs_live_...`
with your key in place of `cs_live_...`. It is the endpoint with the key as
the last path segment ([`keyurl.py`](../src/ca_roads_mcp/keyurl.py) moves it
into the `Authorization` header), so it works in apps that cannot send a
header, such as ChatGPT and claude.ai. The link contains your key: keep it
private, and delete the key under Settings > API keys if it leaks.
`/mcp?key=cs_live_...` works the same way.

| Client | How to add it |
|--------|---------------|
| ChatGPT | Plugins > + > Add custom MCP server, URL: your personal link, Authentication: No authentication |
| claude.ai and Claude Desktop | Customize > Connectors > + Add > Add custom connector, URL: your personal link, Sign-in: No sign in |
| Claude Code | `claude mcp add --transport http --scope user commutescout https://mcp.commutescout.com/mcp/cs_live_...`, then `/mcp` to confirm |
| Cursor | One-click "Add to Cursor" on the site, or `~/.cursor/mcp.json`: `{"mcpServers": {"commutescout": {"url": "https://mcp.commutescout.com/mcp/cs_live_..."}}}` |
| VS Code (Copilot) | One-click "Add to VS Code" on the site, or MCP: Add Server > HTTP with your personal link |
| Windsurf | `mcp_config.json`: `{"mcpServers": {"commutescout": {"serverUrl": "https://mcp.commutescout.com/mcp/cs_live_..."}}}` |
| OpenAI Codex CLI | `codex mcp add commutescout --url https://mcp.commutescout.com/mcp/cs_live_...` |
| Gemini CLI | `gemini mcp add --transport http commutescout https://mcp.commutescout.com/mcp/cs_live_...` |
| stdio-only clients | `npx mcp-remote https://mcp.commutescout.com/mcp/cs_live_... --transport http-only` |

Clients that can send headers can still use the plain endpoint with
`Authorization: Bearer cs_live_...`, which keeps the key out of the URL.

The full steps, including where each client takes the key, are
on [commutescout.com/mcp](https://commutescout.com/mcp#connect). The same
steps as plain text for agents are served at
[commutescout.com/llms.txt](https://commutescout.com/llms.txt) and
[mcp.commutescout.com/llms.txt](https://mcp.commutescout.com/llms.txt),
and as a server card at
[`/.well-known/mcp/server-card.json`](https://mcp.commutescout.com/.well-known/mcp/server-card.json).
All of them render from [`connect.py`](../src/ca_roads_mcp/connect.py).

Check the connection with a question such as "When should I leave Union
Station in Denver for Red Rocks tomorrow?". The assistant should call
`best_time_to_go`.

### Your places

The key also tells the trip tools whose "home", "work" and saved places
to read. With it connected, "When should I leave for the airport?" starts from your Home, and
"from work to the gym" uses your saved Work and the favorite named Gym.
Places are read only for the account that owns the key. A self-hosted
server can set `MCP_HOME` and `MCP_WORK` ("lat,lon" or an address)
instead. No MCP server can see your device's location: for "from here",
the model passes coordinates it already has or asks you.

## Plain HTTP, no MCP client

The full developer documentation (base URL, keys and limits, the error
envelope, conventions, every tool parameter by parameter, bulk snapshots
and what not to do) is at [commutescout.com/developers](https://commutescout.com/developers).
This section is the short version.

Every tool is also a `GET` on the same host, for scripts, dashboards and
anything that is not an MCP client:

```
https://mcp.commutescout.com/v1/tools/plan_trip?origin=Denver%2C%20CO&destination=Boulder%2C%20CO
https://mcp.commutescout.com/v1/tools/get_nearby_events?place=Columbus%2C%20OH&radius_km=30
```

Each call needs the key (`X-API-Key: cs_live_...` or
`Authorization: Bearer cs_live_...`).

Arguments are query parameters with the same names as the tool
parameters below; the body is the tool's JSON. The OpenAPI document is
generated from the tools' own schemas at
[`/v1/openapi.json`](https://mcp.commutescout.com/v1/openapi.json), with
a browsable reference at [`/v1/docs`](https://mcp.commutescout.com/v1/docs)
and an index at [`/v1`](https://mcp.commutescout.com/v1). Errors come back
as `{"error": {"code", "message", "hint"}}` with a 400, 401, 404 or 429;
every response allows cross-origin reads. The same per-account limits
apply as on `/mcp`. The OpenAPI document, `/v1`, `/v1/docs` and the
discovery files (`/llms.txt`, `/.well-known/mcp.json`) need no key.

### Keys

Tool calls on `/v1/tools/*` and every request to `/mcp` need a key,
which needs a signed-in account: open
[the live map](https://commutescout.com/map), choose Settings in the
rail, sign in, and create a key under API keys. Send it as `Authorization: Bearer cs_live_...` or
`X-API-Key`. Free keys get 2,000 requests a day and 30 in a burst; Pro
keys get 10,000 a day and 60 in a burst; ask through the contact page
for more. Every keyed response carries `RateLimit-Limit` and
`RateLimit-Remaining`; a spent day answers 429 with `Retry-After`. A
missing key answers 401 with code `missing_key`:

```json
{"error": {"code": "missing_key", "message": "An API key is required.",
  "hint": "Get a free key (2,000 requests a day) at https://commutescout.com/map: open Settings, sign in, then API keys. Send it as 'Authorization: Bearer cs_live_...' or 'X-API-Key: cs_live_...'."}}
```

A revoked or unknown key answers 401 with code `invalid_key`. On `/mcp`
both come back as a JSON-RPC error (code `-32001`) with the same code
and hint under `data`.

## Run it locally (stdio)

The server is a single Python package. Live events need no keys; the
trip tools (`plan_trip`, `best_time_to_go`, `find_place`) need
`STADIA_API_KEY` for routing and geocoding, and `get_traffic` and the
traffic-aware drive times need `TOMTOM_API_KEY`. Config for Claude
Desktop or Claude Code (needs [uv](https://docs.astral.sh/uv/)):

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
checks off, API key required on `/mcp` and `/v1/tools/*`), so bind it
to localhost and turn the key check off when running it on your machine
without Firestore:
`MCP_REQUIRE_KEY=0 ca-roads-mcp --transport http --host 127.0.0.1`.

## Tools

| Tool | What it answers |
|------|-----------------|
| `check_route(from_place, to_place, from_coords?, to_coords?)` | California only: Everything active along a major corridor (17 curated corridors: I-80 Sacramento-Reno, US-50 to Tahoe, I-5, US-101, SR-17, SR-99, SR-1, I-15 to Vegas, Bay Area freeways, Tahoe locals), ordered by miles along the route |
| `check_region(region)` | California only: One-call report for a whole region (Bay Area, SoCal, Sierra, Central Valley, and four more): exact counts, incidents severity-sorted, full closures first, capped lists that say when they truncate |
| `get_incidents(highway?, area?, center?, radius_km?)` | California only: Live CHP incidents by route, dispatch area, or a point and radius |
| `get_lane_closures(route?, district?, center?, radius_km?)` | California only: Closures in place right now, classified per the [closure taxonomy](data-sources.md#the-closure-taxonomy) |
| `get_chain_controls(route?, center?, radius_km?)` | California only: Current chain requirements; says "none active" explicitly in the off-season |
| `get_wildfires(near_route?, center?, radius_km?)` | California only: Active fires with size, containment, and mapped perimeter edges, flagged near major highways |
| `get_cameras(center?, route?, radius_km?, limit?)` | California only: Roadside camera snapshots, each verified live before it is returned (offline placeholder frames are filtered by image freshness) |
| `get_road_signs(route?, center?, radius_km?)` | California only: What changeable message signs are displaying right now, verbatim |
| `rank_routes(by?, limit?)` | California only: All 17 corridors ranked by live events or measured congestion, with reasons; answers "what are the busiest routes right now" |
| `get_nearby_events(center or place, radius_km?, kinds?)` | Live road events near a place in any of the 37 covered states, each naming its publishing agency; optional signs, road weather, cameras, tolls and speed and red-light cameras |
| `plan_trip(origin, destination, depart_at?, preference?)` | One drive between any two US places: drive time with traffic for that departure, alternatives, everything on the route in mile order, alerts and the arrival forecast |
| `best_time_to_go(origin, destination, day?, earliest?, latest?, arrive_by?, step_minutes?)` | Up to 16 departures compared on drive time, arrival weather and how often incidents start on the route that hour; a pick and the full curve |
| `find_place(query, near?, limit?)` | What a typed place resolves to, with alternatives |
| `get_weather(place or center, hours?)` | NWS alerts and the hourly forecast, with driving hazards flagged |
| `get_traffic(points, place or center)` | Live speed against free-flow around a point |
| `get_area_history(place or center, radius_km?, days?)` | When incidents usually happen near a place, by hour and day, from the event archive |
| `get_my_places()` | Your Home, Work, favorites and recent destinations (needs an API key) |
| `get_coverage()` | Which states and feeds are covered |

Every trip tool takes `"home"`, `"work"` or a saved place's name, and a
trip with no origin starts from Home.

The `check_route`, `check_region`, `rank_routes`, `get_incidents`,
`get_lane_closures`, `get_chain_controls`, `get_wildfires`, `get_cameras`
and `get_road_signs` tools read California's feeds and corridors only;
given a point or a place in another state they answer with an error that
points to `get_nearby_events` or `plan_trip` instead of an empty list.
For a drive or a place in any state, use `plan_trip`, `best_time_to_go`
or `get_nearby_events`.

Parameter notes: `center` is `"lat,lon"`; `radius_km` caps at 160 on
`get_nearby_events`, whose `kinds` is a comma list from `incident`,
`closure`, `chain` and `fire` (all four by default), plus `sign`, `rwis`,
`camera`, `toll` and `enforcement`; `plan_trip`'s
`preference` is one of `fastest` (default), `shortest`, `no_highways`,
`no_tolls` or `avoid_chains`; `depart_at`, `day`, `earliest`, `latest`
and `arrive_by` take plain times such as `"tomorrow 8am"` or `"friday"`
in the origin's local time (`arrive_by` in the destination's), and `day` reaches up to 60 days out; `best_time_to_go`'s
`step_minutes` runs 10 to 180 (the default fits the window into 16
departures); `get_weather` takes `hours` from 1 to 156; `get_traffic`
takes up to 10 `points` as `"lat,lon|lat,lon"`; `get_area_history` takes
`radius_km` from 0.2 to 25 (default 3) and `days` from 7 to 365 (default
90; the archive began 2026-07-12); `find_place` returns 1 to 8 matches
(default 5); `get_cameras` returns at most 10 verified cameras
per call; `get_lane_closures` returns at most 200 closures and says
when it truncates; pass `from_coords` and `to_coords` to `check_route`
whenever you have them (they skip geocoding). The hosted server allows
20 requests in a burst, 30 per minute sustained, and 10,000 per day per
client address. A free API key has its own limit of 2,000 per day and a
Pro key 10,000; see the tier table on the
[developers page](https://commutescout.com/developers#keys).

Route and region reports also carry context that changes the advice:
weather alerts sampled along the trip, road-weather stations reporting
something notable, recent significant earthquakes, the signs and
cameras along the way, and live speeds when a TomTom key is set. Route
names are normalized ("17", "hwy 50", "I80" all work), and docstrings
are written for the LLM consumer: what the data is, its refresh
cadence, and its limits.

## Resources and prompts

Two resources: `commutescout://coverage` (the states and feeds, as JSON)
and `commutescout://about` (what the data is and its limits, as
Markdown). Three prompts: `best_time` ("Best time to visit"),
`trip_check` ("Plan a trip") and `road_trip_check` (a California
corridor check).

## How good are the answers?

An eval suite with recorded fixtures and 91 golden questions scores the
assistant. Runs are triggered manually rather than on every release,
and the scorecard is public. See [EVALS.md](../EVALS.md).

## Registry

The server is published as `io.github.nicglazkov/commutescout`
(see [server.json](../server.json) and [registry notes](registry.md)).
