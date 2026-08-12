"""POST /api/contact: the contact form's server side."""
import asyncio

from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch


def _client(monkeypatch, sent):
    # The shared rate-limiter is reset by the autouse conftest fixture.
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


# --- Turnstile (bot check). The endpoint requires a verified token only
# when TURNSTILE_SECRET_KEY is set, so local dev, CI, and self-hosters
# without Cloudflare keep the plain form. ---

GOOD = {"name": "Ada", "email": "a@b.co", "message": "hello", "website": ""}


def test_turnstile_env_unset_skips_verification(monkeypatch):
    """Without the secret the form must work exactly as before, token or
    no token."""
    sent = []
    c = _client(monkeypatch, sent)
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    assert c.post("/api/contact", data=GOOD).status_code == 200
    assert sent


def test_turnstile_missing_token_rejected_without_verify_call(monkeypatch):
    """No token means no email and no pointless round trip to Cloudflare."""
    sent = []
    c = _client(monkeypatch, sent)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "sk-test")
    called = []

    async def fake_verify(secret, token, ip):
        called.append(token)
        return True
    monkeypatch.setattr(demo_app, "_turnstile_verify", fake_verify)
    r = c.post("/api/contact", data=GOOD)
    assert r.status_code == 403
    assert not sent and not called


def test_turnstile_failed_verification_rejected(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "sk-test")

    async def fake_verify(secret, token, ip):
        return False
    monkeypatch.setattr(demo_app, "_turnstile_verify", fake_verify)
    r = c.post("/api/contact",
               data={**GOOD, "cf-turnstile-response": "tok-bad"})
    assert r.status_code == 403
    assert not sent


def test_turnstile_pass_sends(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "sk-test")
    seen = {}

    async def fake_verify(secret, token, ip):
        seen.update(secret=secret, token=token, ip=ip)
        return True
    monkeypatch.setattr(demo_app, "_turnstile_verify", fake_verify)
    r = c.post("/api/contact",
               data={**GOOD, "cf-turnstile-response": "tok-good"})
    assert r.status_code == 200
    assert sent
    assert seen["secret"] == "sk-test" and seen["token"] == "tok-good"


def test_honeypot_short_circuits_before_turnstile(monkeypatch):
    """A honeypot hit must stay a silent drop with no verify call: bots
    get no signal, Cloudflare gets no traffic."""
    sent = []
    c = _client(monkeypatch, sent)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "sk-test")

    async def fake_verify(secret, token, ip):
        raise AssertionError("siteverify must not be called")
    monkeypatch.setattr(demo_app, "_turnstile_verify", fake_verify)
    r = c.post("/api/contact",
               data={**GOOD, "website": "x", "cf-turnstile-response": "t"})
    assert r.status_code == 200
    assert not sent


# _turnstile_verify internals, with the HTTP layer faked: the fail-closed
# rule is that only an explicit success=true passes.

class _FakeResp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _FakeClient:
    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, data=None):
        if self._exc:
            raise self._exc
        return self._resp


def _verify_with(monkeypatch, resp=None, exc=None):
    monkeypatch.setattr(
        demo_app.httpx, "AsyncClient",
        lambda **kw: _FakeClient(resp=resp, exc=exc))
    return asyncio.run(
        demo_app._turnstile_verify("sk", "tok", "203.0.113.9"))


def test_verify_true_on_success(monkeypatch):
    assert _verify_with(
        monkeypatch, resp=_FakeResp(200, {"success": True})) is True


def test_verify_false_on_rejection(monkeypatch):
    assert _verify_with(
        monkeypatch,
        resp=_FakeResp(200, {"success": False,
                             "error-codes": ["invalid-input-response"]}),
    ) is False


def test_verify_fails_closed_on_http_error(monkeypatch):
    assert _verify_with(
        monkeypatch, resp=_FakeResp(500, {})) is False


def test_verify_fails_closed_when_unreachable(monkeypatch):
    assert _verify_with(
        monkeypatch, exc=ConnectionError("boom")) is False
