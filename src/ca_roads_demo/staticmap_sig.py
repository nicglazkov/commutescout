"""Signed static map URLs.

/api/staticmap composes an image from paid Stadia tiles, and it is
reachable by anyone. Only two places mint its URLs (alert emails and
the trip share page), so those URLs carry an HMAC of their parameters
and the handler refuses everything else. Gmail's image proxy refetches
the same URL, so the signature keeps working per open. Without a
signing key (dev, CI, self-hosters who never set one) the check is off.
The key is its own secret, STATICMAP_SIGNING_KEY: sharing another
secret would make rotating that one silently break every image in
every alert email already sent.
"""

from __future__ import annotations

import hashlib
import hmac
import os


def _key() -> bytes:
    return os.environ.get("STATICMAP_SIGNING_KEY", "").strip().encode()


def sign(lat: str, lon: str, z: str, kind: str) -> str:
    msg = f"{lat}|{lon}|{z}|{kind}".encode()
    return hmac.new(_key(), msg, hashlib.sha256).hexdigest()[:24]


def query(lat: float, lon: float, z: int, kind: str, sep: str = "&") -> str:
    """The query string a minted URL carries, signed when a key is set.
    ``sep`` is "&amp;" inside HTML attributes."""
    lat_s, lon_s, z_s = f"{lat:.4f}", f"{lon:.4f}", str(z)
    parts = [f"lat={lat_s}", f"lon={lon_s}", f"z={z_s}", f"k={kind}"]
    if _key():
        parts.append(f"s={sign(lat_s, lon_s, z_s, kind)}")
    return sep.join(parts)


def verify(params) -> bool:
    """True when the request's parameters carry a valid signature, or
    when no signing key is configured."""
    if not _key():
        return True
    want = sign(params.get("lat", ""), params.get("lon", ""),
                params.get("z", "11"), params.get("k", "incident"))
    return hmac.compare_digest(params.get("s", ""), want)
