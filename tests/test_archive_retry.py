"""The archive must not lose rows when BigQuery is unavailable.

History cannot be backfilled, and the diff that produced a batch is not
reproducible: _seen advances while the rows are built, so by the next
cycle the same events look unchanged and would never generate a row
again. A dropped batch is therefore permanent loss, which is what these
tests exist to prevent.
"""
import pytest

from ca_roads_demo import archive


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(archive, "_seen", {})
    monkeypatch.setattr(archive, "_pending", [])
    monkeypatch.setattr(archive, "_started", False)
    monkeypatch.setattr(archive, "ENABLED", True)
    yield


class _Boom:
    """A client whose insert always fails, like a BigQuery outage."""

    def __init__(self):
        self.calls = 0

    def insert_rows_json(self, table, rows):
        self.calls += 1
        raise RuntimeError("bigquery unavailable")


class _Recorder:
    def __init__(self):
        self.batches = []

    def insert_rows_json(self, table, rows):
        self.batches.append(list(rows))
        return []


def _events(n=2):
    return [{"id": f"chp:{i}", "kind": "incident", "lat": 37.0 + i,
             "lon": -122.0, "title": f"event {i}"} for i in range(n)]


@pytest.mark.asyncio
async def test_failed_batch_is_retained_not_lost(monkeypatch):
    boom = _Boom()
    monkeypatch.setattr(archive, "_bq", lambda: boom)
    out = await archive.observe(_events(3))
    assert out["archived"] == 0
    # The rows survived the failure.
    assert len(archive._pending) == 3, archive._pending


@pytest.mark.asyncio
async def test_retained_rows_go_out_on_the_next_cycle(monkeypatch):
    boom = _Boom()
    monkeypatch.setattr(archive, "_bq", lambda: boom)
    await archive.observe(_events(3))
    assert len(archive._pending) == 3

    rec = _Recorder()
    monkeypatch.setattr(archive, "_bq", lambda: rec)
    # Same events again: unchanged, so this cycle produces no new rows.
    # Without the retry buffer, nothing would ever be written.
    out = await archive.observe(_events(3))
    assert rec.batches, "the retained rows were never retried"
    assert len(rec.batches[0]) == 3
    assert out["archived"] == 3
    assert archive._pending == []


@pytest.mark.asyncio
async def test_partial_rejection_retains_only_the_bad_rows(monkeypatch):
    class Partial:
        def insert_rows_json(self, table, rows):
            return [{"index": 1, "errors": [{"reason": "invalid"}]}]

    monkeypatch.setattr(archive, "_bq", lambda: Partial())
    out = await archive.observe(_events(3))
    assert out["failed"] == 1
    assert len(archive._pending) == 1


@pytest.mark.asyncio
async def test_backlog_is_capped(monkeypatch):
    monkeypatch.setattr(archive, "PENDING_MAX", 5)
    boom = _Boom()
    monkeypatch.setattr(archive, "_bq", lambda: boom)
    await archive.observe(_events(8))
    # Bounded rather than growing until the instance dies.
    assert len(archive._pending) == 5


@pytest.mark.asyncio
async def test_failure_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(archive, "_bq", lambda: _Boom())
    with caplog.at_level("WARNING"):
        await archive.observe(_events(2))
    assert any("archive" in r.message.lower() or "archive" in r.name
               for r in caplog.records), caplog.text
