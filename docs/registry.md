# Registry submissions (manual steps)

Everything here is prepared; submitting is a manual step after the Cloud Run
deploy, once the service URL exists.

## MCP Registry

1. Put the real service URL in `server.json` (`remotes[0].url`).
2. Install the publisher CLI and run it from the repo root:

   ```sh
   mcp-publisher login github
   mcp-publisher publish
   ```

   The `io.github.nicglazkov/*` namespace is verified through the GitHub
   login.

## Claude connectors directory

Submission form asks for a name, the connector URL, and a description.

- Name: `CommuteScout`
- URL: `https://mcp.commutescout.com/mcp`
- Short description:

  > Live US road conditions across 32 states. Ask about a route or a place
  > and get current incidents, closures, chain controls, and wildfires
  > straight from official state DOT feeds, with the deepest coverage in
  > California.

- Longer description:

  > CommuteScout gives your assistant live road intelligence across 32 US
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
