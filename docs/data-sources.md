# Data sources

Everything CommuteScout serves comes from public agency feeds, fetched
live and cached briefly in-process. No feed is ever silently dropped:
every response carries per-source `data_as_of` timestamps, and when a
feed is stale or failing the last good data is served, flagged stale,
with the error attached, so both the UI and an AI assistant can say
how much to trust the answer.

## The feeds

| Source | Data | Refresh |
|--------|------|---------|
| **CHP live feed** | Statewide incidents (collisions, hazards, closures) as dispatchers log them, with travel direction parsed from the location text, plus the full shared dispatch timeline (comments and unit lifecycle, verbatim) | 1-minute cache; feed updates ~1/min |
| **Caltrans LCS** | Lane and road closures physically in place right now (CHP code 1097), classified by what they mean for through traffic | 5-minute cache |
| **Caltrans chain controls** | R-1/R-2/R-3 requirements at mountain checkpoints | 5-minute cache |
| **WFIGS** | Active wildfires (name, size, containment), flagged within ~10 miles of major highways; perimeter edges refine distances for big fires | 5-minute cache |
| **CAL FIRE** | CAL FIRE's own incident postings, merged into the wildfire layer for fires WFIGS does not list yet | 5-minute cache |
| **Caltrans CMS** | What changeable message signs display right now (blank signs filtered) | 2-minute cache |
| **Caltrans CCTV** | Roadside camera snapshots, image-verified live before return | per query |
| **Caltrans RWIS** | Road-weather stations: pavement temperature, gusts, visibility on the passes | 5-minute cache |
| **NWS alerts** | Winter storm, wind, flood, fog, and fire-weather warnings along the route | 5-minute cache |
| **USGS quakes** | M4.5+ earthquakes near a corridor in the last 24 hours | 5-minute cache |
| **TomTom** (optional key) | Actual current speeds vs free-flow along the route | 1-minute cache |
| **511 SF Bay** (optional key) | Bay Area traffic events | 3-minute cache |
| **Nevada DOT** (optional key) | I-80, US-50, I-15 continuations past the state line | 3-minute cache |

Caches are stale-while-revalidate: an expired feed is served from
memory instantly while one background task refreshes it, so requests
never wait on an upstream agency server.

## The closure taxonomy

Every closure record carries a `closure_class` derived from the
Caltrans facility and closure type. The raw feed marks an on-ramp
repair "Full", and reporting that as a closed highway would be wrong,
so the classes keep them apart:

| closure_class | Means | Can you drive through? |
|---|---|---|
| `full-roadway` | The road itself is closed in that direction | No |
| `one-way-traffic` | Alternating single lane with flagging | Yes, with delays |
| `alternating-lanes` / `moving` / `traffic-break` | Rolling or brief work | Yes, minor delays |
| `lane` | Some lanes closed ("2 of 4 lanes closed") | Yes |
| `ramp` | One ramp or connector closed, road unaffected | Yes |

## Hard-won parsing rules

These feeds misbehave in production, and the parsers encode what we
learned running them:

- CHP truncates its XML mid-record on busy days; the parser salvages
  every complete record instead of failing, and recently-seen incidents
  are carried forward briefly so they do not flap out of existence.
- Camera "liveness" is judged by image freshness (Last-Modified within
  30 minutes), not byte size: night frames are tiny but live.
- A missing Caltrans district feed is treated as an empty district, not
  an error: one flaky district should not blank the state.
- Place names go through a real geocoder with an offline California
  gazetteer fallback, and when a street exists in several towns the
  tools say so and ask instead of guessing.

## Expansion states (map only, first wave)

Beyond California, the map also shows live data when you pan there:

| Region | Source | Data |
|---|---|---|
| Maine, New Hampshire, Vermont | NE Compass tri-state portal (keyless C2C XML) | Incidents, lane closures, message signs, road weather, cameras (snapshots served via `/api/stcam`) |
| Iowa | Iowa DOT WZDx feed (keyless, CC0) | Roadwork and closures with route geometry and schedule windows |
| North Carolina | NCDOT WZDx feed (keyless) | Roadwork and closures with geometry and schedules |
| Washington | WSDOT Traveler API (free key) | Incidents, closures, cameras, mountain-pass traction restrictions |
| Oregon | ODOT TripCheck API (free key) | Incidents, roadwork, cameras |
| Ohio | OHGO public API (free key) | Incidents, roadwork, cameras, message signs |

These feeds are fetched only when the viewport touches the state and
carry a source label in every popup. The full state-by-state expansion
plan lives in [state-expansion-audit.md](state-expansion-audit.md).

Want to add a feed? See [adding a data source](adding-a-source.md).
