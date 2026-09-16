"""Stadia Maps request headers, one place.

The key travels in the Authorization header, never in the URL: request
URLs get logged. Every server-side Stadia call (routing, geocoding,
autocomplete, static map tiles) builds its headers here.
"""

from __future__ import annotations


def auth_headers(api_key: str, user_agent: str) -> dict[str, str]:
    return {"User-Agent": user_agent, "Authorization": f"Stadia-Auth {api_key}"}
