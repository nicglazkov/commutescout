# CommuteScout docs

CommuteScout serves live, official road data across 37 US states, on
the map at [commutescout.com](https://commutescout.com) and to AI
assistants over MCP. Start with the page that matches what you want to
do.

## Using CommuteScout

- [mcp.md](mcp.md): connect an MCP client and learn what each tool does.
- [data-sources.md](data-sources.md): where the data comes from, how
  fresh it is, and how the parsers handle bad feeds.
- [state-coverage.md](state-coverage.md): what each covered state has
  on the map, and why the gaps exist.
- [flare.md](flare.md): Flare, the open protocol for plugins that add
  road alert sources.

## Contributing

- [architecture.md](architecture.md): how the packages fit together,
  the MCP request path, and the design choices worth knowing.
- [adding-a-source.md](adding-a-source.md): add a new feed to the feed
  layer.

## Running the hosted service (maintainers)

- [deploy.md](deploy.md): deploy both Cloud Run services, or self-host
  your own, with every environment variable.
- [cloudflare.md](cloudflare.md): put Cloudflare in front of the site
  and the map snapshots.
- [analytics.md](analytics.md): query the BigQuery event archive.
- [registry.md](registry.md): the MCP Registry listing and other
  directory submissions.

## Historical notes

These pages record past research and plans. They are not kept current.

- [state-expansion-audit.md](state-expansion-audit.md): the July 2026
  survey of every state's road data that led to nationwide coverage.
- [plugins-waze-google-plan.md](plugins-waze-google-plan.md): design
  notes for the Waze relay plugin, written before it was built.
