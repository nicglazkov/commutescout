"""POST /api/waitlist: the Pro waitlist.

Firestore is replaced with an in-memory twin reached through
`watch.get_store()`, the same seam `tests/test_watch.py` monkeypatches,
so these tests exercise the real handler without credentials or network.
"""
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch


class MemoryWaitlistStore:
    """In-memory stand-in matching FirestoreStore.add_waitlist_email."""

    def __init__(self):
        self.emails = set()

    async def add_waitlist_email(self, email):
        if email in self.emails:
            return False
        self.emails.add(email)
        return True


class BrokenStore:
    """Simulates Firestore being unreachable (no ADC locally)."""

    async def add_waitlist_email(self, email):
        raise RuntimeError("no ADC locally")


def _client(monkeypatch, store):
    monkeypatch.setattr(watch, "get_store", lambda: store)
    return TestClient(demo_app.app)


def test_signup_stores_email(monkeypatch):
    store = MemoryWaitlistStore()
    c = _client(monkeypatch, store)
    r = c.post("/api/waitlist", data={"email": "a@b.co", "website": ""})
    assert r.status_code == 200
    assert store.emails == {"a@b.co"}


def test_duplicate_is_idempotent(monkeypatch):
    store = MemoryWaitlistStore()
    store.emails.add("a@b.co")
    c = _client(monkeypatch, store)
    r = c.post("/api/waitlist", data={"email": "a@b.co", "website": ""})
    assert r.status_code == 200          # same message, no error
    assert store.emails == {"a@b.co"}


def test_honeypot_and_bad_email(monkeypatch):
    store = MemoryWaitlistStore()
    c = _client(monkeypatch, store)
    assert c.post("/api/waitlist", data={"email": "a@b.co",
                                         "website": "x"}).status_code == 200
    assert c.post("/api/waitlist", data={"email": "not-an-email",
                                         "website": ""}).status_code == 400
    assert not store.emails


def test_store_failure_gives_503(monkeypatch):
    c = _client(monkeypatch, BrokenStore())
    r = c.post("/api/waitlist", data={"email": "a@b.co", "website": ""})
    assert r.status_code == 503


def test_embedded_newline_in_email_is_stripped(monkeypatch):
    store = MemoryWaitlistStore()
    c = _client(monkeypatch, store)
    r = c.post("/api/waitlist",
               data={"email": "a@b.co\r\nBcc:evil@x.com", "website": ""})
    assert r.status_code == 200
    assert store.emails == {"a@b.cobcc:evil@x.com"}
