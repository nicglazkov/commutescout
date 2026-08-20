"""Closure path persistence: deploys must not re-buy routing credits."""

import json

from ca_roads_demo import app as demo_app
from ca_roads_demo import roadsnap


class _FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data


class _FakeDocRef:
    def __init__(self, store, doc_id):
        self._store, self._id = store, doc_id

    async def set(self, data):
        self._store[self._id] = data

    async def delete(self):
        self._store.pop(self._id, None)


class _FakeCollection:
    def __init__(self, store):
        self._store = store

    def document(self, doc_id):
        return _FakeDocRef(self._store, doc_id)

    async def stream(self):
        for doc_id, data in list(self._store.items()):
            yield _FakeDoc(doc_id, data)


class _FakeDb:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        assert name == "closure_paths"
        return _FakeCollection(self.store)


def test_closure_doc_id_is_stable_and_firestore_safe():
    key = (37.3382, -121.8863, 37.7749, -122.4194)
    doc_id = demo_app._closure_doc_id(key)
    assert doc_id == "37.3382_-121.8863_37.7749_-122.4194"
    assert "/" not in doc_id


async def test_closure_paths_round_trip(monkeypatch):
    db = _FakeDb()
    monkeypatch.setattr(roadsnap, "_db", db)
    key = (37.3382, -121.8863, 37.7749, -122.4194)
    path = [[37.3382, -121.8863], [37.5, -122.0], [37.7749, -122.4194]]
    await demo_app._closure_path_store(key, path)
    await demo_app._closure_path_store((38.0, -120.0, 38.1, -120.1), None)
    doc = db.store["37.3382_-121.8863_37.7749_-122.4194"]
    assert json.loads(doc["path"]) == path
    # TTL field present so Firestore can sweep long-unused geometry.
    assert doc["expire_at"] is not None

    loaded: dict = {}
    monkeypatch.setattr(demo_app, "_CLOSURE_PATHS", loaded)
    # Another test's TestClient may have booted the app lifespan and
    # tripped the load-once guard; reset it for this test.
    monkeypatch.setattr(demo_app, "_closure_paths_loaded", False)
    await demo_app._closure_paths_load()
    assert loaded[key] == path
    # A stored None (unroutable stretch) survives as None, not a refetch.
    assert loaded[(38.0, -120.0, 38.1, -120.1)] is None


async def test_closure_paths_load_survives_no_firestore(monkeypatch):
    """Local dev has no ADC: loading must be a silent no-op."""
    def boom():
        raise RuntimeError("no ADC")
    monkeypatch.setattr(roadsnap, "_get_db", boom)
    monkeypatch.setattr(demo_app, "_CLOSURE_PATHS", {})
    monkeypatch.setattr(demo_app, "_closure_paths_loaded", False)
    await demo_app._closure_paths_load()  # must not raise
    assert demo_app._CLOSURE_PATHS == {}
