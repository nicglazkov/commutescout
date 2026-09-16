"""Key management on the demo: a signed-in account (any status) creates,
lists and revokes its keys; the full key appears once; an admin sets a
tier; the Settings pane carries the card."""

import re
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_watch import auth, store  # noqa: F401 - fixture

from ca_roads import apikeys
from ca_roads_demo import watch

HTML = Path("src/ca_roads_demo/static/map.html").read_text(encoding="utf-8")
WATCH_JS = Path("src/ca_roads_demo/static/watch-app.js").read_text(encoding="utf-8")


def _app():
    return Starlette(routes=[
        Route("/api/keys", watch.api_keys_list, methods=["GET"]),
        Route("/api/keys", watch.api_keys_create, methods=["POST"]),
        Route("/api/keys/{key_id}", watch.api_keys_revoke, methods=["DELETE"]),
        Route("/api/admin/key", watch.api_admin_key, methods=["POST"]),
    ])


@pytest.fixture
def keys(store):  # noqa: F811 - fixture
    mem = apikeys.MemoryKeyStore()
    apikeys.set_key_store(mem)
    yield mem
    apikeys.set_key_store(None)


def test_keys_need_sign_in_and_show_the_secret_once(keys):
    c = TestClient(_app())
    assert c.get("/api/keys").status_code == 401
    assert c.post("/api/keys", json={"name": "x"}).status_code == 401
    r = c.post("/api/keys", json={"name": "  my dashboard  "}, headers=auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["key"].startswith("cs_live_") and body["name"] == "my dashboard"
    assert body["tier"] == "free" and body["daily_limit"] == 2000
    listed = c.get("/api/keys", headers=auth()).json()
    assert listed["max_active"] == 5 and listed["tiers"] == {"free": 2000, "pro": 10000}
    assert [k["id"] for k in listed["keys"]] == [body["id"]]
    assert "key" not in listed["keys"][0] and "hash" not in listed["keys"][0]
    # Another account sees nothing of it and cannot revoke it.
    assert c.get("/api/keys", headers=auth("tok-admin")).json()["keys"] == []
    assert c.delete(f"/api/keys/{body['id']}", headers=auth("tok-admin")).status_code == 404
    # The owner can.
    assert c.delete(f"/api/keys/{body['id']}", headers=auth()).status_code == 200
    assert c.get("/api/keys", headers=auth()).json()["keys"][0]["revoked"] is True


def test_active_key_cap_and_admin_tier(keys):
    c = TestClient(_app())
    ids = [c.post("/api/keys", json={"name": f"k{i}"}, headers=auth()).json()["id"]
           for i in range(5)]
    r = c.post("/api/keys", json={"name": "six"}, headers=auth())
    assert r.status_code == 400 and "5 active keys" in r.json()["error"]
    assert c.post("/api/admin/key", json={"key_id": ids[0], "tier": "pro"},
                  headers=auth()).status_code == 403
    r = c.post("/api/admin/key", json={"key_id": ids[0], "tier": "pro"}, headers=auth("tok-admin"))
    assert r.status_code == 200 and r.json()["tier"] == "pro"
    assert c.post("/api/admin/key", json={"key_id": ids[0], "tier": "gold"},
                  headers=auth("tok-admin")).status_code == 400
    listed = {k["id"]: k for k in c.get("/api/keys", headers=auth()).json()["keys"]}
    assert listed[ids[0]]["tier"] == "pro" and listed[ids[0]]["daily_limit"] == 10000


def test_settings_pane_has_the_keys_card_once():
    pane = re.search(r'<section id="pane-settings"[^>]*>(.*?)\n    </section>', HTML, re.S).group(1)
    for i in ("keycard", "keylist", "keyname", "keycreate", "keynew", "keyvalue", "keycopy",
              "keymsg"):
        assert pane.count(f'id="{i}"') == 1 and HTML.count(f'id="{i}"') == 1, i
    assert pane.index('id="keycard"') < pane.index('id="acctcard"')
    assert "async function renderKeys()" in WATCH_JS
    assert "api('/api/keys', { method: 'POST'," in WATCH_JS
    assert "if ($('keycard')) { $('keycard').hidden = false; renderKeys(); }" in WATCH_JS
