"""Unreviewed plugins may alert only after the person acknowledges, at
install, that the plugin was not reviewed and its alerts come from its
operator. The acknowledgement rides with the plugin subscription on the
account (plugins.ack), stamped by the server; the notice itself is
served with the catalog so every client shows the same words; and the
spec says one consistent thing about alerts and voice per tier."""

import re
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_flare_sources import admin_app  # noqa: F401 - fixture
from tests.test_watch import auth, store  # noqa: F401 - fixture

from ca_roads import flare
from ca_roads_demo import watch

SPEC = Path("docs/flare.md").read_text(encoding="utf-8")
NOTICE = ("This plugin hasn't been reviewed by CommuteScout. Its alerts come from "
          "its operator, not from official sources.")


def _app():
    return Starlette(routes=[
        Route("/api/watch/me", watch.api_watch_me),
        Route("/api/me/plugins", watch.api_me_plugins, methods=["GET", "PUT"]),
    ])


def test_the_notice_is_the_approved_wording():
    assert flare.UNREVIEWED_NOTICE == NOTICE
    assert flare.UNREVIEWED_NOTICE_VERSION == "2026-11-19"


def test_only_unreviewed_plugins_wait_for_an_acknowledgement():
    assert flare.needs_ack("unreviewed")
    assert flare.needs_ack(None), "an unknown tier is treated as unreviewed"
    assert not flare.needs_ack("approved")
    assert not flare.needs_ack("private")


def test_acknowledgement_is_kept_with_the_subscription(store):  # noqa: F811 - fixture
    c = TestClient(_app())
    assert c.put("/api/me/plugins", json={"ack": ["wz-flare"]}).status_code == 401
    assert c.get("/api/me/plugins", headers=auth()).json()["plugins"]["ack"] == {}
    r = c.put("/api/me/plugins", json={"ack": ["wz-flare", "wz-flare"]}, headers=auth())
    assert r.status_code == 200
    ack = r.json()["plugins"]["ack"]
    assert list(ack) == ["wz-flare"]
    first = ack["wz-flare"]
    assert first["notice"] == flare.UNREVIEWED_NOTICE_VERSION and first["at"]
    assert store.users["sam"]["plugins"]["ack"]["wz-flare"] == first
    # Another device pushing the same list keeps the original time.
    r = c.put("/api/me/plugins", json={"ack": ["wz-flare", "other"]}, headers=auth())
    ack = r.json()["plugins"]["ack"]
    assert ack["wz-flare"] == first and set(ack) == {"wz-flare", "other"}
    # Other keys leave it alone; leaving an id out withdraws it.
    r = c.put("/api/me/plugins", json={"off": ["x"]}, headers=auth())
    assert set(r.json()["plugins"]["ack"]) == {"wz-flare", "other"}
    r = c.put("/api/me/plugins", json={"ack": ["other"]}, headers=auth())
    assert set(r.json()["plugins"]["ack"]) == {"other"}
    # The account summary carries it for the apps' first load.
    assert set(c.get("/api/watch/me", headers=auth()).json()["plugins"]["ack"]) == {"other"}
    for bad in ("wz-flare", [1], [""], ["x" * 65], {"wz-flare": True}):
        assert c.put("/api/me/plugins", json={"ack": bad},
                     headers=auth()).status_code == 400, bad


def test_a_malformed_stored_ack_reads_as_none(store):  # noqa: F811 - fixture
    store.users["sam"] = {"email": "sam@example.com", "status": "pending",
                          "plugins": {"ack": ["not", "a", "dict"]}}
    c = TestClient(_app())
    assert c.get("/api/me/plugins", headers=auth()).json()["plugins"]["ack"] == {}


def test_the_catalog_serves_the_notice(admin_app):  # noqa: F811 - fixture
    c, _ = admin_app
    body = c.get("/api/flare/sources").json()
    assert body["unreviewed_notice"] == {"text": NOTICE, "version": "2026-11-19"}


def test_the_spec_is_consistent_about_unreviewed_alerts_and_voice():
    flat = " ".join(SPEC.replace("\n> ", " ").split())
    assert NOTICE in flat
    # The old contradiction: "map only until promoted" in one place,
    # "spoken like any other" in the tier table.
    assert "spoken like any other" not in SPEC
    assert "map\nonly until promoted" not in SPEC and "map only until promoted" not in SPEC
    row = re.search(r"^\| `unreviewed` \|.*$", SPEC, re.M).group(0)
    assert "acknowledges" in row and "voice off" in row
    assert "ack: [ids]" in SPEC and "plugins.ack" in SPEC
    section = SPEC[SPEC.index("### Unreviewed plugins and alerts"):SPEC.index("## Shared data")]
    assert "**Alerts**" in section and "**Speak alerts**" in section
    assert "change at any time" in section


def test_rules_stay_deny_all_and_name_the_ack_field():
    rules = Path("firestore.rules").read_text(encoding="utf-8")
    assert "allow read, write: if false;" in rules and "plugins.ack" in rules
