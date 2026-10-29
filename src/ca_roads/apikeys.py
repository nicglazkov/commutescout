"""API keys for the public API and the MCP server.

A key belongs to a signed-in account (no accountless keys) and carries a
tier. The secret is stored hashed; the public key id is the document id,
so a lookup is one read and never a scan. Both services resolve keys
through ``KeyResolver`` with a short in-memory cache, and count usage
per account per UTC day with the same ``DailyCounter`` the other budgets use.

Key format: ``cs_live_<id>_<secret>`` where ``id`` is 8 hex characters
and ``secret`` is 32 URL-safe characters. Shown once at creation.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import os
import secrets
import time
from datetime import UTC, datetime

PREFIX = "cs_live_"
MAX_KEYS_PER_ACCOUNT = 5
# Revoked keys still count here, so revoke-and-mint cannot churn keys.
MAX_NEW_KEYS_PER_DAY = 10

# Requests per account per UTC day (all its keys together), and the short-term bucket (burst, then
# sustained per second). Free is the default on creation; Pro is set by
# an admin; more than Pro is a conversation (the contact page).
TIERS: dict[str, dict] = {
    "free": {"daily": 2000, "burst": 30, "per_second": 0.5},
    "pro": {"daily": 10000, "burst": 60, "per_second": 2.0},
}
DEFAULT_TIER = "free"
CACHE_TTL_S = 60.0
TOUCH_EVERY_S = 300.0


def new_key() -> tuple[str, str, str]:
    """(key_id, secret, full key). The full key is the only thing the
    account ever sees; only its hash is stored."""
    key_id = secrets.token_hex(4)
    secret = secrets.token_urlsafe(24)
    return key_id, secret, f"{PREFIX}{key_id}_{secret}"


def parse(full: str | None) -> tuple[str, str] | None:
    if not full or not full.startswith(PREFIX):
        return None
    rest = full[len(PREFIX):]
    key_id, sep, secret = rest.partition("_")
    if not sep or len(key_id) != 8 or not secret or len(secret) > 64:
        return None
    return key_id, secret


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def from_headers(get) -> str | None:
    """The presented key: ``Authorization: Bearer cs_live_...`` or
    ``X-API-Key``. ``get`` is a case-insensitive header getter."""
    auth = (get("authorization") or "").strip()
    if auth.lower().startswith("bearer ") and auth[7:].strip().startswith(PREFIX):
        return auth[7:].strip()
    key = (get("x-api-key") or "").strip()
    return key or None


def tier_limits(tier: str | None) -> dict:
    return TIERS.get(tier or DEFAULT_TIER, TIERS[DEFAULT_TIER])


class MemoryKeyStore:
    """In-memory store, and the surface the Firestore one matches."""

    def __init__(self) -> None:
        self.keys: dict[str, dict] = {}
        self.usage: dict[str, dict] = {}

    async def get(self, key_id: str) -> dict | None:
        return dict(self.keys[key_id]) if key_id in self.keys else None

    async def put(self, key_id: str, data: dict) -> None:
        self.keys.setdefault(key_id, {}).update(data)

    async def list_for(self, uid: str) -> list[dict]:
        return [{"id": k, **v} for k, v in self.keys.items() if v.get("uid") == uid]

    async def delete_for(self, uid: str) -> int:
        gone = [k for k, v in self.keys.items() if v.get("uid") == uid]
        for k in gone:
            del self.keys[k]
        return len(gone)

    async def get_usage(self, uid: str) -> dict | None:
        rec = self.usage.get(uid)
        return dict(rec) if rec else None

    async def put_usage(self, uid: str, data: dict) -> None:
        self.usage[uid] = dict(data)


class FirestoreKeyStore:
    """Firestore ``api_keys`` collection, document id = key id."""

    def __init__(self, project: str | None = None) -> None:
        from google.cloud import firestore

        self.db = firestore.AsyncClient(
            project=project or os.environ.get("GOOGLE_CLOUD_PROJECT") or "ca-roads-mcp")

    def _col(self):
        return self.db.collection("api_keys")

    async def get(self, key_id: str) -> dict | None:
        snap = await self._col().document(key_id).get()
        return snap.to_dict() if snap.exists else None

    async def put(self, key_id: str, data: dict) -> None:
        await self._col().document(key_id).set(data, merge=True)

    async def list_for(self, uid: str) -> list[dict]:
        out = []
        async for snap in self._col().where("uid", "==", uid).stream():
            d = snap.to_dict()
            d["id"] = snap.id
            out.append(d)
        return out

    async def delete_for(self, uid: str) -> int:
        n = 0
        async for snap in self._col().where("uid", "==", uid).stream():
            await snap.reference.delete()
            n += 1
        with contextlib.suppress(Exception):
            await self.db.collection("api_usage").document(uid).delete()
        return n

    async def get_usage(self, uid: str) -> dict | None:
        snap = await self.db.collection("api_usage").document(uid).get()
        return snap.to_dict() if snap.exists else None

    async def put_usage(self, uid: str, data: dict) -> None:
        await self.db.collection("api_usage").document(uid).set(data)


_store = None


def get_key_store():
    """The process-wide store; tests swap in a MemoryKeyStore."""
    global _store
    if _store is None:
        _store = FirestoreKeyStore()
    return _store


def set_key_store(store) -> None:
    global _store
    _store = store


# The API service counts each account's requests in memory; the
# account page runs in another service, so the count is mirrored to the
# store at most this often per account (and once more after a burst).
USAGE_FLUSH_S = 60.0


class UsageMirror:
    """Writes an account's request count for the UTC day to the key
    store (``api_usage/{uid}``), throttled, never on the request path."""

    def __init__(self, store_getter=None, flush_s: float = USAGE_FLUSH_S) -> None:
        self._store_getter = store_getter or get_key_store
        self.flush_s = flush_s
        self.latest: dict[str, dict] = {}
        self.written_at: dict[str, float] = {}
        self.pending: set[str] = set()

    @property
    def store(self):
        return self._store_getter()

    def note(self, uid: str, day: str, requests: int, limit: int, tier: str) -> None:
        if not uid:
            return
        if len(self.latest) > 10_000:
            self.latest.clear()
            self.written_at.clear()
        self.latest[uid] = {"day": day, "requests": requests, "limit": limit,
                            "tier": tier}
        if uid in self.pending:
            return
        self.pending.add(uid)
        wait = max(0.0, self.written_at.get(uid, 0.0) + self.flush_s - time.monotonic())
        try:
            asyncio.get_running_loop().create_task(self._flush(uid, wait))
        except RuntimeError:  # no loop (sync caller): skip the mirror
            self.pending.discard(uid)

    async def _flush(self, uid: str, wait: float) -> None:
        try:
            if wait:
                await asyncio.sleep(wait)
            rec = dict(self.latest.get(uid) or {})
            if rec:
                rec["updated_at"] = datetime.now(UTC).isoformat()
                await self.store.put_usage(uid, rec)
            self.written_at[uid] = time.monotonic()
        except Exception:  # noqa: BLE001 - a mirror miss is not an outage
            pass
        finally:
            self.pending.discard(uid)


async def usage_today(store, uid: str, tier: str | None) -> dict:
    """Requests today (UTC) against the account's daily limit, as the
    account page shows it."""
    day = datetime.now(UTC).date().isoformat()
    rec = None
    with contextlib.suppress(Exception):
        rec = await store.get_usage(uid)
    limit = tier_limits(tier)["daily"]
    if rec and rec.get("day") == day:
        return {"day": day, "requests": int(rec.get("requests") or 0),
                "limit": int(rec.get("limit") or limit),
                "as_of": rec.get("updated_at")}
    return {"day": day, "requests": 0, "limit": limit, "as_of": None}


def public_view(key_id: str, rec: dict) -> dict:
    """What an account sees about its key: never the hash."""
    return {
        "id": key_id,
        "prefix": f"{PREFIX}{key_id}_",
        "name": rec.get("name") or "",
        "tier": rec.get("tier") or DEFAULT_TIER,
        "daily_limit": tier_limits(rec.get("tier"))["daily"],
        "created_at": rec.get("created_at"),
        "last_used_at": rec.get("last_used_at"),
        "revoked": bool(rec.get("revoked")),
    }


async def create_key(store, uid: str, email: str, name: str) -> tuple[str, dict]:
    """Mint a key for an account. Returns (full key, public view)."""
    mine = await store.list_for(uid)
    existing = [k for k in mine if not k.get("revoked")]
    if len(existing) >= MAX_KEYS_PER_ACCOUNT:
        raise ValueError(f"an account can hold {MAX_KEYS_PER_ACCOUNT} active keys; "
                         "revoke one first")
    today = datetime.now(UTC).date().isoformat()
    minted = [k for k in mine
              if str(k.get("created_at") or "").startswith(today)]
    if len(minted) >= MAX_NEW_KEYS_PER_DAY:
        raise ValueError(f"an account can create {MAX_NEW_KEYS_PER_DAY} keys a day; "
                         "try again tomorrow (UTC)")
    key_id, secret, full = new_key()
    rec = {
        "uid": uid, "email": (email or "").lower(), "name": (name or "")[:40],
        "tier": DEFAULT_TIER, "hash": digest(secret),
        "created_at": datetime.now(UTC).isoformat(), "last_used_at": None,
        "revoked": False,
    }
    await store.put(key_id, rec)
    return full, public_view(key_id, rec)


class KeyResolver:
    """Turns a presented key into ``{"id", "tier", "uid"}`` or None.

    Records are cached for a minute so a busy client costs one Firestore
    read a minute, and ``last_used_at`` is written at most every five
    minutes per key.
    """

    def __init__(self, store=None) -> None:
        self._store = store
        self._cache: dict[str, tuple[float, dict | None]] = {}
        self._touched: dict[str, float] = {}

    @property
    def store(self):
        if self._store is None:
            self._store = get_key_store()
        return self._store

    async def resolve(self, full: str | None) -> dict | None:
        parsed = parse(full)
        if not parsed:
            return None
        key_id, secret = parsed
        now = time.monotonic()
        hit = self._cache.get(key_id)
        if hit and now - hit[0] < CACHE_TTL_S:
            rec = hit[1]
        else:
            rec = await self.store.get(key_id)
            if len(self._cache) > 5000:
                self._cache.clear()
            self._cache[key_id] = (now, rec)
        if not rec or rec.get("revoked"):
            return None
        if not hmac.compare_digest(rec.get("hash") or "", digest(secret)):
            return None
        # None, not 0.0: a monotonic clock can read under five minutes on
        # a fresh machine, which would skip the first touch entirely.
        last = self._touched.get(key_id)
        if last is None or now - last > TOUCH_EVERY_S:
            self._touched[key_id] = now
            with contextlib.suppress(Exception):  # a missed timestamp is fine
                await self.store.put(key_id, {"last_used_at": datetime.now(UTC).isoformat()})
        return {"id": key_id, "tier": rec.get("tier") or DEFAULT_TIER, "uid": rec.get("uid")}

    def forget(self, key_id: str) -> None:
        self._cache.pop(key_id, None)
