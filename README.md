# ca-roads-mcp

[![CI](https://github.com/nicglazkov/ca-roads-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/nicglazkov/ca-roads-mcp/actions/workflows/ci.yml)
[![Evals](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnicglazkov%2Fca-roads-mcp%2Fmain%2Fevals%2Fresults%2Fbadge.json)](EVALS.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Live California road conditions for AI assistants, over
[MCP](https://modelcontextprotocol.io). Add one connector URL to Claude (or
any MCP client) and ask "do I need chains to get to Tahoe?" or "is 17 clear
right now?" - the answer comes from the same live feeds CHP and Caltrans
publish, not from the model's memory.

## Data sources

| Source | Data | Refresh |
|--------|------|---------|
| **CHP live feed** | Statewide incidents (collisions, hazards, closures) as CHP dispatchers log them | Fetched per request; feed updates ~1/min |
| **Caltrans LCS** | Lane and road closures physically in place right now (CHP code 1097), per district | 5-minute cache |
| **Caltrans chain controls** | R-1/R-2/R-3 requirements at mountain checkpoints | 5-minute cache |
| **WFIGS** | Active California wildfires (name, size, containment), flagged within ~10 miles of major highways | 5-minute cache |

Every tool response includes a `data_as_of` timestamp per source and explicit
notes when a feed is stale or failing, so the assistant can tell you how much
to trust the answer.

## Add to Claude

Hosted: add a custom connector with the URL

```
https://ca-roads-mcp-15002631928.us-west1.run.app/mcp
```

Local over stdio:

```json
{
  "mcpServers": {
    "ca-roads": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nicglazkov/ca-roads-mcp", "ca-roads-mcp"]
    }
  }
}
```

Or from a checkout: `pip install .` then run `ca-roads-mcp` (stdio) or
`ca-roads-mcp --transport http` (streamable HTTP on `$PORT`).

## Tools

| Tool | What it answers |
|------|-----------------|
| `check_route(from_place, to_place)` | Everything active along a major corridor (I-80 Sacramento-Reno, US-50 to Tahoe, I-5, US-101, SR-17, SR-99, SR-1, I-15 to Vegas, Bay Area freeways, Tahoe locals), ordered by miles along the route, with a plain-language summary |
| `get_incidents(highway?, area?, center?)` | Live CHP incidents, filterable by route, dispatch area, or a point and radius |
| `get_lane_closures(route?, district?)` | Caltrans closures in place right now - not the construction schedule |
| `get_chain_controls(route?)` | Current chain requirements; says "none active" explicitly in the off-season |
| `get_wildfires(near_route?)` | Active fires with size and containment, flagged near major highways |

There is also a `road_trip_check` prompt template that shows a client how to
compose the tools for a trip check.

## Evals

The eval suite is a first-class part of this repo: recorded feed fixtures for
three scenarios (a Sierra storm day, a fire-closure day, a quiet summer day),
a 75-question golden set with ground truth, and a harness that runs Claude
against the tools in fixture mode and grades answers by exact-fact matching
plus an LLM judge. See [EVALS.md](EVALS.md) for the current scorecard and
`evals/` for how it works.

```sh
pip install -e ".[dev,evals]"
python evals/build_fixtures.py       # regenerate scenario fixtures
python evals/run_evals.py            # needs ANTHROPIC_API_KEY
```

## Development

```sh
python -m venv .venv && . .venv/bin/activate   # or .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check .
```

The feed layer (`ca_roads`) is a standalone package with no MCP dependency:
async httpx fetchers, per-district TTL caches, stale-serve on upstream
failure, and cross-source dedupe. `ca_roads_mcp` is the MCP surface;
`ca_roads_demo` is the public web demo (Claude Haiku answering questions with
the same tools).

Deployment notes are in [docs/deploy.md](docs/deploy.md); registry submission
steps in [docs/registry.md](docs/registry.md).

## Disclaimer

Data: CHP, Caltrans, WFIGS. Not affiliated with any agency. Conditions change
faster than any feed; verify before you drive (511 or
[quickmap.dot.ca.gov](https://quickmap.dot.ca.gov)).
