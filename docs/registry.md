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

- Name: `CA Roads`
- URL: `https://<service-url>/mcp`
- Short description:

  > Live California road conditions. Ask about a route and get current CHP
  > incidents, Caltrans lane closures, chain controls, and wildfires near
  > the road, straight from the official feeds.

- Longer description:

  > CA Roads gives your assistant live California road intelligence. Ask
  > "do I need chains to get to Tahoe?" or "is 17 clear right now?" and it
  > answers from the same feeds Caltrans and CHP publish: real-time
  > incidents, lane closures that are physically in place, chain-control
  > levels, and active wildfires near major highways. Every answer carries
  > per-source timestamps so the assistant can tell you how fresh the data
  > is. Read-only public data, no account needed. Not affiliated with any
  > government agency; verify before you drive.
