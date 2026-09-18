"""Settings tool: distance units follow the locale until chosen, persist
per device and per account; the account controls live here, not in
the Watch pane."""

import re
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_watch import auth, store  # noqa: F401 - fixture

from ca_roads_demo import watch

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
WATCH_HTML = (STATIC / "watch.html").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")
WATCH_JS = (STATIC / "watch-app.js").read_text(encoding="utf-8")
UNITS = (STATIC / "units.js").read_text(encoding="utf-8")


def test_settings_is_a_rail_tool_above_data_with_units_and_account():
    rail = re.search(r'<nav class="rail"[^>]*>(.*?)</nav>', HTML, re.S).group(1)
    assert rail.index('data-tool="settings"') > rail.index('class="railgap"')
    assert rail.index('data-tool="settings"') < rail.index('data-tool="about"')
    pane = re.search(r'<section id="pane-settings"[^>]*>(.*?)\n    </section>', HTML, re.S).group(1)
    assert pane.count('name="units"') == 2 and 'value="mi"' in pane and 'value="km"' in pane
    for i in ("unitpick", "unitnote", "who", "acctnote", "settingssignin", "acctcard",
              "deleteacct", "acctmsg"):
        assert pane.count(f'id="{i}"') == 1, i
    watch_pane = re.search(r'<section id="pane-watch"[^>]*>(.*?)\n    </section>',
                           HTML, re.S).group(1)
    assert "deleteacct" not in watch_pane and 'id="who"' not in watch_pane


def test_units_follow_locale_then_the_choice_on_both_pages():
    assert "window.csUnits" in UNITS and "const KEY = 'cs-units';" in UNITS
    assert "/-(US|GB|LR|MM)\\b/i" in UNITS
    for page in (HTML, WATCH_HTML):
        assert '<script src="/static/units.js?v=__ASSET_V__"></script>' in page
    # The map page loads it before the scripts that read it.
    assert HTML.index("units.js") < HTML.index("map-assistant.js?v=")
    assert "csUnits.set(e.target.value)" in APP
    assert "if (lastEnds) replanVias();" in APP


def test_watch_radius_works_in_the_viewers_unit_and_sends_kilometers():
    assert "function applyUnits()" in WATCH_JS
    assert "r.max = mi ? '25' : '40';" in WATCH_JS
    assert "if (!prev) r.value = mi ? '10' : '15';" in WATCH_JS
    assert "radius_km: Math.min(km, (CFG.limits && CFG.limits.free_radius_km) || km)" in WATCH_JS
    assert "api('/api/watch/prefs', { method: 'POST'," in WATCH_JS
    assert "window.csUnits.set(me.prefs.units, { fromServer: true });" in WATCH_JS


def test_route_distances_follow_the_unit_setting():
    assert "const perUnit = trip.units === 'kilometers' ? 1000 : 1609.344;" in APP
    assert "csUnits.fmt(route.distance / 1000, 0)" in APP
    assert "preset, units: csUnits.get() === 'km' ? 'kilometers' : 'miles'" in APP


def _app():
    return Starlette(routes=[
        Route("/api/watch/me", watch.api_watch_me),
        Route("/api/watch/prefs", watch.api_watch_prefs, methods=["POST"]),
    ])


def test_prefs_persist_on_the_account(store):  # noqa: F811 - fixture
    c = TestClient(_app())
    assert c.post("/api/watch/prefs", json={"units": "km"}).status_code == 401
    assert c.get("/api/watch/me", headers=auth()).json()["prefs"] == {}
    assert c.post("/api/watch/prefs", json={"units": "furlongs"},
                  headers=auth()).status_code == 400
    r = c.post("/api/watch/prefs", json={"units": "km"}, headers=auth())
    assert r.status_code == 200 and r.json()["prefs"] == {"units": "km"}
    assert c.get("/api/watch/me", headers=auth()).json()["prefs"] == {"units": "km"}
    # Pending users keep their preferences too; status is untouched.
    assert c.get("/api/watch/me", headers=auth()).json()["status"] == "pending"


def _plugins_app():
    return Starlette(routes=[
        Route("/api/watch/me", watch.api_watch_me),
        Route("/api/me/plugins", watch.api_me_plugins, methods=["GET", "PUT"]),
    ])


def test_plugin_choices_follow_the_account(store):  # noqa: F811 - fixture
    c = TestClient(_plugins_app())
    assert c.get("/api/me/plugins").status_code == 401
    assert c.get("/api/me/plugins", headers=auth()).json()["plugins"] == {"off": [], "private": []}
    # Switch a catalog plugin off; add a private one by URL.
    r = c.put("/api/me/plugins", json={"off": ["wz-flare", "wz-flare"]}, headers=auth())
    assert r.status_code == 200 and r.json()["plugins"]["off"] == ["wz-flare"]
    mine = {"id": "mine", "name": "Mine", "base": "https://p.example.com", "token": "t"}
    r = c.put("/api/me/plugins", json={"private": [mine]}, headers=auth())
    assert r.status_code == 200
    assert r.json()["plugins"]["private"][0]["base"] == "https://p.example.com"
    assert r.json()["plugins"]["off"] == ["wz-flare"], "an omitted key keeps what is stored"
    assert c.put("/api/me/plugins", json={"private": [{"id": "x", "base": "http://p"}]},
                 headers=auth()).status_code == 400
    assert c.put("/api/me/plugins", json={"off": "wz-flare"}, headers=auth()).status_code == 400
    # The account summary carries the same choices for the apps' first load.
    assert c.get("/api/watch/me", headers=auth()).json()["plugins"]["off"] == ["wz-flare"]


def _places_app():
    return Starlette(routes=[Route("/api/me/places", watch.api_me_places, methods=["GET", "PUT"])])


def test_places_merge_across_devices(store):  # noqa: F811 - fixture
    c = TestClient(_places_app())
    assert c.get("/api/me/places").status_code == 401
    assert c.get("/api/me/places", headers=auth()).json()["places"] == []
    phone = [{"id": "h", "kind": "home", "name": "Home", "lat": 37.3, "lon": -121.9,
              "used_at": 100},
             {"id": "r1", "kind": "recent", "name": "Los Altos", "lat": 37.37, "lon": -122.11,
              "used_at": 90}]
    r = c.put("/api/me/places", json={"places": phone}, headers=auth())
    assert r.status_code == 200 and [p["id"] for p in r.json()["places"]] == ["h", "r1"]
    # The web sets a newer Home and adds a recent; the phone's old Home loses.
    web = [{"id": "h2", "kind": "home", "name": "New home", "lat": 37.4, "lon": -121.8,
            "used_at": 200},
           {"id": "r2", "kind": "recent", "name": "Gilroy", "lat": 37.0, "lon": -121.57,
            "used_at": 150}]
    r = c.put("/api/me/places", json={"places": web}, headers=auth())
    ids = [p["id"] for p in r.json()["places"]]
    assert ids == ["h2", "r2", "r1"], ids
    # Removing on one device: push the list without it.
    r = c.put("/api/me/places", json={"places": [], "replace": True}, headers=auth())
    assert r.json()["places"] == []
    assert c.put("/api/me/places", json={"places": "x"}, headers=auth()).status_code == 400
    # Junk is dropped, not fatal.
    junk = [{"kind": "castle", "lat": 1, "lon": 2}, {"kind": "saved", "lat": "x"}]
    r = c.put("/api/me/places", json={"places": junk}, headers=auth())
    assert r.status_code == 200 and r.json()["places"] == []


def test_merge_caps_recents_and_keeps_newest():
    recents = [{"kind": "recent", "lat": 37.0, "lon": -122.0 + i * 0.01, "used_at": i}
               for i in range(30)]
    out = watch.merge_places([], recents)
    assert len(out) == watch.MAX_RECENTS and out[0]["used_at"] == 29
