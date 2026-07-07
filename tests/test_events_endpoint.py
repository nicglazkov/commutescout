import json

import pytest
from starlette.testclient import TestClient

from ca_roads_demo.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_event_beacon_accepts_allowlisted(client, capsys):
    r = client.post("/api/event", json={"event": "pageview"})
    assert r.status_code == 200
    logged = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert logged["event"] == "pageview"
    assert "visitor" in logged and len(logged["visitor"]) == 12


def test_event_beacon_rejects_unknown(client):
    assert client.post("/api/event", json={"event": "evil"}).status_code == 400
    assert client.post("/api/event", content=b"junk").status_code == 400


def test_feedback_carries_question(client, capsys):
    r = client.post("/api/event", json={
        "event": "feedback_down", "question": "Is 17 clear?" * 100,
    })
    assert r.status_code == 200
    logged = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert logged["event"] == "feedback_down"
    assert len(logged["question"]) <= 300  # capped
