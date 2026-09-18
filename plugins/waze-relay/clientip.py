"""Which address a limit is counted against.

The same reasoning as the main repository's ``ca_roads_mcp.ratelimit``, kept
here rather than imported because the plugin ships as a service of its own
with no dependency on that package.

Two rules, and both of them matter:

* Cloud Run APPENDS the address it actually saw to ``X-Forwarded-For``, so
  the last entry is the only one infrastructure vouched for. Trusting the
  first entry lets a caller put whatever it likes in the header and get a
  fresh bucket per request.
* An IPv6 client is folded to its /64. A residential allocation is one /64
  holding 2**64 addresses, so a caller rotating the low bits would otherwise
  get an unlimited supply of buckets.

There is no Cloudflare case here on purpose. The relay is reached at its own
run.app address, not through a proxy, so ``CF-Connecting-IP`` would be a
header the caller chose. Honouring it would reopen the hole the last-entry
rule closes.
"""

from __future__ import annotations

import ipaddress

from starlette.requests import Request


def trusted_client_ip(forwarded_for: str | None, peer: str | None) -> str:
    """The address the fronting infrastructure vouched for."""
    if forwarded_for:
        entries = [e.strip() for e in forwarded_for.split(",") if e.strip()]
        if entries:
            return entries[-1]
    return peer or "unknown"


def limiter_key(ip: str) -> str:
    """The identity a limit is keyed on: the address for IPv4, the /64 for
    IPv6, and anything that is not an address passed through."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if addr.version == 6:
        mapped = addr.ipv4_mapped
        if mapped is not None:
            return str(mapped)
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return ip


def key_for(request: Request) -> str:
    """The bucket key for one request."""
    return limiter_key(trusted_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None))
