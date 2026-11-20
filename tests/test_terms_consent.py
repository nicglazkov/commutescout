"""Sign-up agreement: every sign-in surface on the web asks for an
unticked "I agree to the Terms of Use and Privacy Policy" before any
sign-in button works, and the account records the acceptance through
/api/me/terms with a server-stamped time and the terms version."""

import re
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_watch import auth, store  # noqa: F401 - fixture

from ca_roads_demo import watch

STATIC = Path("src/ca_roads_demo/static")
WATCH_JS = (STATIC / "watch-app.js").read_text(encoding="utf-8")
RULES = Path("firestore.rules").read_text(encoding="utf-8")


def _app():
    return Starlette(routes=[
        Route("/api/watch/me", watch.api_watch_me),
        Route("/api/watch/config", watch.api_watch_config),
        Route("/api/me/terms", watch.api_me_terms, methods=["POST"]),
    ])


def test_terms_version_is_the_published_one():
    assert watch.TERMS_VERSION == "2026-11-19"


def test_acceptance_is_recorded_on_the_account(store):  # noqa: F811 - fixture
    c = TestClient(_app())
    assert c.get("/api/watch/config").json()["termsVersion"] == watch.TERMS_VERSION
    v = watch.TERMS_VERSION
    assert c.post("/api/me/terms", json={"version": v}).status_code == 401
    me = c.get("/api/watch/me", headers=auth()).json()
    assert me["terms"] == {"version": None, "accepted_at": None, "current": v}
    # Only the current version can be agreed to.
    assert c.post("/api/me/terms", json={"version": "2020-01-01"},
                  headers=auth()).status_code == 400
    assert c.post("/api/me/terms", json={}, headers=auth()).status_code == 400
    r = c.post("/api/me/terms", json={"version": v}, headers=auth())
    assert r.status_code == 200
    first = r.json()["terms"]
    assert first["version"] == v and first["accepted_at"]
    assert store.users["sam"]["terms_version"] == v
    assert store.users["sam"]["terms_accepted_at"] == first["accepted_at"]
    # A second device agreeing again keeps the first acceptance time.
    again = c.post("/api/me/terms", json={"version": v}, headers=auth()).json()["terms"]
    assert again["accepted_at"] == first["accepted_at"]
    assert c.get("/api/watch/me", headers=auth()).json()["terms"]["version"] == v
    # Recording it does not touch approval.
    assert store.users["sam"]["status"] == "pending"


def test_an_older_acceptance_is_replaced_by_the_current_one(store):  # noqa: F811 - fixture
    store.users["sam"] = {"email": "sam@example.com", "status": "approved",
                          "terms_version": "2025-01-01",
                          "terms_accepted_at": "2025-01-01T00:00:00+00:00"}
    c = TestClient(_app())
    r = c.post("/api/me/terms", json={"version": watch.TERMS_VERSION}, headers=auth())
    t = r.json()["terms"]
    assert t["version"] == watch.TERMS_VERSION and not t["accepted_at"].startswith("2025")
    assert store.users["sam"]["status"] == "approved"


def test_the_route_is_mounted():
    src = Path("src/ca_roads_demo/app.py").read_text(encoding="utf-8")
    assert 'Route("/api/me/terms", watch.api_me_terms, methods=["POST"])' in src


def test_both_sign_in_pages_have_an_unticked_agreement_with_links():
    for page in ("map.html", "watch.html"):
        html = (STATIC / page).read_text(encoding="utf-8")
        card = re.search(r'<div class="card signin-card">(.*?)<div class="msg" id="signinmsg"',
                         html, re.S).group(1)
        box = re.search(r'<input type="checkbox" id="agree"[^>]*>', card).group(0)
        assert "checked" not in box, page
        assert 'href="/terms"' in card and 'href="/privacy"' in card, page
        assert "I agree to the" in card and "Terms of Use" in card and "Privacy Policy" in card
        # The agreement comes before every sign-in button.
        assert card.index('id="agree"') < card.index('id="googlebtn"') < card.index('id="emailbtn"')
        assert 'id="agreenote"' in card and 'id="termsbtn"' in card


def test_sign_in_buttons_wait_for_the_tick_and_the_account_records_it():
    assert "$('googlebtn').disabled = !ok;" in WATCH_JS
    assert "$('emailbtn').disabled = !ok;" in WATCH_JS
    # Both sign-in paths refuse to start without agreement, then remember it.
    for btn in ("googlebtn", "emailbtn"):
        handler = WATCH_JS[WATCH_JS.index(f"$('{btn}').addEventListener"):]
        handler = handler[:handler.index("});")]
        assert "if (!mayStart())" in handler and "noteAgreed();" in handler, btn
    assert "api('/api/me/terms', { method: 'POST'" in WATCH_JS
    # An account with no acceptance and no tick on this browser is held
    # at the agreement instead of going on.
    assert "termsGate = true;" in WATCH_JS


def test_rules_stay_deny_all_and_name_the_server_only_fields():
    assert "allow read, write: if false;" in RULES
    assert "allow read" not in RULES.replace("allow read, write: if false;", "")
    assert "terms_accepted_at" in RULES
