"""GET /api/admin/waitlist: the Pro-waitlist viewer on /admin.

Firestore is replaced with an in-memory twin (mirroring
tests/test_watch.py's MemoryStore) and token verification with a stub,
so these tests exercise the real handler without credentials or
network.
"""
from datetime import UTC, datetime

from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch
from ca_roads_mcp.ratelimit import RateLimiter


class MemoryStore:
    """In-memory stand-in exposing list_waitlist, matching
    FirestoreStore's surface (tests/test_watch.py's MemoryStore
    pattern). rows holds raw {"email": ..., "added": datetime|missing}
    dicts, the same shape FirestoreStore.list_waitlist returns."""

    def __init__(self):
        self.rows: list[dict] = []

    async def list_waitlist(self) -> list[dict]:
        return list(self.rows)


USERS = {
    "tok-sam": {"sub": "sam", "email": "sam@example.com",
                "email_verified": True, "iss": watch.ISSUER},
    "tok-admin": {"sub": "boss", "email": "admin@example.com",
                  "email_verified": True, "iss": watch.ISSUER},
}


def _client(monkeypatch, store):
    monkeypatch.setattr(watch, "get_store", lambda: store)
    monkeypatch.setattr(watch, "ADMIN_EMAILS", {"admin@example.com"})
    # demo_app.app is SecurityHeaders(RateLimitMiddleware(...)); the
    # RateLimitMiddleware layer (demo_app.app.app) wraps one
    # process-lifetime token bucket (capacity 20, 0.5/s refill) shared by
    # every test module that exercises demo_app.app (test_waitlist.py,
    # test_contact.py, etc, all keyed on TestClient's fixed "testclient"
    # peer). Swapping in a fresh limiter here (monkeypatch reverts it
    # after the test) keeps this file's requests from spending down - or
    # being starved by - that shared budget.
    monkeypatch.setattr(demo_app.app.app, "limiter",
                        RateLimiter(capacity=20, refill_per_second=0.5))

    async def fake_verify(request):
        header = request.headers.get("authorization") or ""
        return USERS.get(header.removeprefix("Bearer ").strip())

    monkeypatch.setattr(watch, "verify_user", fake_verify)
    return TestClient(demo_app.app)


def auth(token="tok-admin"):
    return {"Authorization": f"Bearer {token}"}


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=UTC)


def test_admin_gate(monkeypatch):
    store = MemoryStore()
    c = _client(monkeypatch, store)
    assert c.get("/api/admin/waitlist").status_code == 403
    assert c.get("/api/admin/waitlist",
                 headers=auth("tok-sam")).status_code == 403
    store.rows = [{"email": "a@b.co", "added": _dt("2026-01-01T00:00:00")}]
    r = c.get("/api/admin/waitlist", headers=auth("tok-admin"))
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_lists_entries_newest_first(monkeypatch):
    store = MemoryStore()
    store.rows = [
        {"email": "old@example.com", "added": _dt("2026-01-01T00:00:00")},
        {"email": "new@example.com", "added": _dt("2026-06-01T00:00:00")},
    ]
    c = _client(monkeypatch, store)
    data = c.get("/api/admin/waitlist", headers=auth()).json()
    assert data["count"] == 2
    assert [e["email"] for e in data["entries"]] == [
        "new@example.com", "old@example.com"]
    assert data["entries"][0]["added"].startswith("2026-06-01")


def test_missing_added_is_null_and_sorts_last(monkeypatch):
    store = MemoryStore()
    store.rows = [
        {"email": "pending@example.com"},  # SERVER_TIMESTAMP not resolved
        {"email": "known@example.com", "added": _dt("2026-06-01T00:00:00")},
    ]
    c = _client(monkeypatch, store)
    data = c.get("/api/admin/waitlist", headers=auth()).json()
    assert [e["email"] for e in data["entries"]] == [
        "known@example.com", "pending@example.com"]
    assert data["entries"][1]["added"] is None


def test_empty_waitlist(monkeypatch):
    store = MemoryStore()
    c = _client(monkeypatch, store)
    data = c.get("/api/admin/waitlist", headers=auth()).json()
    assert data == {"count": 0, "entries": []}
