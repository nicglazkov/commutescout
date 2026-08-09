"""POST /api/signin-link: the branded, self-sent email-link sign-in.

We mint the link server-side (Firebase sends nothing) and deliver it
through Resend. The endpoint emails an address the caller types, so the
abuse caps are the point of most of these tests.
"""
import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch


@pytest.fixture()
def client(monkeypatch):
    # The shared rate-limiter is reset by the autouse conftest fixture.
    # Reset the in-process abuse throttle state between tests.
    monkeypatch.setattr(demo_app, "_signin_email_hits", {})
    monkeypatch.setattr(demo_app, "_signin_ip_hits", {})

    sent = []

    async def fake_email(to_email, subject, html, text, reply_to=None):
        sent.append({"to": to_email, "subject": subject, "html": html})
        return True

    def fake_link(email):
        return "https://ca-roads-mcp.firebaseapp.com/__/auth/action?oobCode=x&mode=signIn"

    monkeypatch.setattr(watch, "_email_alert", fake_email)
    monkeypatch.setattr(watch, "generate_signin_link", fake_link)
    c = TestClient(demo_app.app)
    c.sent = sent
    return c


def test_valid_request_mints_and_sends(client):
    r = client.post("/api/signin-link",
                    data={"email": "a@b.co", "website": ""})
    assert r.status_code == 200 and "inbox" in r.text.lower()
    assert client.sent and client.sent[0]["to"] == "a@b.co"
    assert "Sign in to CommuteScout" in client.sent[0]["subject"]
    # The minted link must be in the email body.
    assert "oobCode=x" in client.sent[0]["html"]


def test_honeypot_sends_nothing_but_looks_successful(client):
    r = client.post("/api/signin-link",
                    data={"email": "bot@b.co", "website": "filled"})
    assert r.status_code == 200
    assert not client.sent


def test_invalid_email_rejected(client):
    r = client.post("/api/signin-link",
                    data={"email": "notanemail", "website": ""})
    assert r.status_code == 400
    assert not client.sent


def test_per_email_cap_blocks_bombing_one_victim(client):
    # The victim's address, sprayed. After the per-email cap it must 429
    # even though each request could come from a fresh IP.
    ok = 0
    for i in range(_cap := demo_app._SIGNIN_PER_EMAIL_HOUR + 3):
        r = client.post("/api/signin-link",
                        data={"email": "victim@b.co", "website": ""},
                        headers={"x-forwarded-for": f"9.9.9.{i}"})
        ok += r.status_code == 200
    assert ok == demo_app._SIGNIN_PER_EMAIL_HOUR
    assert len(client.sent) == demo_app._SIGNIN_PER_EMAIL_HOUR


def test_blocked_victim_does_not_burn_the_ip_budget(client):
    # Spray the victim past their cap from one IP, then that IP requests a
    # link to its OWN address: it must still work (the blocked victim
    # attempts did not consume this IP's budget).
    for _ in range(demo_app._SIGNIN_PER_EMAIL_HOUR + 2):
        client.post("/api/signin-link",
                    data={"email": "victim@b.co", "website": ""},
                    headers={"x-forwarded-for": "5.5.5.5"})
    client.sent.clear()
    r = client.post("/api/signin-link",
                    data={"email": "self@b.co", "website": ""},
                    headers={"x-forwarded-for": "5.5.5.5"})
    assert r.status_code == 200 and client.sent


def test_link_generation_failure_is_503(client, monkeypatch):
    monkeypatch.setattr(watch, "generate_signin_link", lambda e: None)
    r = client.post("/api/signin-link",
                    data={"email": "a@b.co", "website": ""})
    assert r.status_code == 503
    assert not client.sent


def test_send_failure_is_502(client, monkeypatch):
    async def fail_email(*a, **k):
        return False
    monkeypatch.setattr(watch, "_email_alert", fail_email)
    r = client.post("/api/signin-link",
                    data={"email": "a@b.co", "website": ""})
    assert r.status_code == 502


def test_generate_signin_link_never_raises(monkeypatch):
    # google.auth.default failing (no ADC locally) must yield None, not
    # an exception into the request path.
    import ca_roads_demo.watch as w

    def boom(*a, **k):
        raise RuntimeError("no ADC")

    monkeypatch.setattr("google.auth.default", boom)
    assert w.generate_signin_link("a@b.co") is None
