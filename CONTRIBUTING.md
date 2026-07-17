# Contributing

Thanks for looking at CommuteScout. PRs and issues are welcome. This
is a real, running product, so the bar is "small, tested, and shipped,"
and the workflow below keeps it that way.

## Dev setup

```sh
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest        # fixture-based, no network access needed
ruff check .
```

The test suite runs entirely from recorded fixtures. If your change
needs the network to test, that's a sign it needs a fixture instead.

Use the stdio transport for local MCP work (`ca-roads-mcp`). The http
transport is tuned for Cloud Run and binds 0.0.0.0 with host-header
checks off; bind it to localhost if you must run it locally:
`ca-roads-mcp --transport http --host 127.0.0.1`.

Running the web app locally: `pip install -e ".[demo]"` then
`ca-roads-demo` with `ANTHROPIC_API_KEY` set. Watch areas, trips, and
analytics need GCP services and will 500 locally; the map, planner,
and assistant work without them.

## Pull requests

- Keep PRs small and focused; one change per PR.
- `pytest` and `ruff check .` must pass; CI gates every merge.
- Match the surrounding style: the codebase favors plain, commented
  Python and vanilla JS over frameworks and abstraction.
- New feeds: follow [docs/adding-a-source.md](docs/adding-a-source.md).
  Feed parsers should salvage what they can from malformed input, never
  raise on it.

## Evals

Changes that touch tool behavior or prompts should be checked against
the eval suite ([EVALS.md](EVALS.md)):

```sh
pip install -e ".[dev,evals]"
python evals/build_fixtures.py
python evals/run_evals.py       # needs your own ANTHROPIC_API_KEY; costs a few dollars
```

Evals also run automatically on releases that touch the data or tool
layers.

## Releases

Maintainer releases bump `pyproject.toml` and `server.json` together,
tag a GitHub release, and redeploy both Cloud Run services. If your PR
merges, it ships in the next release, usually within a day or two.
