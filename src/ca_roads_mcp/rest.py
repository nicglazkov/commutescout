"""A REST bridge over the MCP tools: ``GET /v1/tools/{name}?param=...``.

Developers who are not running an MCP client get the same ten tools as
plain HTTP with an OpenAPI document generated from the tools' own JSON
schemas, so the two surfaces cannot drift. The MCP transport at ``/mcp``
is untouched and the rate limiter wraps both.

Contract (additive changes only within ``/v1``):

- One error envelope: ``{"error": {"code", "message", "hint"}}``.
- Query parameters map one to one onto the tool's arguments; pydantic
  coerces ``"1.5"`` and ``"true"`` the way an MCP client's JSON would.
- ``Access-Control-Allow-Origin: *`` on every ``/v1`` response, so a
  browser page can call it directly.
"""

from __future__ import annotations

import textwrap
from importlib import metadata
from typing import Any

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

PREFIX = "/v1"
PUBLIC_BASE = "https://mcp.commutescout.com"
CORS = {"Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type",
        "Access-Control-Max-Age": "86400"}


def _version() -> str:
    try:
        return metadata.version("ca-roads-mcp")
    except metadata.PackageNotFoundError:  # pragma: no cover - source checkout
        return "0"


def error(status: int, code: str, message: str, hint: str | None = None) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if hint:
        body["hint"] = hint
    return JSONResponse({"error": body}, status_code=status, headers=CORS)


def _param_schema(prop: dict) -> dict:
    """The query-parameter schema for one argument: ``anyOf [T, null]``
    collapses to ``T`` because a query string cannot carry null."""
    if "anyOf" in prop:
        options = [o for o in prop["anyOf"] if o.get("type") != "null"]
        if len(options) == 1:
            prop = {**prop, **options[0]}
            prop.pop("anyOf", None)
    out = {k: v for k, v in prop.items() if k in ("type", "enum", "default", "format",
                                                    "minimum", "maximum")}
    return out or {"type": "string"}


def _describe(text: str | None) -> str:
    return textwrap.dedent(text or "").strip()


def tool_specs(mcp) -> list[dict]:
    """Name, description and argument schema for every registered tool."""
    specs = []
    for tool in mcp._tool_manager.list_tools():
        schema = tool.parameters or {}
        specs.append({
            "name": tool.name,
            "description": _describe(tool.description),
            "properties": schema.get("properties", {}),
            "required": list(schema.get("required", [])),
        })
    return specs


def openapi(mcp) -> dict:
    paths: dict[str, Any] = {}
    for spec in tool_specs(mcp):
        params = []
        for name, prop in spec["properties"].items():
            params.append({
                "name": name, "in": "query",
                "required": name in spec["required"],
                "description": prop.get("description", ""),
                "schema": _param_schema(prop),
            })
        summary = spec["description"].split("\n", 1)[0][:120]
        paths[f"{PREFIX}/tools/{spec['name']}"] = {"get": {
            "operationId": spec["name"],
            "summary": summary,
            "description": spec["description"],
            "parameters": params,
            "responses": {
                "200": {"description": "The tool's result.",
                        "content": {"application/json": {"schema": {"type": "object"}}}},
                "400": {"$ref": "#/components/responses/BadRequest"},
                "401": {"$ref": "#/components/responses/InvalidKey"},
                "429": {"$ref": "#/components/responses/RateLimited"},
            },
        }}
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "CommuteScout API",
            "version": _version(),
            "description": (
                "Live US road conditions: incidents, closures, chain controls, "
                "wildfires, cameras and message signs, California in the most "
                "depth and live events across every covered state. The same ten "
                "tools the MCP server exposes, as plain HTTP GET. Works without a "
                "key at per-address limits; a key from Settings on commutescout.com/map "
                "gives 2,000 requests a day (Pro: 10,000). Attribution to CommuteScout "
                "and the agencies named in each response is required."),
        },
        "servers": [{"url": PUBLIC_BASE}],
        "security": [{}, {"ApiKey": []}, {"BearerKey": []}],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "ApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key",
                           "description": "A key from Settings on commutescout.com/map. "
                                          "Optional: without one, per-address limits apply."},
                "BearerKey": {"type": "http", "scheme": "bearer",
                              "description": "The same key as a bearer token."},
            },
            "schemas": {"Error": {
                "type": "object",
                "properties": {"error": {"type": "object", "properties": {
                    "code": {"type": "string"}, "message": {"type": "string"},
                    "hint": {"type": "string"}}, "required": ["code", "message"]}},
                "required": ["error"],
            }},
            "responses": {
                "BadRequest": {"description": "A parameter is missing, unknown or malformed.",
                               "content": {"application/json": {
                                   "schema": {"$ref": "#/components/schemas/Error"}}}},
                "InvalidKey": {"description": "The API key is unknown or revoked.",
                               "content": {"application/json": {
                                   "schema": {"$ref": "#/components/schemas/Error"}}}},
                "RateLimited": {"description": "Slow down; Retry-After says how long.",
                                "content": {"application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}}}},
            },
        },
    }


DOCS_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CommuteScout API</title>
<style>body{margin:0;font-family:Inter,system-ui,sans-serif}</style>
</head><body>
<div id="redoc"></div>
<script src="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js"
  integrity="sha384-0GrsyTQc9Oqd8h+b2dbc4XdR2T/DYpy0tLNNstyx+LBMUyiBbcWPbEs9aRmUcaxD"
  crossorigin="anonymous"></script>
<script>Redoc.init('/v1/openapi.json', {hideDownloadButton: false},
  document.getElementById('redoc'))</script>
</body></html>
"""


def register(mcp) -> None:
    """Mount the bridge on ``mcp`` (before ``streamable_http_app()`` runs)."""
    from mcp.server.fastmcp.exceptions import ToolError

    @mcp.custom_route(f"{PREFIX}/openapi.json", methods=["GET"])
    async def openapi_doc(_: Request) -> Response:
        return JSONResponse(openapi(mcp), headers={**CORS, "Cache-Control": "public, max-age=300"})

    @mcp.custom_route(f"{PREFIX}/docs", methods=["GET"])
    async def docs(_: Request) -> Response:
        return HTMLResponse(DOCS_HTML, headers={"Cache-Control": "public, max-age=300"})

    @mcp.custom_route(PREFIX, methods=["GET"])
    async def index(_: Request) -> Response:
        tools = [{"name": s["name"], "url": f"{PUBLIC_BASE}{PREFIX}/tools/{s['name']}",
                  "summary": s["description"].split("\n", 1)[0][:120]}
                 for s in tool_specs(mcp)]
        return JSONResponse({"version": _version(), "docs": f"{PUBLIC_BASE}{PREFIX}/docs",
                             "openapi": f"{PUBLIC_BASE}{PREFIX}/openapi.json",
                             "mcp": f"{PUBLIC_BASE}/mcp", "tools": tools}, headers=CORS)

    @mcp.custom_route(f"{PREFIX}/tools/{{name}}", methods=["GET", "OPTIONS"])
    async def call(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=CORS)
        name = request.path_params["name"]
        tool = mcp._tool_manager.get_tool(name)
        if tool is None:
            return error(404, "unknown_tool", f"No tool named {name!r}.",
                         f"See {PUBLIC_BASE}{PREFIX} for the list.")
        props = (tool.parameters or {}).get("properties", {})
        args: dict[str, Any] = {}
        for key, value in request.query_params.items():
            if key not in props:
                return error(400, "unknown_parameter", f"{name} has no parameter {key!r}.",
                             "Accepted: " + ", ".join(props) + ".")
            args[key] = value
        missing = [r for r in (tool.parameters or {}).get("required", []) if r not in args]
        if missing:
            return error(400, "missing_parameter",
                         f"{name} needs {', '.join(missing)}.",
                         f"See {PUBLIC_BASE}{PREFIX}/docs#operation/{name}.")
        try:
            tool.fn_metadata.arg_model.model_validate(args)
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(p) for p in first.get("loc", ())) or "parameters"
            return error(400, "invalid_parameter", f"{where}: {first.get('msg', 'invalid')}.")
        try:
            result = await tool.run(args)
        except ToolError as exc:
            return error(400, "tool_error", str(exc))
        except Exception:  # noqa: BLE001 - one envelope for the caller, the log has the trace
            import logging

            logging.getLogger("ca_roads_mcp.rest").exception("tool %s failed", name)
            return error(502, "upstream_error",
                         "The tool could not complete; a source feed may be down.",
                         "Retry in a minute.")
        # A tool that answers {"error": "..."} is refusing the request as
        # given (a malformed center, an unknown region): that is the
        # caller's mistake, so it is a 400 in the one envelope, never a
        # 200 that a navigation client would read as "nothing nearby".
        if isinstance(result, dict) and isinstance(result.get("error"), str):
            return error(400, "invalid_parameter", result["error"],
                         f"See {PUBLIC_BASE}{PREFIX}/docs#operation/{name}.")
        return JSONResponse(result, headers={**CORS, "Cache-Control": "no-store"})
