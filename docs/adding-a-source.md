# Adding a data source

The feed layer is built to grow. Every source is one module in
`src/ca_roads/feeds/` with the same shape; nothing else in the stack needs
to know how a feed works.

## The contract

A source module provides:

1. **A record dataclass** in `ca_roads/models.py` (frozen, typed, normalized).
2. **A parse function** that turns raw bytes into records and never throws on
   partial data. Salvage what parsed and report truncation in a note. See
   `ca_roads/xmlutil.py` for the salvaging XML helper.
3. **A `to_event(record)` function** mapping the record to a `RoadEvent`
   (source name, family, lat/lon, one-line summary). This is what corridor
   matching and cross-source dedupe consume.
4. **A source class** with `async def get(...) -> FeedResult`, built on
   `ca_roads/cache.py` (`TTLCache.get` gives you TTL, stale-serve on upstream
   failure, and single-flight per key).

Rules learned the hard way, keep them:

- A missing regional feed is an empty result, not an error.
- Never return zero records silently because the fetch failed. Serve the
  last good data flagged `stale`, and put the error in `FeedResult.error`.
- Dedupe across sources, never within one source.
- Every result carries `data_as_of` so agents can reason about freshness.

## Wiring it in

- Add the source to `RoadData` in `ca_roads/roaddata.py`.
- Give it a priority in `ca_roads/dedupe.py` if its events can duplicate
  another source's.
- Expose it in a tool (new or existing) in `ca_roads_mcp/server.py`, with a
  docstring that tells the LLM what the data is, its refresh cadence, and
  its limits.
- Add its URLs to `evals/record.py` so scenarios capture it, extend
  `evals/build_fixtures.py`, and add golden questions for it.
- Unit tests against recorded fixture files, like `tests/test_chp.py`.

## Candidate sources for v2

Roughly in order of value per effort:

| Source | What it adds | Access |
|--------|--------------|--------|
| Caltrans CMS signs (`cwwp2.dot.ca.gov/data/d<N>/cms/`) | What the changeable message signs are showing right now, per district | Free, same portal and XML shape as LCS |
| NWS alerts (`api.weather.gov/alerts`) | Winter storm warnings, high wind, flood alerts along corridors | Free JSON, no key |
| Caltrans CCTV (`cwwp2.dot.ca.gov/data/d<N>/cctv/`) | Camera snapshot URLs near a route (visual confirmation) | Free, same portal |
| 511 SF Bay (`api.511.org`) | Bay Area events and transit disruptions | Free token, sign-up |
| WFIGS fire perimeters (NIFC ArcGIS) | Actual fire footprints instead of origin points, so "near the road" gets accurate | Free, same ArcGIS host we already query |
| Nevada DOT (`nvroads.com`) | Continuations to Reno and Las Vegas past the state line | Free feed, registration |
| Caltrans RWIS (`cwwp2.dot.ca.gov/data/d<N>/rwis/`) | Road weather stations: pavement temp, wind, visibility on passes | Free, same portal |
| USGS earthquakes (`earthquake.usgs.gov/fdsnws/`) | Significant quakes near corridors | Free JSON |
| PeMS or a commercial speeds API | Actual travel speeds and delay | Key and/or paid |

The corridor table (`ca_roads_mcp/corridors.py`) is the other growth axis:
adding a corridor is a dozen waypoints and a few aliases, no code.

## Adding a state

Wiring the feed is only half of it. A state is live when all of these
agree, and they are in different files, so they drift:

1. `ca_roads_demo/states.py` registry (the adapter itself).
2. The `COVERED` set in `static/index.html`, or `PARTIAL` if only some
   layers work. A state missing here renders under the grey
   "not supported yet" wash even though its data is on the map.
3. A row in [state-coverage.md](state-coverage.md).
4. The **state count**, which appears in more places than you would
   expect: `index.html` metadata (title, description, og, ld+json),
   `prompt.py`, the `get_nearby_events` docstring in
   `ca_roads_mcp/server.py`, and [registry.md](registry.md).
5. The **feed count**. A new state usually adds new feed sources too.
   Unlike the state count, this one is not read live from the registry:
   `PUBLIC_SOURCE_COUNT` in `states.py` is a manually maintained
   constant (the number production's topbar shows with keys
   configured; the live `coverage_summary()["sources"]` count varies
   with key availability and WZDx supersession, so it is not a stable
   source of truth for marketing copy). Update `PUBLIC_SOURCE_COUNT`
   yourself, then update its copies: `README.md`,
   `site/lib/stats.ts`, `site/app/about/page.tsx`, and
   `site/components/blocks/hero-section-1.tsx`.

`tests/test_snapshot.py::test_state_counts_are_current` fails when a
state count drifts from the live registry, and
`test_feed_counts_are_current` fails when a copy's feed count drifts
from `PUBLIC_SOURCE_COUNT`, so items 4 and 5 cannot be forgotten
quietly. The count in the MCP tool docstring matters most: the model
reads it to decide whether a location is worth querying at all.
