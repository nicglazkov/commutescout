"""Turning a signed-in caller into an opaque session key.

The app sends a Firebase ID token. This module checks it and throws almost
all of it away: what comes back is a keyed hash of the token's subject, long
enough to tell two people apart and useless for anything else. The token, the
account id, the email and the name are never stored, never logged and never
reach the upstream.

The hashing key is generated at boot unless one is configured, so the keys do
not even survive a restart. Sessions are in memory and die with the process
anyway, so there is nothing to gain by making them outlive it.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time

import httpx

log = logging.getLogger("waze_relay.auth")

PROJECT = os.environ.get("FIREBASE_PROJECT") or "ca-roads-mcp"
ISSUER = f"https://securetoken.google.com/{PROJECT}"
CERTS_URL = ("https://www.googleapis.com/robot/v1/metadata/x509/"
             "securetoken@system.gserviceaccount.com")
CERTS_TTL_S = 3600.0
_SALT = os.environ.get("WAZE_USER_SALT") or secrets.token_hex(32)

_certs: tuple[float, dict] | None = None


async def _google_certs(client: httpx.AsyncClient) -> dict:
    """Google's signing certificates, cached for an hour."""
    global _certs

    if _certs is not None and time.monotonic() - _certs[0] < CERTS_TTL_S:
        return _certs[1]
    response = await client.get(CERTS_URL, timeout=15.0)
    response.raise_for_status()
    _certs = (time.monotonic(), response.json())
    return _certs[1]


def session_key(subject: str) -> str:
    """The opaque, per-process key one signed-in person is known by here."""
    mac = hmac.new(_SALT.encode("utf-8"), subject.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()[:24]


async def verify(token: str, client: httpx.AsyncClient) -> str | None:
    """The session key for a Firebase ID token, or None when it is no good.

    Signature, expiry and audience are checked by google.auth against
    Google's certificates; the issuer and the subject are checked here.
    """
    if not token:
        return None
    try:
        from google.auth import jwt as google_jwt

        claims = google_jwt.decode(token, certs=await _google_certs(client),
                                   audience=PROJECT)
    except Exception:  # noqa: BLE001 - any bad token is just "no"
        return None
    if claims.get("iss") != ISSUER or not claims.get("sub"):
        return None
    return session_key(str(claims["sub"]))


def bearer(header: str | None) -> str:
    """The token out of an Authorization header, or an empty string."""
    if not header or not header.startswith("Bearer "):
        return ""
    return header[7:].strip()
