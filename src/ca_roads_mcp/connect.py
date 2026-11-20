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
KEY_PAGE = f"{SITE}/map"
# The placeholder every step uses for the user's key. The site swaps in
# the real key in the browser (on /mcp once pasted, and on the map right
# after a key is created), so the steps people copy are ready to paste.
KEY_PLACEHOLDER = "cs_live_..."
# A personal connector link: the endpoint with the key as the last path
# segment (ca_roads_mcp/keyurl.py). Every client accepts a URL, and the
# chat apps (ChatGPT, claude.ai) accept nothing else, so it is the one
# thing people copy, whatever they use.
PERSONAL_URL = f"{ENDPOINT}/{KEY_PLACEHOLDER}"
LINK_NOTE = ("Your link contains your key, so keep it private like a "
             "password. If it leaks, delete the key under Settings > API keys "
             "on the map and make a new one.")

# Each client: name, a short hint shown beside it, whether it can use a
# key (the hosted server needs one), an optional one-click install
# ("cursor" or "vscode": the site builds the deep link from the personal
# link), and its steps. A step is {"text": ...} or {"code": ..., "lang": ...}.
CLIENTS: list[dict] = [
    {
        "id": "chatgpt",
        "name": "ChatGPT",
        "hint": "chatgpt.com and the ChatGPT apps",
        "key": True,
        "steps": [
            {"text": "On chatgpt.com, open Plugins, choose +, then Add custom "
                     "MCP server."},
            {"text": "Name: CommuteScout. URL: your personal link. "
                     "Authentication: No authentication (the key is in the link)."},
            {"lang": "text", "code": PERSONAL_URL},
            {"text": "Save, then ask about a drive in a new chat. Menu names can "
                     "differ slightly between ChatGPT versions and plans."},
        ],
    },
    {
        "id": "claude-ai",
        "name": "Claude",
        "hint": "claude.ai, Claude Desktop and the mobile apps",
        "key": True,
        "steps": [
            {"text": "Open Customize > Connectors > + Add > Add custom connector."},
            {"text": "Name: CommuteScout. URL: your personal link. Sign-in: No "
                     "sign in (the key is in the link)."},
            {"lang": "text", "code": PERSONAL_URL},
            {"text": "Choose Add. The connector then appears in Claude Desktop and "
                     "the mobile apps too. On Team and Enterprise plans an owner "
                     "adds it first under Organization settings > Connectors."},
        ],
    },
    {
        "id": "claude-code",
        "name": "Claude Code",
        "hint": "Terminal",
        "key": True,
        "steps": [
            {"lang": "sh", "code":
                f"claude mcp add --transport http --scope user commutescout {PERSONAL_URL}"},
            {"text": "Run /mcp inside Claude Code to confirm it connected."},
        ],
    },
    {
        "id": "cursor",
        "name": "Cursor",
        "hint": "One-click install",
        "key": True,
        "install": "cursor",
        "steps": [
            {"text": "Use Add to Cursor, or add this to ~/.cursor/mcp.json:"},
            {"lang": "json", "code":
                '{\n  "mcpServers": {\n    "commutescout": {\n'
                f'      "url": "{PERSONAL_URL}"\n'
                "    }\n  }\n}"},
        ],
    },
    {
        "id": "vscode",
        "name": "VS Code (GitHub Copilot)",
        "hint": "One-click install",
        "key": True,
        "install": "vscode",
        "steps": [
            {"text": "Use Add to VS Code, or run MCP: Add Server from the Command "
                     "Palette, choose HTTP, and paste your personal link:"},
            {"lang": "text", "code": PERSONAL_URL},
        ],
    },
    {
        "id": "codex",
        "name": "OpenAI Codex CLI",
        "hint": "Terminal",
        "key": True,
        "steps": [
            {"lang": "sh", "code": f"codex mcp add commutescout --url {PERSONAL_URL}"},
        ],
    },
    {
        "id": "gemini",
        "name": "Gemini CLI",
        "hint": "Terminal",
        "key": True,
        "steps": [
            {"lang": "sh", "code":
                f"gemini mcp add --transport http commutescout {PERSONAL_URL}"},
        ],
    },
    {
        "id": "windsurf",
        "name": "Windsurf",
        "hint": "Config file",
        "key": True,
        "steps": [
            {"text": "Add to its mcp_config.json (MCP settings > View raw config):"},
            {"lang": "json", "code":
                '{\n  "mcpServers": {\n    "commutescout": {\n'
                f'      "serverUrl": "{PERSONAL_URL}"\n'
                "    }\n  }\n}"},
        ],
    },
    {
        "id": "other",
        "name": "Any other MCP client",
        "hint": "Streamable HTTP",
        "key": True,
        "steps": [
            {"text": "Point the client at your personal link (streamable HTTP, "
                     "stateless, no OAuth sign-in):"},
            {"lang": "text", "code": PERSONAL_URL},
            {"text": f"Or use {ENDPOINT} and send the key on every request as "
                     f"{KEY_HEADER} (or X-API-Key: cs_live_...). A client that "
                     "only speaks stdio can bridge with:"},
            {"lang": "sh", "code": f"npx mcp-remote {PERSONAL_URL} --transport http-only"},
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
> to leave, as a public MCP server. Hosted endpoint (streamable HTTP, free
> API key required): {ENDPOINT}

CommuteScout ({SITE}) is a live road map, a driving app and an MCP server
built on the same data: state DOT, highway patrol and 511 feeds, NWS
weather, wildfires, cameras, message signs, TomTom traffic and an archive
of past events. The MCP server lets an assistant answer "what's a good time to
drive to X?", "is the pass on my route open?" or "what's going on near me?"
with live data.

## Install the MCP server

Endpoint: `{ENDPOINT}` (streamable HTTP). Every request needs a
CommuteScout API key (free; see "API keys" below). Without one the server
answers 401 with code `missing_key`.

The easiest setup, in every client: the user's personal link,
`{PERSONAL_URL}` with their key in place of `{KEY_PLACEHOLDER}`. It is
the endpoint with the key as the last path segment, so it works in apps
that cannot send a header (ChatGPT, claude.ai). {LINK_NOTE}
Pick the user's client:

{clients}

After connecting, check it with a question such as "When should I leave
for work tomorrow morning?" (or name your own start and end). The
assistant should call `best_time_to_go`.

## API keys (required)

The hosted MCP server and the REST API need a key. The user gets one free
at {KEY_PAGE}: Settings, sign in, then API keys. It is shown once.
Send it on every request as `{KEY_HEADER}` or `X-API-Key: cs_live_...`.
Free keys get 2,000 requests a day (Pro: 10,000), counted once per account
across all of its keys. The key also lets "home", "work" and the names of
the user's saved places work in every trip tool. An agent cannot create a
key for the user: ask them to create one and paste it, and keep it out of
shared files. Discovery needs no key: this file, the server card and
the OpenAPI document.

The server cannot see the user's device location. For "from here", pass
coordinates or a city you already know, or ask.

## Tools

- Trips: `plan_trip`, `best_time_to_go`, `find_place`, `get_my_places`
- Around a place: `get_nearby_events`, `get_weather`, `get_traffic`,
  `get_area_history`
- California only (extra depth there; use the tools above for every
  other state): `check_route`, `check_region`, `rank_routes`,
  `get_incidents`, `get_lane_closures`, `get_chain_controls`,
  `get_wildfires`, `get_cameras`, `get_road_signs`
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
    return {"endpoint": ENDPOINT, "key_header": KEY_HEADER,
            "key_placeholder": KEY_PLACEHOLDER, "personal_url": PERSONAL_URL,
            "link_note": LINK_NOTE, "clients": CLIENTS}


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
                "required": True,
                "schemes": ["bearer"],
                "header": "Authorization",
                "description": "CommuteScout API key (cs_live_...), required. "
                               f"Free at {KEY_PAGE} (Settings, then API keys); "
                               "also enables saved places.",
            },
        }],
        "capabilities": {"tools": True, "resources": True, "prompts": True},
    }
