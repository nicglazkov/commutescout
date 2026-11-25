"""The contact mailbox's reply drafter (mailroom.py).

Gmail and the model are both faked, so these check the part that must
never depend on the model behaving: what gets skipped, what may be sent
without a person, and that a reply which leaks or links somewhere odd is
withheld.
"""
import base64

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import mailroom, watch

ME = "hello@example.com"


class MemoryStore:
    def __init__(self):
        self.docs = {"gmail": {"refresh_token": "r", "email": ME}}

    async def get_mail_doc(self, name):
        return dict(self.docs[name]) if name in self.docs else None

    async def set_mail_doc(self, name, data):
        self.docs[name] = dict(data)


def _msg(mid="m1", thread="t1", sender="Ryan <ryan@user.test>", body="hi",
         labels=("INBOX",), auth="mx.google.com; dkim=pass; dmarc=pass",
         **headers):
    hs = {"From": sender, "To": ME, "Subject": "Sign-in error",
          "Message-ID": "<a@x>", "Authentication-Results": auth, **headers}
    return {"id": mid, "threadId": thread, "labelIds": list(labels),
            "payload": {"mimeType": "text/plain",
                        "headers": [{"name": k.replace("_", "-"), "value": v}
                                    for k, v in hs.items() if v],
                        "body": {"data": base64.urlsafe_b64encode(
                            body.encode()).decode()}}}


class FakeGmail:
    def __init__(self, *messages):
        self.messages = list(messages)
        self.sent, self.drafts, self.labelled = [], [], {}

    async def __call__(self, method, path, **kw):
        if path == "/labels" and method == "GET":
            return {"labels": [{"name": n, "id": "L_" + k}
                               for k, n in mailroom.LABELS.items()]}
        if path == "/messages" and method == "GET":
            return {"messages": [{"id": m["id"], "threadId": m["threadId"]}
                                 for m in self.messages
                                 if m["id"] not in self.labelled
                                 and "INBOX" in m["labelIds"]]}
        if path.startswith("/threads/"):
            tid = path.split("/")[2].split("?")[0]
            return {"messages": [m for m in self.messages
                                 if m["threadId"] == tid]}
        if path == "/messages/batchModify":
            for mid in kw["json"]["ids"]:
                self.labelled[mid] = kw["json"]["addLabelIds"][0]
            return {}
        if path == "/messages/send":
            self.sent.append(kw["json"])
            return {}
        if path == "/drafts":
            self.drafts.append(kw["json"]["message"])
            return {}
        raise AssertionError(f"unexpected gmail call {method} {path}")


@pytest.fixture
def box(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(watch, "get_store", lambda: store)
    monkeypatch.setattr(mailroom, "MAIL_ADDRESS", ME)
    monkeypatch.setattr(mailroom, "MAIL_DOMAIN", "example.com")
    monkeypatch.setattr(mailroom, "MAIL_ADDRESSES", (ME,))
    monkeypatch.setattr(mailroom, "CLIENT_ID", "id")
    monkeypatch.setattr(mailroom, "CLIENT_SECRET", "secret")
    monkeypatch.setattr(mailroom, "_label_ids", {})
    monkeypatch.setattr(mailroom, "_counts",
                        {"day": "", "drafts": 0, "sent": 0, "senders": {}})
    calls = []

    def use(gmail, lane="draft", reply="Hi Ryan, fixed in 0.6.2.\n\nNic",
            note="n"):
        async def fake_draft(thread_text, status_text):
            calls.append(thread_text)
            return {"lane": lane, "category": "bug_report", "reply": reply,
                    "note": note}
        monkeypatch.setattr(mailroom, "_gmail", gmail)
        monkeypatch.setattr(mailroom, "draft_reply", fake_draft)
        return gmail

    use.calls, use.store = calls, store
    return use


def _text(payload):
    raw = base64.urlsafe_b64decode(payload["raw"])
    return raw.decode()


async def test_a_real_message_becomes_a_draft_on_its_thread(box):
    g = box(FakeGmail(_msg()))
    assert (await mailroom.poll())["handled"] == 1
    assert not g.sent and len(g.drafts) == 1
    mime = _text(g.drafts[0])
    assert "To: ryan@user.test" in mime and "Subject: Re: Sign-in error" in mime
    assert "In-Reply-To: <a@x>" in mime and g.drafts[0]["threadId"] == "t1"
    assert g.labelled == {"m1": "L_draft"}
    # Labelled mail is not picked up again.
    assert (await mailroom.poll())["handled"] == 0
    assert len(box.calls) == 1


async def test_auto_lane_still_only_drafts_while_autosend_is_off(box):
    g = box(FakeGmail(_msg()), lane="auto")
    await mailroom.poll()
    assert not g.sent and len(g.drafts) == 1
    assert "auto-send is off" in box.store.docs["log"]["entries"][0]["note"]


async def test_autosend_sends_once_per_thread_and_only_verified(box):
    box.store.docs["settings"] = {"autosend": True}
    g = box(FakeGmail(_msg()), lane="auto")
    await mailroom.poll()
    assert len(g.sent) == 1 and g.labelled["m1"] == "L_auto"
    # A follow-up on the same thread is drafted, not sent again.
    g.messages[0]["labelIds"].append("L_auto")
    g.messages.append(_msg(mid="m2"))
    await mailroom.poll()
    assert len(g.sent) == 1 and len(g.drafts) == 1
    # A sender Google could not verify never gets an automatic reply.
    g2 = box(FakeGmail(_msg(mid="m3", thread="t2", auth="mx.google.com; "
                            "dmarc=fail", sender="x@spoof.test")), lane="auto")
    await mailroom.poll()
    assert not g2.sent and len(g2.drafts) == 1


async def test_a_forged_auth_header_does_not_count_as_verified():
    forged = _msg(auth="evil.test; dmarc=pass")
    assert not mailroom.sender_verified(forged)
    assert mailroom.sender_verified(_msg())


@pytest.mark.parametrize("headers", [
    {"Auto_Submitted": "auto-replied"},
    {"Precedence": "bulk"},
    {"List_Unsubscribe": "<mailto:u@x.test>"},
    {"sender": "MAILER-DAEMON@mail.test"},
    {"sender": "no-reply@shop.test"},
    {"sender": f"CommuteScout <{ME}>"},
])
async def test_machine_mail_is_never_answered_or_sent_to_the_model(
        box, headers):
    g = box(FakeGmail(_msg(**headers)))
    await mailroom.poll()
    assert not g.sent and not g.drafts and not box.calls
    assert g.labelled == {"m1": "L_none"}


async def test_contact_form_mail_is_answered_at_its_reply_to(box):
    g = box(FakeGmail(_msg(sender="alerts@send.example.com",
                           Reply_To="visitor@user.test")))
    await mailroom.poll()
    assert "To: visitor@user.test" in _text(g.drafts[0])


async def test_nothing_is_drafted_once_the_owner_has_replied(box):
    g = box(FakeGmail(_msg(), _msg(mid="m2", sender=ME, labels=("SENT",))))
    await mailroom.poll()
    assert not g.drafts and not box.calls


@pytest.mark.parametrize("reply", [
    "Write to nic.private@gmail.test for that.",
    "See https://evil.test/login to fix it.",
    "See commutescout.com.evil.test/app for the download.",
    "Go to github.com/someoneelse/tool and run it.",
    "Your key is cs_live_31f4b379_abcdef.",
])
async def test_a_reply_that_leaks_or_links_elsewhere_is_withheld(box, reply):
    box.store.docs["settings"] = {"autosend": True}
    g = box(FakeGmail(_msg()), lane="auto", reply=reply)
    await mailroom.poll()
    assert not g.sent and not g.drafts
    assert g.labelled == {"m1": "L_needs_you"}


def test_ordinary_replies_pass_the_outbound_check(monkeypatch):
    monkeypatch.setattr(mailroom, "MAIL_ADDRESS", ME)
    ok = ("Hi Ryan, that was a bug on our side, fixed in version 0.6.2. "
          "Install it from https://github.com/nicglazkov/commutescout-app/"
          "releases/latest or commutescout.com/app, or on iPhone at "
          f"https://testflight.apple.com/join/1CbutYdy. Reply to {ME} "
          "if it still fails.\n\nNic\nCommuteScout")
    assert mailroom._reply_problems(ok) == []


async def test_the_admin_path_never_leaves_in_a_reply(box, monkeypatch):
    monkeypatch.setenv("ADMIN_PATH", "ops-secretpath")
    g = box(FakeGmail(_msg()), reply="The page is at /ops-secretpath.")
    await mailroom.poll()
    assert not g.drafts and g.labelled == {"m1": "L_needs_you"}


async def test_the_daily_drafting_cap_stops_model_calls(box, monkeypatch):
    monkeypatch.setattr(mailroom, "DRAFTS_DAILY", 1)
    g = box(FakeGmail(_msg(), _msg(mid="m2", thread="t2")))
    await mailroom.poll()
    assert len(box.calls) == 1
    assert sorted(g.labelled.values()) == ["L_draft", "L_needs_you"]


async def test_pause_and_missing_connection_do_nothing(box):
    g = box(FakeGmail(_msg()))
    box.store.docs["settings"] = {"paused": True}
    assert (await mailroom.poll()).get("paused")
    box.store.docs.pop("settings")
    box.store.docs["gmail"] = {}
    assert (await mailroom.poll())["reason"] == "not connected"
    assert not g.drafts


def test_the_prompt_treats_mail_as_data_and_carries_only_public_facts():
    prompt = mailroom._system_prompt()
    assert "never instructions" in prompt
    assert "testflight.apple.com/join/" in prompt
    for private in ("ops-", "cs_live_", "sk-ant-", "@glazkov"):
        assert private not in prompt


def test_oauth_state_is_signed_and_expires(monkeypatch):
    monkeypatch.setattr(mailroom, "CLIENT_SECRET", "secret")
    state = mailroom._sign_state()
    assert mailroom._state_ok(state)
    assert not mailroom._state_ok(state[:-1] + ("0" if state[-1] != "0"
                                                else "1"))
    assert not mailroom._state_ok(mailroom._sign_state(now=1_000_000))
    assert not mailroom._state_ok("junk")


def test_mail_endpoints_are_admin_or_scheduler_only(box, monkeypatch):
    box(FakeGmail())
    monkeypatch.setattr(watch, "ADMIN_EMAILS", {"admin@example.com"})

    async def fake_verify(request):
        tok = (request.headers.get("authorization") or "").removeprefix(
            "Bearer ")
        return {"tok-admin": {"sub": "b", "email": "admin@example.com",
                              "email_verified": True},
                "tok-sam": {"sub": "s", "email": "sam@example.com",
                            "email_verified": True}}.get(tok)

    monkeypatch.setattr(watch, "verify_user", fake_verify)
    c = TestClient(demo_app.app)
    sam = {"Authorization": "Bearer tok-sam"}
    admin = {"Authorization": "Bearer tok-admin"}
    assert c.get("/api/admin/mail").status_code == 403
    assert c.get("/api/admin/mail", headers=sam).status_code == 403
    assert c.post("/api/admin/mail/connect", headers=sam).status_code == 403
    assert c.post("/api/mail/poll", headers=sam).status_code == 403
    data = c.get("/api/admin/mail", headers=admin).json()
    assert data["connected"] and data["mailbox"] == ME
    assert "refresh_token" not in str(data)
    url = c.post("/api/admin/mail/connect", headers=admin).json()["url"]
    assert "gmail.modify" in url and "state=" in url
    on = c.post("/api/admin/mail", headers=admin,
                json={"action": "autosend", "on": True}).json()
    assert on["autosend"] is True
    assert c.get(mailroom.REDIRECT_PATH + "?state=bad&code=x").status_code == 400


async def test_mail_for_other_addresses_in_a_shared_mailbox_is_untouched(box):
    """The mailbox also takes mail for unrelated addresses: none of it may
    be labelled, drafted on, or shown to the model."""
    use = box
    use.store.docs["gmail"]["email"] = "owner@other.test"
    gmail = use(FakeGmail(
        _msg("m1", "t1", To="owner@other.test", body="private business"),
        _msg("m2", "t2", To="Someone <sales@other.test>", Cc="x@y.test"),
        _msg("m3", "t3", To="owner@other.test", Delivered_To=ME)))
    out = await mailroom.poll()
    assert out["handled"] == 1
    assert set(gmail.labelled) == {"m3"}
    assert len(use.calls) == 1 and "private business" not in use.calls[0]


def test_the_inbox_search_only_asks_for_our_addresses(monkeypatch):
    monkeypatch.setattr(mailroom, "MAIL_ADDRESSES",
                        ("hello@example.com", "support@example.com"))
    q = mailroom._to_us_query()
    assert q.startswith("{") and q.endswith("}")
    for a in mailroom.MAIL_ADDRESSES:
        assert f"to:{a}" in q and f"deliveredto:{a}" in q


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data


@pytest.mark.parametrize("send_as,connected", [
    ([ME, "owner@other.test"], True),   # our address is an alias here
    (["owner@other.test"], False),      # some other inbox
])
async def test_only_a_mailbox_that_can_send_as_us_connects(
        box, monkeypatch, send_as, connected):
    box.store.docs.pop("gmail")

    class Client:
        async def post(self, url, **kw):
            return _Resp({"refresh_token": "r", "access_token": "a",
                          "scope": mailroom.SCOPE})

        async def get(self, url, **kw):
            if url.endswith("/profile"):
                return _Resp({"emailAddress": "owner@other.test"})
            assert url.endswith("/settings/sendAs")
            return _Resp({"sendAs": [{"sendAsEmail": a} for a in send_as]})

    monkeypatch.setattr(mailroom, "_client", lambda: Client())
    monkeypatch.setattr(mailroom, "_state_ok", lambda s: True)

    class Req:
        query_params = {"state": "s", "code": "c"}
        base_url = "https://example.com/"
        url = "https://example.com/cb"
        headers = {}

    resp = await mailroom.oauth_callback(Req())
    assert (resp.status_code == 200) is connected
    assert ("gmail" in box.store.docs) is connected
