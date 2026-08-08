"""POST /api/contact: the contact form's server side."""
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch
from ca_roads_mcp.ratelimit import RateLimiter


def _reset_shared_limiters(monkeypatch):
    """The main and SoftLimit rate buckets are one process-lifetime
    instance shared across every test module (keyed on TestClient's fixed
    peer). This file's several POSTs would otherwise drain them and 429 a
    later module (it did: test_waitlist). Give every limiter in the chain
    a fresh, generous bucket for this file. Walk by attribute, not depth,
    so middleware reordering doesn't break it."""
    layer = demo_app.app
    for _ in range(12):
        if layer is None:
            break
        if hasattr(layer, "limiter"):
            monkeypatch.setattr(
                layer, "limiter",
                RateLimiter(capacity=1000, refill_per_second=1000))
        layer = getattr(layer, "app", None)


def _client(monkeypatch, sent):
    _reset_shared_limiters(monkeypatch)

    async def fake_email(to_email, subject, html, text, reply_to=None):
        sent.append({"to": to_email, "subject": subject, "html": html,
                     "text": text, "reply_to": reply_to})
        return True
    monkeypatch.setattr(watch, "_email_alert", fake_email)
    monkeypatch.setenv("CONTACT_EMAIL", "owner@example.com")
    return TestClient(demo_app.app)


def test_valid_submission_sends_email(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    r = c.post("/api/contact", data={"name": "Ada", "email": "a@b.co",
                                     "message": "hello", "website": ""})
    assert r.status_code == 200
    assert sent and sent[0]["to"] == "owner@example.com"
    assert "Ada" in sent[0]["text"] and "a@b.co" in sent[0]["text"]
    # A reply must reach the visitor, not the alerts mailbox the message
    # is delivered from.
    assert sent[0]["reply_to"] == "a@b.co"


def test_email_is_clearly_the_form_and_states_how_to_validate(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    c.post("/api/contact", data={"name": "Ada", "email": "a@b.co",
                                 "message": "hello", "website": ""})
    subj, html, text = sent[0]["subject"], sent[0]["html"], sent[0]["text"]
    # Unmistakably the form, in the subject and the body.
    assert "contact form" in subj.lower()
    assert "contact form" in html.lower()
    # The sender is labelled unverified so it is not over-trusted.
    assert "unverified" in html.lower() and "unverified" in text.lower()
    # The authoritative validator is named.
    assert "send.commutescout.com" in html and "send.commutescout.com" in text
    # A server-stamped reference and time are present.
    assert "Reference" in html and "Received" in html


def test_message_is_html_escaped_in_the_email(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    c.post("/api/contact",
           data={"name": "Ada", "email": "a@b.co",
                 "message": "<img src=x onerror=alert(1)>", "website": ""})
    html = sent[0]["html"]
    assert "<img src=x onerror=" not in html
    assert "&lt;img" in html


def test_honeypot_filled_is_dropped_but_returns_ok(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    r = c.post("/api/contact", data={"name": "Bot", "email": "b@b.co",
                                     "message": "spam", "website": "x"})
    assert r.status_code == 200      # bots get no signal
    assert not sent


def test_missing_fields_rejected(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    assert c.post("/api/contact", data={"name": "", "email": "a@b.co",
                                        "message": "m", "website": ""}
                  ).status_code == 400
    assert not sent


def test_unconfigured_contact_email_gives_503(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    monkeypatch.delenv("CONTACT_EMAIL")
    r = c.post("/api/contact", data={"name": "Ada", "email": "a@b.co",
                                     "message": "m", "website": ""})
    assert r.status_code == 503


def test_embedded_newline_in_name_produces_clean_subject(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    r = c.post("/api/contact",
               data={"name": "Ada\r\nBcc: evil@x.com", "email": "a@b.co",
                     "message": "hello", "website": ""})
    assert r.status_code == 200
    assert "\r" not in sent[0]["subject"] and "\n" not in sent[0]["subject"]
    assert sent[0]["subject"] == (
        "[commutescout.com contact form] AdaBcc: evil@x.com")
