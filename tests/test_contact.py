"""POST /api/contact: the contact form's server side."""
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch


def _client(monkeypatch, sent):
    async def fake_email(to_email, subject, html, text, reply_to=None):
        sent.append({"to": to_email, "subject": subject, "text": text,
                     "reply_to": reply_to})
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
    assert sent[0]["subject"] == "CommuteScout contact: AdaBcc: evil@x.com"
