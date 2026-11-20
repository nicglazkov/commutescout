"""The map details pane's one-line AI overview: one small model call per
distinct record, shared cache, the assistant's dollar cap, a per-client
daily cap, and a pane that never depends on it."""

from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from ca_roads.budget import DailyCounter
from ca_roads_demo import app as demo_app

RECORD = {"type": "Collision", "road": "SR-99", "dir": "N", "lat": 38.5, "lon": -121.4,
          "path": [[38.5, -121.4]] * 400, "desc": "Two vehicles, right lane blocked"}


class FakeMessages:
    def __init__(self, text="A two-car collision is blocking the right lane northbound.",
                 fail=False):
        self.calls = []
        self.text = text
        self.fail = fail

    async def create(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("upstream down")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.text)],
            usage=SimpleNamespace(input_tokens=300, output_tokens=25))


@pytest.fixture
def fake(monkeypatch):
    msgs = FakeMessages()
    monkeypatch.setattr(demo_app, "get_client", lambda: SimpleNamespace(messages=msgs))
    monkeypatch.setattr(demo_app, "guards", demo_app.DailyGuards())
    monkeypatch.setattr(demo_app, "paid_use", DailyCounter())
    monkeypatch.setattr(demo_app, "_OVERVIEW_CACHE", {})
    return msgs


def _post(client, body, ctype="application/json"):
    import json
    return client.post("/api/overview", content=json.dumps(body),
                       headers={"content-type": ctype})


def test_returns_one_sentence_and_charges_the_shared_budget(fake):
    client = TestClient(demo_app.app)
    r = _post(client, {"kind": "inc_collision", "record": RECORD, "tz": "America/Chicago"})
    assert r.status_code == 200, r.text
    assert r.json() == {"overview": "A two-car collision is blocking the right lane northbound.",
                        "cached": False}
    assert r.headers["Cache-Control"] == "no-store"
    call = fake.calls[0]
    assert call["model"] == demo_app.OVERVIEW_MODEL
    assert call["max_tokens"] == demo_app.OVERVIEW_MAX_TOKENS
    assert "tools" not in call
    prompt = call["messages"][0]["content"]
    assert "Two vehicles" in prompt and "America/Chicago" in prompt
    assert '"path"' not in prompt  # geometry never reaches the model
    assert demo_app.guards.dollars > 0
    # It never spends the visitor's assistant questions.
    assert demo_app.guards.questions.used("testclient") == 0


def test_the_same_record_costs_one_call(fake):
    client = TestClient(demo_app.app)
    body = {"kind": "inc_collision", "record": RECORD}
    assert _post(client, body).json()["cached"] is False
    again = _post(client, body)
    assert again.status_code == 200 and again.json()["cached"] is True
    assert len(fake.calls) == 1


def test_rejects_non_json_and_empty_records(fake):
    client = TestClient(demo_app.app)
    assert _post(client, {"record": RECORD}, ctype="text/plain").status_code == 415
    assert _post(client, {"record": {}}).status_code == 400
    assert _post(client, {"record": "a string"}).status_code == 400
    assert _post(client, {"record": {"path": [[1, 2]]}}).status_code == 400
    assert not fake.calls


def test_spent_budget_returns_429_before_any_call(fake):
    demo_app.guards._roll()
    demo_app.guards.dollars = demo_app.GLOBAL_DAILY_DOLLARS
    r = _post(TestClient(demo_app.app), {"record": RECORD})
    assert r.status_code == 429 and not fake.calls


def test_per_client_daily_cap(fake, monkeypatch):
    monkeypatch.setitem(demo_app.PAID_PER_CLIENT_DAILY, "overview", 2)
    client = TestClient(demo_app.app)
    codes = [_post(client, {"record": dict(RECORD, desc=f"case {i}")}).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]
    assert len(fake.calls) == 2


def test_model_failure_is_a_quiet_503_and_not_cached(fake):
    fake.fail = True
    client = TestClient(demo_app.app)
    assert _post(client, {"record": RECORD}).status_code == 503
    fake.fail = False
    assert _post(client, {"record": RECORD}).status_code == 200
    assert len(fake.calls) == 2


def test_long_answers_are_trimmed_to_one_line(fake):
    fake.text = "  " + ("word " * 120) + "\n\nsecond paragraph"
    r = _post(TestClient(demo_app.app), {"record": RECORD})
    text = r.json()["overview"]
    assert "\n" not in text and len(text) <= demo_app.OVERVIEW_MAX_CHARS + 1
    assert text.endswith("…")


def test_record_trim_keeps_scalars_and_short_lists_only():
    rec = demo_app._overview_record({
        "a": "x" * 900, "b": 3, "c": None, "d": [1, 2], "e": {"nested": 1},
        "path": [[1, 2]], "f": list(range(40)), "image": "https://x"})
    assert rec == {"a": "x" * 500, "b": 3, "c": None, "d": [1, 2]}


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(demo_app, "_OVERVIEW_CACHE", {})
    monkeypatch.setattr(demo_app, "_OVERVIEW_MAX", 3)
    for i in range(10):
        demo_app._overview_cache_put(str(i), "t")
    assert len(demo_app._OVERVIEW_CACHE) == 3
    assert demo_app._overview_cache_get("9") == "t"
