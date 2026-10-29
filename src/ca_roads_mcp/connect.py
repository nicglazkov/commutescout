"""How to connect: one source for people and for agents.

CLIENTS is the per-client setup. It renders three ways:

- /llms.txt on commutescout.com and on mcp.commutescout.com (where it is
  also the root page), so an agent handed either host finds the endpoint
  and the steps without reading HTML;
- site/lib/mcp-clients.json, written by scripts/gen_api_reference.py,
  which the /mcp page on the site renders as cards;
- the server card at /.well-known/mcp/server-card.json, the same facts as
  data.

tests/test_connect.py fails when the JSON on the site drifts from this.
Steps were checked against each vendor's own docs on 2026-10-29. Menu
names move, so recheck them when a client ships a redesign.
"""

from __future__ import annotations

ENDPOINT = "https://mcp.commutescout.com/mcp"
SITE = "https://commutescout.com"
KEY_HEADER = "Authorization: Bearer cs_live_..."

# Each client: name, whether it can send a key (saved places), and its
# steps. A step is {"text": ...} or {"code": ..., "lang": ...}.
CLIENTS: list[dict] = [
    {
        "id": "claude-code",
        "name": "Claude Code",
        "key": True,
        "steps": [
            {"lang": "sh", "code":
                f"claude mcp add --transport http --scope user commutescout {ENDPOINT}"},
            {"text": "With a key, for saved places:"},
            {"lang": "sh", "code":
                f"claude mcp add --transport http --scope user commutescout {ENDPOINT} \\\n"
                f'  --header "{KEY_HEADER}"'},
            {"text": "Run /mcp inside Claude Code to confirm it connected."},
        ],
    },
    {
        "id": "claude-ai",
        "name": "claude.ai and Claude Desktop",
        "key": True,
        "steps": [
            {"text": "Customize > Connectors > + Add > Add custom connector. "
                     f"Name: CommuteScout. URL: {ENDPOINT}. Sign-in: No sign in."},
            {"text": "For saved places, add a request header named Authorization "
                     "with the value Bearer cs_live_..."},
            {"text": "On Team and Enterprise plans, an owner adds it first under "
                     "Organization settings > Connectors. The connector also "
                     "appears in Claude Desktop and the mobile apps."},
        ],
    },
    {
        "id": "cursor",
        "name": "Cursor",
        "key": True,
        "steps": [
            {"text": "Add to ~/.cursor/mcp.json, or .cursor/mcp.json in a project:"},
            {"lang": "json", "code":
                '{\n  "mcpServers": {\n    "commutescout": {\n'
                f'      "url": "{ENDPOINT}",\n'
                '      "headers": { "Authorization": "Bearer ${env:COMMUTESCOUT_API_KEY}" }\n'
                "    }\n  }\n}"},
            {"text": "Leave out headers to connect without a key."},
        ],
    },
    {
        "id": "vscode",
        "name": "VS Code (GitHub Copilot)",
        "key": True,
        "steps": [
            {"text": "Add to .vscode/mcp.json:"},
            {"lang": "json", "code":
                '{\n  "servers": {\n    "commutescout": {\n'
                f'      "type": "http",\n      "url": "{ENDPOINT}",\n'
                '      "headers": { "Authorization": "Bearer ${input:commutescout-key}" }\n'
                "    }\n  },\n"
                '  "inputs": [\n    { "type": "promptString", "id": "commutescout-key",\n'
                '      "description": "CommuteScout API key", "password": true }\n  ]\n}'},
            {"text": "Leave out headers and inputs to connect without a key."},
        ],
    },
    {
        "id": "windsurf",
        "name": "Windsurf",
        "key": True,
        "steps": [
            {"text": "Add to its mcp_config.json (MCP settings > view raw config):"},
            {"lang": "json", "code":
                '{\n  "mcpServers": {\n    "commutescout": {\n'
                f'      "serverUrl": "{ENDPOINT}",\n'
                '      "headers": { "Authorization": "Bearer ${env:COMMUTESCOUT_API_KEY}" }\n'
                "    }\n  }\n}"},
        ],
    },
    {
        "id": "codex",
        "name": "OpenAI Codex CLI",
        "key": True,
        "steps": [
            {"lang": "sh", "code": f"codex mcp add commutescout --url {ENDPOINT}"},
            {"text": "With a key, in ~/.codex/config.toml:"},
            {"lang": "toml", "code":
                "[mcp_servers.commutescout]\n"
                f'url = "{ENDPOINT}"\n'
                'bearer_token_env_var = "COMMUTESCOUT_API_KEY"'},
        ],
    },
    {
        "id": "gemini",
        "name": "Gemini CLI",
        "key": True,
        "steps": [
            {"lang": "sh", "code":
                f"gemini mcp add --transport http commutescout {ENDPOINT}"},
            {"text": f'Add --header "{KEY_HEADER}" for saved places.'},
        ],
    },
    {
        "id": "chatgpt",
        "name": "ChatGPT",
        "key": False,
        "steps": [
            {"text": "On chatgpt.com: Plugins > + > Add custom MCP server. "
                     f"URL: {ENDPOINT}. Authentication: none."},
            {"text": "Custom MCP servers depend on your plan and workspace "
                     "settings. ChatGPT offers sign-in (OAuth) rather than a key "
                     'field, so use addresses instead of "home" and "work" there.'},
        ],
    },
    {
        "id": "other",
        "name": "Any other MCP client",
        "key": True,
        "steps": [
            {"text": f"Streamable HTTP at {ENDPOINT}: stateless, no sign-in, "
                     f"optional {KEY_HEADER} (or X-API-Key)."},
            {"text": "A client that only speaks stdio can bridge with:"},
            {"lang": "sh", "code": f"npx mcp-remote {ENDPOINT} --transport http-only"},
        ],
    },
]


def _markdown(steps: list[dict]) -> str:
    out = []
    for s in steps:
        if "code" in s:
            out.append(f"```{s.get('lang', '')}\n{s['code']}\n```")
        else:
            out.append(s["text"])
    return "\n\n".join(out)


def guide() -> str:
    """The llms.txt body (llmstxt.org layout: title, summary, sections)."""
    clients = "\n\n".join(f"### {c['name']}\n\n{_markdown(c['steps'])}"
                          for c in CLIENTS)
    return f"""# CommuteScout

> Live road conditions for 37 US states, trip planning, and the best time
> to leave, as a public MCP server. Hosted endpoint (streamable HTTP, no
> key needed): {ENDPOINT}

CommuteScout ({SITE}) is a live road map, a driving app and an MCP server
built on the same data: state DOT and 511 feeds, CHP, NWS weather,
wildfires, cameras, message signs, TomTom traffic and an archive of past
events. The MCP server lets an assistant answer "what's a good time to
drive to X?", "is I-80 open over Donner?" or "what's going on near me?"
with live data.

## Install the MCP server

Endpoint: `{ENDPOINT}` (streamable HTTP). It works without a key or an
account. Pick the user's client:

{clients}

After connecting, check it with a question such as "When should I leave
Union Station in Denver for Red Rocks tomorrow?". The assistant should
call `best_time_to_go`.

## Saved places and API keys (optional)

A key lets "home", "work" and the names of the user's saved places work in
every trip tool, and gives the client its own rate limits. The user gets
one at {SITE}/map: Settings, sign in, then API keys. It is shown once.
Send it as `{KEY_HEADER}` or `X-API-Key: cs_live_...`. Free keys get
2,000 requests a day; without a key, each address gets 10,000 a day. An
agent cannot create a key for the user: ask them to create one and paste
it, and keep it out of shared files.

The server cannot see the user's device location. For "from here", pass
coordinates or a city you already know, or ask.

## Tools

- Trips: `plan_trip`, `best_time_to_go`, `find_place`, `get_my_places`
- Around a place: `get_nearby_events`, `get_weather`, `get_traffic`,
  `get_area_history`
- California corridors and regions: `check_route`, `check_region`,
  `rank_routes`, `get_incidents`, `get_lane_closures`,
  `get_chain_controls`, `get_wildfires`, `get_cameras`, `get_road_signs`
- Coverage: `get_coverage`

## Docs

- [MCP setup and tool list]({SITE}/mcp)
- [Developer docs: REST API, keys, limits, errors]({SITE}/developers)
- [OpenAPI document](https://mcp.commutescout.com/v1/openapi.json)
- [Every tool over plain HTTP](https://mcp.commutescout.com/v1)
- [Server card](https://mcp.commutescout.com/.well-known/mcp/server-card.json)
- [Source code (MIT)](https://github.com/nicglazkov/commutescout)
- [Data sources]({SITE}/data-sources)

## Run it yourself

```sh
uvx --from git+https://github.com/nicglazkov/commutescout ca-roads-mcp
```

That is a stdio server. Live events need no keys; routing and geocoding
for the trip tools need `STADIA_API_KEY`, and traffic needs
`TOMTOM_API_KEY`. `MCP_HOME` and `MCP_WORK` ("lat,lon" or an address) set
fixed places.

Not affiliated with any government agency. Verify before driving.
"""


def clients_json() -> dict:
    """What the site's /mcp page renders (site/lib/mcp-clients.json)."""
    return {"endpoint": ENDPOINT, "key_header": KEY_HEADER, "clients": CLIENTS}


def server_card(version: str) -> dict:
    """MCP server card (the .well-known discovery document)."""
    return {
        "name": "io.github.nicglazkov/commutescout",
        "title": "CommuteScout",
        "version": version,
        "description": "Trip planning, best time to leave, and live road, "
                       "traffic and weather data for 37 US states.",
        "websiteUrl": SITE,
        "documentationUrl": f"{SITE}/mcp",
        "instructionsUrl": "https://mcp.commutescout.com/llms.txt",
        "iconUrl": f"{SITE}/static/icon-512.png",
        "repository": "https://github.com/nicglazkov/commutescout",
        "remotes": [{
            "type": "streamable-http",
            "url": ENDPOINT,
            "authentication": {
                "required": False,
                "schemes": ["bearer"],
                "header": "Authorization",
                "description": "Optional CommuteScout API key (cs_live_...) "
                               f"from Settings on {SITE}/map: saved places "
                               "and per-key limits.",
            },
        }],
        "capabilities": {"tools": True, "resources": True, "prompts": True},
    }
