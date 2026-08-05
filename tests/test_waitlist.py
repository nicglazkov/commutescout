"""POST /api/waitlist: the Pro waitlist.

Firestore is replaced with an in-memory twin reached through
`watch.get_store()`, the same seam `tests/test_watch.py` monkeypatches,
so these tests exercise the real handler without credentials or network.
"""
import hashlib

from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch


def _firestore_document_segments(collection_name, doc_id):
    """Mirrors google-cloud-firestore's collection().document(doc_id)
    path parsing, just enough to catch the waitlist doc-id bug: doc_id
    is split on "/"; combined with the one already-consumed collection
    segment, the total must be even to name a document. An even number
    of "/"-split segments in doc_id makes the total odd (names a
    collection, not a document) -- the real client raises. An odd
    number keeps the total even but, when doc_id has more than one
    segment, nests the "document" inside a sub-collection instead of
    landing in the flat top-level collection. A raw email used as a
    doc id can hit either case; a hashed id (single segment, no "/")
    always takes the flat, one-segment path."""
    segments = doc_id.split("/")
    if len(segments) % 2 == 0:
        raise ValueError(
            f"{collection_name}/{doc_id} names a collection, not a document")
    return segments


class MemoryWaitlistStore:
    """In-memory stand-in matching FirestoreStore.add_waitlist_email.

    Mirrors the real store's id derivation (sha256 hex digest of the
    lowercased address) and Firestore's document-path parsing, instead
    of a naive set/dict keyed by the raw address. A regression back to
    "raw email as doc id" -- which breaks on a "/" in the local part --
    shows up here the same way it would against real Firestore: a
    ValueError (surfaced by the handler as 503) or a document landing
    outside the flat top-level collection, instead of passing trivially
    because a Python dict does not care what characters a key contains.
    """

    def __init__(self):
        self.docs = {}     # flat "waitlist" collection: doc_id -> data
        self.nested = {}   # anything a raw multi-segment id would nest under

    async def add_waitlist_email(self, email):
        key = email.lower()
        doc_id = hashlib.sha256(key.encode()).hexdigest()
        return self._put(doc_id, key)

    def _put(self, doc_id, key):
        segments = _firestore_document_segments("waitlist", doc_id)
        if len(segments) == 1:
            if doc_id in self.docs:
                return False
            self.docs[doc_id] = {"email": key}
            return True
        node = self.nested
        for seg in segments[:-1]:
            node = node.setdefault(seg, {})
        if segments[-1] in node:
            return False
        node[segments[-1]] = {"email": key}
        return True

    @property
    def emails(self):
        return {d["email"] for d in self.docs.values()}

    def seed(self, email):
        """Pre-populate a signup, using the same id derivation as
        add_waitlist_email, for tests that need a pre-existing entry."""
        key = email.lower()
        doc_id = hashlib.sha256(key.encode()).hexdigest()
        self._put(doc_id, key)


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
    store.seed("a@b.co")
    c = _client(monkeypatch, store)
    r = c.post("/api/waitlist", data={"email": "a@b.co", "website": ""})
    assert r.status_code == 200          # same message, no error
    assert store.emails == {"a@b.co"}
    assert len(store.docs) == 1


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


def test_one_slash_email_is_accepted_and_stored_flat(monkeypatch):
    """Legal local-part slash (a/b@c.d): as a raw doc id this is two
    "/"-split segments, which the real client rejects as naming a
    collection, not a document. The hashed id must sidestep that and
    land in exactly one flat document."""
    store = MemoryWaitlistStore()
    c = _client(monkeypatch, store)
    email = "a/b@c.d"
    r = c.post("/api/waitlist", data={"email": email, "website": ""})
    assert r.status_code == 200
    assert store.emails == {email}
    assert len(store.docs) == 1          # one flat document, not nested
    assert not store.nested

    r2 = c.post("/api/waitlist", data={"email": email, "website": ""})
    assert r2.status_code == 200
    assert len(store.docs) == 1          # resubmission dedupes


def test_two_slash_email_is_accepted_and_stored_flat(monkeypatch):
    """Two local-part slashes (a/b/c@d.e): as a raw doc id this is
    three "/"-split segments, which the real client accepts but nests
    as waitlist/a/b/c@d.e, outside the flat top-level collection. The
    hashed id must keep this one flat document instead."""
    store = MemoryWaitlistStore()
    c = _client(monkeypatch, store)
    email = "a/b/c@d.e"
    r = c.post("/api/waitlist", data={"email": email, "website": ""})
    assert r.status_code == 200
    assert store.emails == {email}
    assert len(store.docs) == 1
    assert not store.nested

    r2 = c.post("/api/waitlist", data={"email": email, "website": ""})
    assert r2.status_code == 200
    assert len(store.docs) == 1          # resubmission dedupes
