# Registry submissions

The server has been listed in the MCP Registry since July 2026 as
`io.github.nicglazkov/commutescout`, from [server.json](../server.json).
The entry is republished at release time so the registry carries the
released version; a workflow that does this on each release is being
added separately. The Claude connectors directory entry below was
submitted by hand.

## MCP Registry

To republish by hand after a release:

1. Confirm `server.json` carries the released version and the service
   URL (`remotes[0].url`).
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
