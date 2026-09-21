# Registry submissions

## MCP Registry

CommuteScout has been listed since July 2026, and the listing republishes
itself on every release: `.github/workflows/registry.yml` runs
`mcp-publisher` against `server.json`, authenticating with GitHub Actions
OIDC, so there is no token to rotate and no interactive login.

Two things the workflow protects against, both of which had already
happened:

- The listing sat at v2.24.0 for two months, describing the service as
  California-only, because nothing ever ran a publish.
- It could not have succeeded anyway. The registry rejects a description
  over 100 characters and ours was 152, so every publish would have
  failed validation. `test_the_registry_manifest_fits_what_the_registry_accepts`
  now checks the length, the schema version and that the manifest version
  matches `pyproject.toml`.

To repair the listing without cutting a release, run the workflow by hand
from the Actions tab. To publish from a laptop instead, install the
publisher CLI and run it from the repo root:

```sh
mcp-publisher login github
mcp-publisher publish
```

The `io.github.nicglazkov/*` namespace is verified through the GitHub
login, or through this repository's OIDC identity in Actions.

## Claude connectors directory

Submission form asks for a name, the connector URL, and a description.

- Name: `CommuteScout`
- URL: `https://mcp.commutescout.com/mcp`
- Short description:

  > Live US road conditions across 37 states. Ask about a route or a place
  > and get current incidents, closures, chain controls, and wildfires
  > straight from official state DOT feeds, with the deepest coverage in
  > California.

- Longer description:

  > CommuteScout gives your assistant live road intelligence across 37 US
  > states. Ask "do I need chains to get to Tahoe?", "is 17 clear right
  > now?", or "any roadwork near Salt Lake City?" and it answers from the
  > same feeds state transportation agencies publish: real-time incidents,
  > closures that are physically in place (with lane, ramp, and full
  > roadway closures told apart), chain controls, live sign text, road
  > weather, and active wildfires with mapped burn footprints. California
  > has the richest detail (CHP dispatch logs, 17 route corridors, region
  > reports); everywhere else a nearby-events tool serves the same live
  > map data, and each event names its source agency. Every answer carries
  > per-source timestamps so the assistant can tell you how fresh the data
  > is. Read-only public data, no account needed. Not affiliated with any
  > government agency; verify before you drive.
