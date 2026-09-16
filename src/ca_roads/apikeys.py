"""API keys for the public API and the MCP server.

A key belongs to a signed-in account (no accountless keys) and carries a
tier. The secret is stored hashed; the public key id is the document id,
so a lookup is one read and never a scan. Both services resolve keys
through ``KeyResolver`` with a short in-memory cache, and count usage
per key per UTC day with the same ``DailyCounter`` the other budgets use.

Key format: ``cs_live_<id>_<secret>`` where ``id`` is 8 hex characters
and ``secret`` is 32 URL-safe characters. Shown once at creation.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import os
import secrets
import time
from datetime import UTC, datetime

PREFIX = "cs_live_"
MAX_KEYS_PER_ACCOUNT = 5

# Requests per key per UTC day, and the short-term bucket (burst, then
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
        return n


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
    existing = [k for k in await store.list_for(uid) if not k.get("revoked")]
    if len(existing) >= MAX_KEYS_PER_ACCOUNT:
        raise ValueError(f"an account can hold {MAX_KEYS_PER_ACCOUNT} active keys; "
                         "revoke one first")
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
        if now - self._touched.get(key_id, 0.0) > TOUCH_EVERY_S:
            self._touched[key_id] = now
            with contextlib.suppress(Exception):  # a missed timestamp is fine
                await self.store.put(key_id, {"last_used_at": datetime.now(UTC).isoformat()})
        return {"id": key_id, "tier": rec.get("tier") or DEFAULT_TIER, "uid": rec.get("uid")}

    def forget(self, key_id: str) -> None:
        self._cache.pop(key_id, None)
