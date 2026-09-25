"""A form the browser posts itself lands back on its page, not on a
line of text."""

from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app

HTML = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}


def test_a_browser_post_to_the_waitlist_returns_to_the_pricing_page():
    c = TestClient(demo_app.app)
    # The honeypot path stores nothing, so no Firestore is needed here.
    r = c.post("/api/waitlist", data={"email": "a@b.co", "website": "spam"},
               headers=HTML, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/pricing?notice=joined"
    r = c.post("/api/waitlist", data={"email": "nope"}, headers=HTML, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/pricing?notice=invalid"


def test_a_script_post_still_gets_the_text():
    c = TestClient(demo_app.app)
    r = c.post("/api/waitlist", data={"email": "nope"}, headers={"Accept": "*/*"})
    assert r.status_code == 400 and "valid email" in r.text


def test_a_browser_post_to_contact_returns_to_the_contact_page(monkeypatch):
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    c = TestClient(demo_app.app)
    r = c.post("/api/contact", data={"name": "", "email": "a@b.co", "message": "x"},
               headers=HTML, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/contact?notice=invalid"
