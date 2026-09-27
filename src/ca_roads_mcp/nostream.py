"""No idle notification stream on the MCP endpoint.

Streamable HTTP lets a client open a GET on the endpoint and hold it for
messages the server sends on its own. This server runs stateless and
never sends one, so the stream only ever sits there until Cloud Run
cuts it at the five-minute request timeout, and the client opens the
next. Measured 2026-09-27: about 300 of those a day, each logged as a
"truncated response body" warning, and together they held the service
awake every hour of the day although it is meant to scale to zero.

The spec's answer for a server with no stream to offer is 405 Method
Not Allowed on that GET, which tells a client not to open one. Every
other request passes through untouched.
"""
from __future__ import annotations

import json

ALLOW = b"POST"


class NoIdleStream:
    def __init__(self, app, path: str = "/mcp") -> None:
        self.app = app
        self.path = path.rstrip("/")

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and scope["method"] == "GET"
                and scope["path"].rstrip("/") == self.path):
            body = json.dumps({"error": "This endpoint has no event stream; "
                                        "send JSON-RPC requests with POST."}).encode()
            await send({"type": "http.response.start", "status": 405,
                        "headers": [(b"allow", ALLOW),
                                    (b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
