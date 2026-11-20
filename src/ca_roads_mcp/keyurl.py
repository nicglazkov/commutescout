"""Personal connector links: the key in the URL.

ChatGPT's custom MCP servers cannot send a request header, and claude.ai
only offers request headers to some organizations. Both accept a URL, so
the hosted server also takes the key as the last path segment:

    https://mcp.commutescout.com/mcp/cs_live_<id>_<secret>

This middleware sits outside the key check. It moves the key from the
path into an ``Authorization: Bearer`` header (unless the request already
carries one) and rewrites the path to ``/mcp``, so everything behind it,
the key check, its metering log and the MCP transport, sees an ordinary
keyed request and never logs the key. ``?key=cs_live_...`` on ``/mcp``
works the same way for clients that keep query strings.

A personal link is the key itself: whoever has the link uses the key's
daily allowance and saved places. The setup steps say so, and a key can
be revoked from Settings on the map.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode

from ca_roads.apikeys import PREFIX

# cs_live_ + 8 hex id + _ + token_urlsafe secret.
_KEY = re.compile(re.escape(PREFIX) + r"[0-9a-f]{8}_[A-Za-z0-9_-]{8,64}")
_PATH = re.compile(r"^/mcp/(" + _KEY.pattern + r")/?$")


def key_from_scope(scope) -> tuple[str | None, str, bytes]:
    """(key, path, query) after taking a key out of the path or query."""
    path = scope.get("path", "")
    query = scope.get("query_string") or b""
    m = _PATH.match(path)
    if m:
        return m.group(1), "/mcp", query
    if path in ("/mcp", "/mcp/") and query:
        pairs = parse_qsl(query.decode("latin-1"), keep_blank_values=True)
        keys = [v for k, v in pairs if k == "key" and _KEY.fullmatch(v)]
        if keys:
            rest = [(k, v) for k, v in pairs if k != "key"]
            return keys[0], path, urlencode(rest).encode("latin-1")
    return None, path, query


class KeyInUrl:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        key, path, query = key_from_scope(scope)
        if key is None:
            await self.app(scope, receive, send)
            return
        headers = list(scope.get("headers") or [])
        has_auth = any(k.lower() in (b"authorization", b"x-api-key")
                       for k, _ in headers)
        if not has_auth:
            headers.append((b"authorization", b"Bearer " + key.encode("latin-1")))
        scope = dict(scope, path=path, raw_path=path.encode("latin-1"),
                     query_string=query, headers=headers)
        await self.app(scope, receive, send)
