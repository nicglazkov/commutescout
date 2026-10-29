# Contributing

Thanks for looking at CommuteScout. PRs and issues are welcome. This
is a real, running product, so the bar is "small, tested, and shipped,"
and the workflow below keeps it that way.

## Dev setup

You need Python 3.12 or later (`requires-python` in `pyproject.toml`).
CI runs on Python 3.12 and installs with pip, pinned by
`constraints.txt`. Use the same command to match it:

```sh
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,demo]" -c constraints.txt
pytest        # fixture-based, no network access needed
ruff check .
```

You can use [uv](https://docs.astral.sh/uv/) instead, for example
`uv run pytest`. uv writes a local `uv.lock`, which is gitignored:
`constraints.txt` is the only pin file the repo and CI use, so bump a
version there, not in `uv.lock`.

The test suite runs entirely from recorded fixtures. If your change
needs the network to test, that's a sign it needs a fixture instead.
Some tests read the built site in `site/out`; they skip with a reason
when it is missing. Build the site (below) to run them.

Use the stdio transport for local MCP work (`ca-roads-mcp`). The http
transport is tuned for Cloud Run and binds 0.0.0.0 with host-header
checks off; bind it to localhost if you must run it locally:
`ca-roads-mcp --transport http --host 127.0.0.1`.

Running the web app locally: `pip install -e ".[demo]"` then
`ca-roads-demo` with `ANTHROPIC_API_KEY` set. Watch areas, trips, and
analytics need GCP services and will 500 locally; the map, planner,
and assistant work without them.

## Working on site/

`site/` holds the commutescout.com marketing and docs pages. It is a
Next.js static export: `npm run build` writes plain HTML to `site/out`,
and the Python web app (`src/ca_roads_demo/app.py`) serves those files.
There is no Node server in production. CI uses Node 22.

```sh
cd site
npm ci              # install the locked dependencies
npm run dev         # local dev server with hot reload
npm run lint        # ESLint; CI runs it
npx tsc --noEmit    # type check
npm run build       # static export to site/out
```

See [site/README.md](site/README.md) for the page list and where the
counts live.

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

Evals run only on manual dispatch from the Actions tab, not on releases
and not on a schedule. The release trigger was removed after it
repeatedly ran up the monthly API budget. (The Monday cron in
`model-watch.yml` checks the Models API for new models; it does not run
the suite.)

## Releases

Maintainer releases bump `pyproject.toml` and `server.json` together,
tag a GitHub release, and redeploy both Cloud Run services. If your PR
merges, it ships in the next release, usually within a day or two.
