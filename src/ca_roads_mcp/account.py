"""The caller's own places: "home", "work", "the gym", "my location".

A request made with a CommuteScout API key (``Authorization: Bearer
cs_live_...``, minted under Settings on the map) belongs to an account,
and an account has the Home, Work, favorites and recent destinations the
site and the apps sync (ca_roads_demo/watch.py, ``places``). The key
middleware puts the resolved key in ``CURRENT`` for the length of the
request, so the trip tools can read "from home" as that account's Home.

A person's places are theirs alone: they are read for the account that
made the request, never cached under anything but its uid, and never
logged.

Without a key there is no account. A self-hosted or stdio server can
still give fixed places through ``MCP_HOME`` and ``MCP_WORK`` ("lat,lon"
or an address).

"My location" is the user's device position, which no MCP server can
see: the tools say so and tell the model to pass coordinates it already
has, or to ask.
"""

from __future__ import annotations

import os
import re
import time
from contextvars import ContextVar

CURRENT: ContextVar[dict | None] = ContextVar("commutescout_api_key", default=None)
TTL_SECONDS = 60.0
_CACHE_MAX = 2000
_cache: dict[str, tuple[float, list[dict]]] = {}

HOME = {"home", "my home", "my house", "house", "my place", "my apartment"}
WORK = {"work", "my work", "office", "my office", "the office", "my job",
        "job", "workplace"}
HERE = {"here", "my location", "current location", "my current location",
        "where i am", "me", "my position", "current position"}

CONNECT_HINT = (
    "To use saved places, connect with a CommuteScout API key (Settings on "
    "commutescout.com/map) sent as 'Authorization: Bearer cs_live_...'; "
    "Home, Work and favorites then come from the user's account.")
HERE_HINT = (
    "This server cannot see the user's device location. If you already know "
    "where they are (coordinates, or a city or address from the "
    "conversation), pass it as the place or as *_coords; otherwise ask them "
    "where they are starting from.")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def wants_here(text: str | None) -> bool:
    return bool(text) and _norm(text) in HERE


def current_uid() -> str | None:
    info = CURRENT.get()
    return (info or {}).get("uid") or None


async def _account_places(uid: str) -> list[dict]:
    hit = _cache.get(uid)
    if hit and time.monotonic() - hit[0] < TTL_SECONDS:
        return hit[1]
    from ca_roads_demo.watch import get_store, merge_places  # noqa: PLC0415

    user = await get_store().get_user(uid) or {}
    places = merge_places(user.get("places") or [], [])
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[uid] = (time.monotonic(), places)
    return places


def _env_places() -> list[dict]:
    out = []
    for kind, var in (("home", "MCP_HOME"), ("work", "MCP_WORK")):
        value = os.environ.get(var, "").strip()
        if value:
            out.append({"kind": kind, "name": kind.title(), "value": value})
    return out


async def places() -> tuple[list[dict], str]:
    """The caller's places and where they came from: "account", "server"
    (MCP_HOME / MCP_WORK) or "none". Entries carry lat/lon, or a
    ``value`` to resolve (an env address)."""
    uid = current_uid()
    if uid:
        try:
            return await _account_places(uid), "account"
        except Exception:  # noqa: BLE001 - the store being down is not fatal
            return [], "account_unavailable"
    env = _env_places()
    return env, ("server" if env else "none")


def match(text: str, saved: list[dict]) -> dict | None:
    """The saved place a phrase names: "home", "work", or a favorite or
    recent by its name ("the gym" matches "Gym" or "Gold's Gym")."""
    t = _norm(text)
    if not t:
        return None
    kind = "home" if t in HOME else "work" if t in WORK else None
    if kind:
        return next((p for p in saved if p.get("kind") == kind), None)
    t = re.sub(r"^(the|my) ", "", t)
    for p in sorted(saved, key=lambda p: p.get("kind") != "saved"):
        name = _norm(p.get("name") or "")
        if name and (name == t or re.search(rf"\b{re.escape(t)}\b", name)):
            return p
    return None


def mentions_saved_kind(text: str | None) -> str | None:
    t = _norm(text or "")
    return "home" if t in HOME else "work" if t in WORK else None
