<div align="center">
  <img src="docs/logo.svg" width="110" alt="CommuteScout logo">
  <h1>CommuteScout</h1>
  <p><b>Live California road conditions: a map, a route planner, and an
  AI assistant.<br>Also an MCP server, so your assistant can use it too.</b></p>

[![CI](https://github.com/nicglazkov/commutescout/actions/workflows/ci.yml/badge.svg)](https://github.com/nicglazkov/commutescout/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/nicglazkov/commutescout?color=2f81f7)](https://github.com/nicglazkov/commutescout/releases)
[![Evals](evals/results/badge.svg)](EVALS.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

  <p>
    <a href="https://commutescout.com"><b>Open the app</b></a> ·
    <a href="#add-to-claude">Add to Claude</a> ·
    <a href="#self-hosting-advanced">Self-hosting</a> ·
    <a href="docs/data-sources.md">Data</a> ·
    <a href="docs/mcp.md">MCP tools</a> ·
    <a href="docs/architecture.md">Architecture</a>
  </p>

  <p>
    <a href="https://commutescout.com">
      <img src="docs/try-demo-button.svg" width="230" alt="Open CommuteScout">
    </a>
  </p>
  <p>
    No install, no account:
    <a href="https://commutescout.com"><b>commutescout.com</b></a>
  </p>

  <a href="https://commutescout.com">
    <img src="docs/demo.gif" width="880"
         alt="Demo: autocompleting San Jose and San Francisco, planning a route with two traffic-colored options, switching between them, tapping a suggested question for a live AI answer, then flashing the statewide live traffic overlay">
  </a>
</div>

CommuteScout watches 13 public agency feeds (CHP dispatch, Caltrans
closures, chain controls, cameras and message signs, wildfire
perimeters, weather) and turns them into one live picture of
California's roads. Look at the map, plan a route and see what's
actually on it, or just ask about a drive in plain English. The same
data is served over [MCP](docs/mcp.md), so Claude and other AI
assistants can use it as a tool instead of guessing about traffic.

## What you get

- **A live statewide map:** incidents by type, closures by class,
  chain controls, wildfires with burn footprints, weather stations,
  ~3,300 verified-live cameras, and every message sign currently
  displaying something.
- **A route planner that knows the roads:** autocomplete, route
  options, turn-by-turn directions, live conditions along the way, and
  print / GPX / KML / share-link export.
- **An assistant that reads the feeds:** plan a route, tap a suggested
  question, and the answer streams in from the same live data, with
  per-source timestamps.
- **Watch areas:** draw a circle, polygon, or route corridor and get a
  push or email alert when an incident, closure, chain control, or
  wildfire appears inside it.
- **An MCP server:** nine tools over curated corridors and regions,
  with a [closure taxonomy](docs/data-sources.md#the-closure-taxonomy)
  that keeps a closed on-ramp from reading as a closed highway.
- **Public evals:** 91 golden questions on recorded fixtures gate
  every release; the [scorecard](EVALS.md) and its history are
  committed to this repo.

<table>
  <tr>
    <td width="34%"><img src="docs/shots/planner.png" alt="Route planner with two route options, turn-by-turn directions, and suggested questions"><br><sub><b>Plan a trip.</b> Autocomplete, route options, directions, print or export.</sub></td>
    <td width="34%"><img src="docs/shots/answer.png" alt="An AI answer about a drive, with live speeds and conditions"><br><sub><b>Ask about it.</b> One tap on a suggested question; the answer reads the live feeds.</sub></td>
    <td width="32%"><img src="docs/shots/map.png" alt="The statewide map with per-layer filters and live counts"><br><sub><b>Or just look.</b> Every layer toggleable, from full closures to blank signs.</sub></td>
  </tr>
</table>

## Get started

The fastest way to use CommuteScout is the hosted app:
**[commutescout.com](https://commutescout.com)**. Nothing to run,
always on the latest release, feeds already warm.

|  | [commutescout.com](https://commutescout.com) | Self-hosted |
|---|---|---|
| Setup | None, just open it | `pip install` or Cloud Run deploy |
| Updates & feeds | Always current, managed | You redeploy and manage keys |
| AI assistant | Included | Bring your own Anthropic API key |
| Watch-area alerts | Included (invite-only trial) | Extra setup: Firestore, push keys, a scheduler |
| Upcoming premium features | Land here first | Not planned |
| Support | Actively maintained | Best effort via issues |

### Add to Claude

Give Claude live road data with a custom connector:

```
https://mcp.commutescout.com/mcp
```

Local stdio setup and the full tool reference: [docs/mcp.md](docs/mcp.md).

### Self-hosting (advanced)

Everything here is MIT licensed and the core runs with zero accounts or
keys:

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

The web app is `pip install ".[demo]"` then `ca-roads-demo` with an
`ANTHROPIC_API_KEY` in the environment. For your own Cloud Run copy
(small enough for the free tier most months), optional feed keys, and
the watch-areas setup, see **[docs/deploy.md](docs/deploy.md)**.

Self-hosted deployments are supported on a best-effort basis: issues
and PRs are very welcome, but there is no support guarantee for
deployments I don't run.

## The data

CHP incidents, Caltrans lane closures, chain controls, message signs,
cameras, and road weather; WFIGS and CAL FIRE wildfires with
perimeters; NWS alerts; USGS quakes; and optional TomTom, 511 SF Bay,
and Nevada DOT feeds. Every response carries per-source `data_as_of`
timestamps, and a failing feed is never silent: the last good data is
served, flagged stale, with the error attached.

Full source table, refresh rates, and the closure taxonomy:
**[docs/data-sources.md](docs/data-sources.md)**.

## How good are the answers?

An eval suite gates every release: recorded fixtures for four scenarios
(a Sierra storm day, a fire-closure day, a quiet day, and a
byte-for-byte capture of a real fire-season day), 91 golden questions
with ground truth including traps, and an LLM judge that is never an
evaluated model. Every run appends to a committed history file, so the
trend is public: **[EVALS.md](EVALS.md)**.

## Under the hood

Three cleanly layered Python packages (a feed layer with
stale-while-revalidate caches and salvaging parsers, the MCP surface,
and the web app) sharing one data spine. Diagram and design notes:
**[docs/architecture.md](docs/architecture.md)**.

## Contributing

PRs welcome. The test suite is fixture-based and runs without network
access. Start with **[CONTRIBUTING.md](CONTRIBUTING.md)**, and see
[adding a data source](docs/adding-a-source.md) if you want to wire up
a new feed.

## License & sustainability

CommuteScout is [MIT licensed](LICENSE): the map, the planner, the MCP
server, and every data parser, with no open-core carve-outs. The hosted
app at [commutescout.com](https://commutescout.com) will soon offer
optional premium features (deeper history, more alerts); that is what
funds the servers and keeps the free tier free.

## Disclaimer

Data: CHP, Caltrans, WFIGS, CAL FIRE, NWS, USGS. Not affiliated with
any agency. Conditions change faster than any feed; verify before you
drive (511 or [quickmap.dot.ca.gov](https://quickmap.dot.ca.gov)).

Place names resolve through the Nominatim and Photon OpenStreetMap
geocoders; the web app loads map tiles from CARTO and route previews
from the public OSRM and Valhalla routers, so those services see the
coordinates involved. Fonts and map libraries are served locally.
