"""Baseline hardening headers for the API host.

The map site has carried these since the redesign; the API host,
mcp.commutescout.com, answered with none of them. Most of its responses
are JSON, where a content-security-policy mostly matters as a backstop
against a response being rendered as a page, but the one HTML page it
serves, the reference under /v1/docs, loads Redoc from a CDN and is
exactly the kind of page that wants a policy.

HSTS is a year with subdomains, matching the site. The policy for HTML
allows what Redoc needs and nothing else; every other response gets a
policy that allows nothing at all.
"""
from __future__ import annotations

COMMON = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"permissions-policy", b"geolocation=(), camera=(), microphone=(), payment=()"),
]

# The reference page: Redoc's bundle from jsdelivr, its inline boot
# script, its inline styles, Google Fonts, the OpenAPI document from
# this origin, and the web worker it builds from a blob.
HTML_CSP = (
    b"default-src 'none'; "
    b"base-uri 'none'; "
    b"object-src 'none'; "
    b"frame-ancestors 'none'; "
    b"form-action 'none'; "
    b"script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    b"style-src 'unsafe-inline' https://fonts.googleapis.com; "
    b"font-src https://fonts.gstatic.com; "
    b"img-src 'self' data: https:; "
    b"connect-src 'self'; "
    b"worker-src blob:"
)
# Everything else is data, not a document.
DATA_CSP = b"default-src 'none'; frame-ancestors 'none'"


def _is_html(headers: list) -> bool:
    for name, value in headers:
        if name.lower() == b"content-type":
            return value.lower().startswith(b"text/html")
    return False


class SecurityHeaders:
    """ASGI middleware adding the headers above to every HTTP response."""

    def __init__(self, app_) -> None:
        self.app = app_

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_secure(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.extend(COMMON)
                headers.append((b"content-security-policy",
                                HTML_CSP if _is_html(headers) else DATA_CSP))
            await send(message)

        await self.app(scope, receive, send_secure)
