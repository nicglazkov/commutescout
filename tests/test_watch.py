"""Watch-area gating, validation, admin, and check-cycle behavior.

Firestore is replaced with an in-memory twin and token verification with
a stub, so these tests exercise the real handlers and checker logic
without credentials or network.
"""

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from ca_roads_demo import watch


def _firestore_would_reject(value, inside_array=False):
    """Firestore refuses arrays nested inside arrays; the production
    polygon-500 slipped through because this store did not. Mimic the
    restriction so storage-shape bugs fail here first."""
    if isinstance(value, list | tuple):
        return inside_array or any(
            _firestore_would_reject(v, inside_array=True) for v in value)
    if isinstance(value, dict):
        return any(_firestore_would_reject(v) for v in value.values())
    return False


class MemoryStore:
    """In-memory stand-in matching FirestoreStore's surface."""

    def __init__(self):
        self.users = {}
        self.codes = {}
        self.watches = {}
        self.subs = {}
        self.seen = {}
        self._next = 0

    async def get_user(self, uid):
        return dict(self.users[uid]) if uid in self.users else None

    async def upsert_user(self, uid, data):
        self.users.setdefault(uid, {}).update(data)

    async def delete_user(self, uid):
        self.users.pop(uid, None)

    async def list_users(self):
        return [{"uid": k, **v} for k, v in self.users.items()]

    async def get_code(self, code):
        return dict(self.codes[code]) if code in self.codes else None

    async def upsert_code(self, code, data):
        self.codes.setdefault(code, {}).update(data)

    async def increment_code_use(self, code):
        self.codes[code]["uses"] = self.codes[code].get("uses", 0) + 1

    async def list_codes(self):
        return [{"code": k, **v} for k, v in self.codes.items()]

    async def list_watches(self, uid=None):
        return [{"id": k, **v} for k, v in self.watches.items()
                if uid is None or v["uid"] == uid]

    async def create_watch(self, data):
        if _firestore_would_reject(data):
            raise ValueError("400 Nested arrays are not allowed")
        self._next += 1
        wid = f"w{self._next}"
        self.watches[wid] = dict(data)
        return wid

    async def update_watch(self, watch_id, data):
        if _firestore_would_reject(data):
            raise ValueError("400 Nested arrays are not allowed")
        self.watches[watch_id].update(data)

    async def get_watch(self, watch_id):
        return (dict(self.watches[watch_id])
                if watch_id in self.watches else None)

    async def delete_watch(self, watch_id):
        self.watches.pop(watch_id, None)
        self.seen.pop(watch_id, None)

    async def list_push_subs(self, uid):
        return [{"id": k, **v} for k, v in self.subs.items()
                if v["uid"] == uid]

    async def upsert_push_sub(self, sub_id, data):
        self.subs[sub_id] = dict(data)

    async def delete_push_sub(self, sub_id):
        self.subs.pop(sub_id, None)

    async def get_seen(self, watch_id):
        if watch_id not in self.seen:
            return None
        return set(self.seen[watch_id])

    async def set_seen(self, watch_id, seen):
        self.seen[watch_id] = set(seen)


def make_app():
    return Starlette(routes=[
        Route("/api/watch/config", watch.api_watch_config),
        Route("/api/watch/me", watch.api_watch_me),
        Route("/api/watch/redeem", watch.api_watch_redeem, methods=["POST"]),
        Route("/api/watch/create", watch.api_watch_create, methods=["POST"]),
        Route("/api/watch/push", watch.api_push_subscribe, methods=["POST"]),
        Route("/api/watch/account", watch.api_account_delete,
              methods=["DELETE"]),
        Route("/api/watch/{watch_id}", watch.api_watch_delete,
              methods=["DELETE"]),
        Route("/api/watch/{watch_id}", watch.api_watch_update,
              methods=["PATCH"]),
        Route("/api/admin/overview", watch.api_admin_overview),
        Route("/api/admin/user", watch.api_admin_user, methods=["POST"]),
        Route("/api/admin/code", watch.api_admin_code, methods=["POST"]),
        Route("/api/check-watches", watch.api_check_watches,
              methods=["POST"]),
    ])


USERS = {
    "tok-sam": {"sub": "sam", "email": "sam@example.com",
                "email_verified": True, "iss": watch.ISSUER},
    "tok-admin": {"sub": "boss", "email": "nic@glazkov.com",
                  "email_verified": True, "iss": watch.ISSUER},
}


@pytest.fixture
def store(monkeypatch):
    mem = MemoryStore()
    monkeypatch.setattr(watch, "get_store", lambda: mem)

    async def fake_verify(request):
        header = request.headers.get("authorization") or ""
        return USERS.get(header.removeprefix("Bearer ").strip())

    monkeypatch.setattr(watch, "verify_user", fake_verify)
    return mem


@pytest.fixture
def client(store):
    return TestClient(make_app())


def auth(token="tok-sam"):
    return {"Authorization": f"Bearer {token}"}


CIRCLE = {"type": "circle", "name": "Home", "kinds": ["incident"],
          "center": {"lat": 37.3, "lon": -121.9}, "radius_km": 20}


async def approve(store, uid="sam"):
    await store.upsert_user(uid, {"email": f"{uid}@example.com",
                                  "status": "approved"})


# ---------------------------------------------------------------- access

def test_config_is_public(client):
    data = client.get("/api/watch/config").json()
    assert data["limits"]["watches"] == watch.MAX_WATCHES
    assert data["firebase"]["projectId"] == watch.PROJECT


def test_everything_else_requires_sign_in(client):
    assert client.get("/api/watch/me").status_code == 401
    assert client.post("/api/watch/create", json=CIRCLE).status_code == 401


def test_first_sign_in_lands_pending(client, store):
    data = client.get("/api/watch/me", headers=auth()).json()
    assert data["status"] == "pending"
    assert store.users["sam"]["email"] == "sam@example.com"


def test_pending_users_cannot_create(client):
    r = client.post("/api/watch/create", json=CIRCLE, headers=auth())
    assert r.status_code == 403


def test_code_redemption_approves(client, store):
    store.codes["ROADS-AA11BB"] = {"active": True, "max_uses": 2, "uses": 1}
    r = client.post("/api/watch/redeem", json={"code": "roads-aa11bb"},
                    headers=auth())
    assert r.json()["status"] == "approved"
    assert store.codes["ROADS-AA11BB"]["uses"] == 2
    assert store.users["sam"]["status"] == "approved"


def test_bad_or_exhausted_codes_refuse(client, store):
    store.codes["ROADS-USED"] = {"active": True, "max_uses": 1, "uses": 1}
    store.codes["ROADS-OFF"] = {"active": False, "max_uses": 5, "uses": 0}
    for code in ("ROADS-NOPE", "ROADS-USED", "ROADS-OFF"):
        r = client.post("/api/watch/redeem", json={"code": code},
                        headers=auth())
        assert r.status_code == 403, code


# ---------------------------------------------------------------- watches

@pytest.fixture
def approved_client(client, store):
    store.users["sam"] = {"email": "sam@example.com", "status": "approved"}
    return client


def test_create_circle_watch(approved_client, store):
    r = approved_client.post("/api/watch/create", json=CIRCLE, headers=auth())
    assert r.status_code == 200
    assert store.watches[r.json()["id"]]["radius_km"] == 20


def test_radius_clamps_to_trial_cap(approved_client):
    body = {**CIRCLE, "radius_km": 500}
    r = approved_client.post("/api/watch/create", json=body, headers=auth())
    assert r.json()["radius_km"] == watch.MAX_RADIUS_KM


def test_rejects_outside_california(approved_client):
    body = {**CIRCLE, "center": {"lat": 40.7, "lon": -74.0}}  # NYC
    r = approved_client.post("/api/watch/create", json=body, headers=auth())
    assert r.status_code == 400


def test_polygon_needs_three_points_inside_ca(approved_client):
    base = {"type": "polygon", "name": "Tahoe", "kinds": ["chain"]}
    two = {**base, "points": [[39.0, -120.0], [39.2, -120.1]]}
    assert approved_client.post("/api/watch/create", json=two,
                                headers=auth()).status_code == 400
    good = {**base, "points": [[38.9, -120.2], [39.2, -120.2],
                               [39.2, -120.1]]}
    assert approved_client.post("/api/watch/create", json=good,
                                headers=auth()).status_code == 200


def test_polygon_stores_firestore_safe_points(approved_client, store):
    body = {"type": "polygon", "name": "Tahoe", "kinds": ["fire"],
            "points": [[38.9, -120.2], [39.2, -120.2], [39.2, -120.1]]}
    wid = approved_client.post("/api/watch/create", json=body,
                               headers=auth()).json()["id"]
    stored = store.watches[wid]["points"]
    assert stored[0] == {"lat": 38.9, "lon": -120.2}
    # And the checker matches against the stored dict form.
    assert watch.watch_matches(store.watches[wid], 39.05, -120.15)
    assert not watch.watch_matches(store.watches[wid], 37.0, -122.0)


def test_watch_count_cap(approved_client):
    for _ in range(watch.MAX_WATCHES):
        assert approved_client.post("/api/watch/create", json=CIRCLE,
                                    headers=auth()).status_code == 200
    r = approved_client.post("/api/watch/create", json=CIRCLE,
                             headers=auth())
    assert r.status_code == 403


def test_delete_is_owner_only(approved_client, store):
    wid = approved_client.post("/api/watch/create", json=CIRCLE,
                               headers=auth()).json()["id"]
    store.users["boss"] = {"email": "nic@glazkov.com", "status": "approved"}
    assert approved_client.delete(f"/api/watch/{wid}",
                                  headers=auth("tok-admin")).status_code == 404
    assert approved_client.delete(f"/api/watch/{wid}",
                                  headers=auth()).status_code == 200
    assert wid not in store.watches


def test_push_subscribe_validates_and_caps(approved_client, store):
    bad = {"subscription": {"endpoint": "http://insecure", "keys": {}}}
    assert approved_client.post("/api/watch/push", json=bad,
                                headers=auth()).status_code == 400
    for i in range(watch.MAX_PUSH_SUBS):
        sub = {"subscription": {
            "endpoint": f"https://fcm.googleapis.com/fcm/send/dev{i}",
            "keys": {"p256dh": "k", "auth": "x"}}}
        assert approved_client.post("/api/watch/push", json=sub,
                                    headers=auth()).status_code == 200
    extra = {"subscription": {
        "endpoint": "https://fcm.googleapis.com/fcm/send/extra",
        "keys": {"p256dh": "k", "auth": "x"}}}
    assert approved_client.post("/api/watch/push", json=extra,
                                headers=auth()).status_code == 403


# ---------------------------------------------------------------- admin

def test_admin_gate(client, store):
    assert client.get("/api/admin/overview",
                      headers=auth()).status_code == 403
    store.users["sam"] = {"email": "sam@example.com", "status": "pending"}
    data = client.get("/api/admin/overview",
                      headers=auth("tok-admin")).json()
    assert data["users"][0]["uid"] == "sam"


def test_admin_approve_and_revoke(client, store):
    store.users["sam"] = {"email": "sam@example.com", "status": "pending"}
    r = client.post("/api/admin/user",
                    json={"uid": "sam", "action": "approve"},
                    headers=auth("tok-admin"))
    assert r.json()["status"] == "approved"
    r = client.post("/api/admin/user",
                    json={"uid": "sam", "action": "revoke"},
                    headers=auth("tok-admin"))
    assert store.users["sam"]["status"] == "revoked"


def test_admin_creates_and_disables_codes(client, store):
    r = client.post("/api/admin/code", json={"max_uses": 10, "note": "beta"},
                    headers=auth("tok-admin"))
    code = r.json()["code"]
    assert code.startswith("ROADS-") and store.codes[code]["max_uses"] == 10
    client.post("/api/admin/code", json={"action": "disable", "code": code},
                headers=auth("tok-admin"))
    assert store.codes[code]["active"] is False


# ---------------------------------------------------------------- geometry

def test_haversine_sanity():
    # San Jose to San Francisco is roughly 67 km as the crow flies.
    d = watch.haversine_km(37.3382, -121.8863, 37.7749, -122.4194)
    assert 60 < d < 75


def test_point_in_polygon():
    square = [[38.0, -121.0], [38.0, -120.0], [39.0, -120.0], [39.0, -121.0]]
    assert watch.point_in_polygon(38.5, -120.5, square)
    assert not watch.point_in_polygon(37.5, -120.5, square)


def test_watch_matches_circle():
    w = {"type": "circle", "center": {"lat": 37.3, "lon": -121.9},
         "radius_km": 10}
    assert watch.watch_matches(w, 37.33, -121.9)
    assert not watch.watch_matches(w, 38.5, -121.9)


# ---------------------------------------------------------------- checker

@pytest.fixture
def checker(store, monkeypatch):
    events = []
    pushes = []

    async def fake_events():
        return list(events)

    async def fake_push(subs, payload):
        pushes.append((len(subs), payload))
        return len(subs)

    monkeypatch.setattr(watch, "_collect_events", fake_events)
    monkeypatch.setattr(watch, "_push_to_subs", fake_push)
    return store, events, pushes


EVENT = {"id": "chp:1", "kind": "incident", "lat": 37.31, "lon": -121.9,
         "title": "Collision", "body": "US-101 near San Jose"}


async def seed_watch(store):
    await approve(store)
    wid = await store.create_watch({
        "uid": "sam", "name": "Home", "type": "circle",
        "center": {"lat": 37.3, "lon": -121.9}, "radius_km": 20,
        "kinds": ["incident"], "channels": {"push": True}, "active": True,
    })
    await store.upsert_push_sub("dev1", {
        "uid": "sam", "subscription": {"endpoint": "https://p/1"}})
    return wid


async def test_first_cycle_seeds_silently(checker):
    store, events, pushes = checker
    await seed_watch(store)
    events.append(EVENT)
    stats = await watch.run_check_cycle()
    assert stats["alerts"] == 0  # backlog absorbed, not alerted
    assert not pushes


async def test_new_event_alerts_once(checker):
    store, events, pushes = checker
    wid = await seed_watch(store)
    await store.set_seen(wid, {"chp:0"})  # already past first cycle
    events.append(EVENT)
    stats = await watch.run_check_cycle()
    assert stats["alerts"] == 1 and len(pushes) == 1
    assert "Collision" in pushes[0][1]["title"]
    # Same event again: no re-alert.
    stats = await watch.run_check_cycle()
    assert stats["alerts"] == 0
    assert len(pushes) == 1


async def test_cleared_event_can_realert(checker):
    store, events, pushes = checker
    wid = await seed_watch(store)
    await store.set_seen(wid, {"chp:0"})
    events.append(EVENT)
    await watch.run_check_cycle()
    events.clear()  # incident clears
    await watch.run_check_cycle()
    events.append(EVENT)  # and returns
    await watch.run_check_cycle()
    assert len(pushes) == 2


async def test_kind_and_geometry_filters(checker):
    store, events, pushes = checker
    wid = await seed_watch(store)
    await store.set_seen(wid, {"chp:0"})
    events.append({**EVENT, "id": "fire:9", "kind": "fire"})
    events.append({**EVENT, "id": "chp:far", "lat": 40.5, "lon": -122.0})
    await watch.run_check_cycle()
    assert not pushes


async def test_revoked_users_get_nothing(checker):
    store, events, pushes = checker
    wid = await seed_watch(store)
    await store.set_seen(wid, {"chp:0"})
    await store.upsert_user("sam", {"status": "revoked"})
    events.append(EVENT)
    await watch.run_check_cycle()
    assert not pushes


def test_update_edits_name_kinds_channels(approved_client, store):
    wid = approved_client.post("/api/watch/create", json=CIRCLE,
                               headers=auth()).json()["id"]
    r = approved_client.patch(
        "/api/watch/" + wid,
        json={"name": "School run", "kinds": ["closure", "fire"],
              "channels": {"push": False, "email": True}},
        headers=auth())
    assert r.status_code == 200
    saved = store.watches[wid]
    assert saved["name"] == "School run"
    assert saved["kinds"] == ["closure", "fire"]
    assert saved["channels"] == {"push": False, "email": True}


def test_update_pause_and_resume(approved_client, store):
    wid = approved_client.post("/api/watch/create", json=CIRCLE,
                               headers=auth()).json()["id"]
    approved_client.patch("/api/watch/" + wid, json={"active": False},
                          headers=auth())
    assert store.watches[wid]["active"] is False
    approved_client.patch("/api/watch/" + wid, json={"active": True},
                          headers=auth())
    assert store.watches[wid]["active"] is True


def test_update_is_owner_only_and_validates(approved_client, store):
    wid = approved_client.post("/api/watch/create", json=CIRCLE,
                               headers=auth()).json()["id"]
    store.users["boss"] = {"email": "nic@glazkov.com", "status": "approved"}
    assert approved_client.patch("/api/watch/" + wid,
                                 json={"active": False},
                                 headers=auth("tok-admin")).status_code == 404
    assert approved_client.patch("/api/watch/" + wid, json={"kinds": []},
                                 headers=auth()).status_code == 400
    assert approved_client.patch("/api/watch/" + wid, json={},
                                 headers=auth()).status_code == 400


def test_update_polygon_shape(approved_client, store):
    body = {"type": "polygon", "name": "Tahoe", "kinds": ["fire"],
            "points": [[38.9, -120.2], [39.2, -120.2], [39.2, -120.1]]}
    wid = approved_client.post("/api/watch/create", json=body,
                               headers=auth()).json()["id"]
    r = approved_client.patch(
        "/api/watch/" + wid,
        json={"points": [[38.8, -120.5], [39.3, -120.5],
                         [39.3, -120.1], [38.8, -120.1]]},
        headers=auth())
    assert r.status_code == 200
    stored = store.watches[wid]["points"]
    assert len(stored) == 4
    assert stored[0] == {"lat": 38.8, "lon": -120.5}  # Firestore-safe maps


def test_nevada_and_oregon_corners_refuse(approved_client):
    base = {"type": "polygon", "name": "Edge", "kinds": ["incident"]}
    reno = {**base, "points": [[39.5, -119.8], [39.6, -119.8],
                               [39.6, -119.7]]}
    assert approved_client.post("/api/watch/create", json=reno,
                                headers=auth()).status_code == 400
    oregon = {**base, "points": [[42.3, -122.0], [42.4, -122.0],
                                 [42.4, -121.9]]}
    assert approved_client.post("/api/watch/create", json=oregon,
                                headers=auth()).status_code == 400
    # Offshore stays allowed: a coastal watch reaching into the Pacific.
    coastal = {**base, "points": [[36.5, -122.5], [36.9, -122.5],
                                  [36.9, -121.9]]}
    assert approved_client.post("/api/watch/create", json=coastal,
                                headers=auth()).status_code == 200
    reno_circle = {"type": "circle", "name": "Reno", "kinds": ["incident"],
                   "center": {"lat": 39.53, "lon": -119.81}, "radius_km": 10}
    assert approved_client.post("/api/watch/create", json=reno_circle,
                                headers=auth()).status_code == 400


def test_update_shape_validates(approved_client, store):
    poly = {"type": "polygon", "name": "Tahoe", "kinds": ["fire"],
            "points": [[38.9, -120.2], [39.2, -120.2], [39.2, -120.1]]}
    wid = approved_client.post("/api/watch/create", json=poly,
                               headers=auth()).json()["id"]
    # Too few points, out-of-state points, and circles all refuse.
    assert approved_client.patch("/api/watch/" + wid,
                                 json={"points": [[38.9, -120.2]]},
                                 headers=auth()).status_code == 400
    assert approved_client.patch(
        "/api/watch/" + wid,
        json={"points": [[40.7, -74.0], [40.8, -74.0], [40.8, -73.9]]},
        headers=auth()).status_code == 400
    cid = approved_client.post("/api/watch/create", json=CIRCLE,
                               headers=auth()).json()["id"]
    r = approved_client.patch(
        "/api/watch/" + cid,
        json={"points": [[38.9, -120.2], [39.2, -120.2], [39.2, -120.1]]},
        headers=auth())
    assert r.status_code == 400


async def test_paused_watches_get_no_alerts(checker):
    store, events, pushes = checker
    wid = await seed_watch(store)
    await store.set_seen(wid, {"chp:0"})
    store.watches[wid]["active"] = False
    events.append(EVENT)
    stats = await watch.run_check_cycle()
    assert stats["alerts"] == 0 and not pushes


def test_scheduler_endpoint_refuses_anonymous(client):
    assert client.post("/api/check-watches").status_code == 403


# ------------------------------------------------------------------ email

def test_email_single_event_subject_and_body():
    subject, html, text = watch.render_alert_email("Commute over 17", [EVENT])
    assert subject == "CA Roads: Collision in Commute over 17"
    assert "Commute over 17" in html
    assert "US-101 near San Jose" in html and "US-101 near San Jose" in text
    assert "Informational only" in html and "Informational only" in text
    assert "Open the live map" in html


def test_email_multi_event_counts_and_overflow():
    events = [EVENT, {**EVENT, "id": "fire:2", "kind": "fire",
                      "title": "Wildfire: KESTREL", "body": "310 acres"}]
    subject, html, text = watch.render_alert_email("Tahoe", events, more=3)
    assert subject == "CA Roads: 5 new events in Tahoe"
    assert "and 3 more" in html and "3 more" in text
    assert "WILDFIRE" in html.upper()


def test_email_escapes_html_in_event_text():
    evil = {**EVENT, "title": "<script>x</script>", "body": "a & b <i>"}
    _, html, _ = watch.render_alert_email("Home", [evil])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


async def test_busy_cycle_sends_one_email(checker, monkeypatch):
    store, events, pushes = checker
    wid = await seed_watch(store)
    await store.upsert_user("sam", {"email": "sam@example.com"})
    store.watches[wid]["channels"] = {"push": False, "email": True}
    await store.set_seen(wid, {"chp:0"})
    emails = []

    async def fake_email(to, subject, html, text):
        emails.append((to, subject))
        return True

    monkeypatch.setattr(watch, "_email_alert", fake_email)
    for i in range(4):
        events.append({**EVENT, "id": f"chp:{i + 1}"})
    stats = await watch.run_check_cycle()
    assert stats["alerts"] == 4
    assert len(emails) == 1  # one digest, not four emails
    assert emails[0][0] == "sam@example.com"
    assert "4 new events" in emails[0][1]


def test_account_delete_removes_everything(approved_client, store):
    approved_client.post("/api/watch/create", json=CIRCLE, headers=auth())
    approved_client.post("/api/watch/push", json={"subscription": {
        "endpoint": "https://fcm.googleapis.com/fcm/send/dev",
        "keys": {"p256dh": "k", "auth": "x"}}},
        headers=auth())
    r = approved_client.request("DELETE", "/api/watch/account",
                                headers=auth())
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] is True
    assert body["watches"] == 1 and body["devices"] == 1
    assert "sam" not in store.users
    assert not store.watches and not store.subs
    # Anonymous callers get refused.
    assert approved_client.request(
        "DELETE", "/api/watch/account").status_code == 401


ROUTE_PTS = [[37.34, -121.89], [37.45, -122.0], [37.6, -122.1],
             [37.77, -122.42]]


def test_create_route_watch(approved_client, store):
    body = {"type": "route", "name": "SJ to SF", "kinds": ["incident"],
            "points": ROUTE_PTS, "buffer_km": 3.2}
    r = approved_client.post("/api/watch/create", json=body, headers=auth())
    assert r.status_code == 200
    saved = store.watches[r.json()["id"]]
    assert saved["type"] == "route"
    assert saved["buffer_km"] == 3.2
    assert saved["length_km"] > 50
    assert isinstance(saved["points"][0], dict)  # Firestore-safe


def test_route_watch_validation(approved_client):
    base = {"type": "route", "name": "Bad", "kinds": ["incident"]}
    one = {**base, "points": [[37.3, -121.9]]}
    assert approved_client.post("/api/watch/create", json=one,
                                headers=auth()).status_code == 400
    reno = {**base, "points": [[38.6, -121.5], [39.53, -119.81]]}
    assert approved_client.post("/api/watch/create", json=reno,
                                headers=auth()).status_code == 400
    too_long = {**base, "points": [[33.0, -117.2], [41.9, -122.3]]}
    assert approved_client.post("/api/watch/create", json=too_long,
                                headers=auth()).status_code == 400


def test_route_matching_uses_corridor_distance():
    w = {"type": "route", "buffer_km": 3.0,
         "points": [{"lat": 37.34, "lon": -121.89},
                    {"lat": 37.77, "lon": -122.42}]}
    assert watch.watch_matches(w, 37.55, -122.15)
    assert not watch.watch_matches(w, 37.55, -121.8)


async def test_route_watch_alerts(checker):
    store, events, pushes = checker
    await approve(store)
    wid = await store.create_watch({
        "uid": "sam", "name": "SJ-SF", "type": "route",
        "points": [{"lat": 37.34, "lon": -121.89},
                   {"lat": 37.77, "lon": -122.42}],
        "buffer_km": 3.0, "kinds": ["incident"],
        "channels": {"push": True}, "active": True,
    })
    await store.upsert_push_sub("dev1", {
        "uid": "sam", "subscription": {"endpoint": "https://p/1"}})
    await store.set_seen(wid, {"chp:0"})
    events.append({**EVENT, "lat": 37.55, "lon": -122.15})
    stats = await watch.run_check_cycle()
    assert stats["alerts"] == 1 and len(pushes) == 1


def test_route_buffer_updates_and_clamps(approved_client, store):
    body = {"type": "route", "name": "SJ to SF", "kinds": ["incident"],
            "points": ROUTE_PTS, "buffer_km": 3.0}
    wid = approved_client.post("/api/watch/create", json=body,
                               headers=auth()).json()["id"]
    r = approved_client.patch("/api/watch/" + wid,
                              json={"buffer_km": 50}, headers=auth())
    assert r.status_code == 200
    assert store.watches[wid]["buffer_km"] == watch.MAX_BUFFER_KM
    cid = approved_client.post("/api/watch/create", json=CIRCLE,
                               headers=auth()).json()["id"]
    assert approved_client.patch("/api/watch/" + cid,
                                 json={"buffer_km": 3},
                                 headers=auth()).status_code == 400


def test_redeem_brute_force_throttles(client, store, monkeypatch):
    monkeypatch.setattr(watch, "REDEEM_FAILS_PER_DAY", 3)
    watch._redeem_fails.clear()
    for i in range(3):
        r = client.post("/api/watch/redeem", json={"code": f"ROADS-WRONG{i}"},
                        headers=auth())
        assert r.status_code == 403
    r = client.post("/api/watch/redeem", json={"code": "ROADS-WRONG9"},
                    headers=auth())
    assert r.status_code == 429
    # Even a VALID code is refused while throttled: guessing is over
    # for the day.
    store.codes["ROADS-GOOD"] = {"active": True, "max_uses": 5, "uses": 0}
    r = client.post("/api/watch/redeem", json={"code": "ROADS-GOOD"},
                    headers=auth())
    assert r.status_code == 429
    watch._redeem_fails.clear()


def test_push_endpoint_ssrf_blocked(approved_client, store):
    from ca_roads_demo import watch as w
    # Internal / metadata / arbitrary hosts are refused.
    for bad_ep in ("https://169.254.169.254/push",
                   "https://localhost/push",
                   "https://evil.example.com/push",
                   "https://10.0.0.1/x",
                   "http://fcm.googleapis.com/fcm/send/x"):
        r = approved_client.post("/api/watch/push", json={"subscription": {
            "endpoint": bad_ep, "keys": {"p256dh": "k", "auth": "x"}}},
            headers=auth())
        assert r.status_code == 400, bad_ep
    assert not w.valid_push_endpoint("https://169.254.169.254/x")
    assert w.valid_push_endpoint(
        "https://web.push.apple.com/abc")
    assert w.valid_push_endpoint(
        "https://fcm.googleapis.com/fcm/send/abc")


def test_bad_watch_id_is_not_found(approved_client):
    for bad in ("../../etc", "a/b", "..", "x" * 200):
        assert approved_client.request(
            "DELETE", "/api/watch/" + bad, headers=auth()).status_code == 404


def test_oversized_body_rejected(approved_client):
    huge = {"type": "circle", "name": "x", "kinds": ["incident"],
            "center": {"lat": 37.3, "lon": -121.9}, "radius_km": 10,
            "pad": "z" * 300000}
    r = approved_client.post("/api/watch/create", json=huge, headers=auth())
    assert r.status_code in (400, 413)
