"""The answer stream must never end silently when the model call
fails: users get a plain-language note instead of a blank box."""

from ca_roads_demo import app


async def _boom(msg):
    raise RuntimeError(msg)
    yield  # pragma: no cover - makes this an async generator


async def _collect(gen):
    return [chunk async for chunk in gen]


async def test_budget_cap_yields_friendly_pause_note(monkeypatch):
    monkeypatch.setattr(app, "log_event", lambda *a, **k: None)
    chunks = await _collect(app._safe_answer_stream(
        _boom("Error code: 400 - You have reached your specified "
              "workspace API usage limits.")))
    joined = "".join(chunks)
    assert "monthly" in joined and "budget" in joined
    assert '"done": true' in joined or '"done": True' in joined or "done" in joined
    # The raw provider error never reaches the browser.
    assert "usage limits" not in joined and "400" not in joined


async def test_other_errors_yield_retry_note(monkeypatch):
    monkeypatch.setattr(app, "log_event", lambda *a, **k: None)
    chunks = await _collect(app._safe_answer_stream(_boom("boom")))
    joined = "".join(chunks)
    assert "try again" in joined
    assert "boom" not in joined


async def test_normal_stream_passes_through(monkeypatch):
    async def ok():
        yield "a"
        yield "b"
    assert await _collect(app._safe_answer_stream(ok())) == ["a", "b"]
