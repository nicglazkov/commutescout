"""The nationwide tool shared by the assistant and the MCP server."""

from ca_roads_mcp import server


async def test_nearby_events_filters_sorts_and_labels(monkeypatch):
    from ca_roads_demo import states as expansion

    async def fake_markers(client, box, want):
        assert "closure" in want
        return [
            {"kind": "lane_closure", "lat": 40.76, "lon": -111.9,
             "cls": "lane", "label": "I-15 NB lane closed",
             "route": "I-15", "src": "UDOT"},
            {"kind": "incident", "lat": 40.60, "lon": -111.8,
             "type": "Crash", "label": "Crash at 9000 S", "src": "UDOT"},
            # Inside the bbox corner but outside the radius circle.
            {"kind": "incident", "lat": 41.9, "lon": -110.6,
             "type": "Crash", "label": "Too far", "src": "WYDOT"},
        ]

    monkeypatch.setattr(expansion, "markers_for_bbox", fake_markers)
    out = await server.get_nearby_events(center="40.75,-111.89",
                                         radius_km=40)
    assert out["count"] == 2
    assert [e["summary"] for e in out["events"]] == [
        "I-15 NB lane closed", "Crash at 9000 S"]
    assert out["events"][0]["source"] == "UDOT"
    assert out["events"][0]["miles_away"] < out["events"][1]["miles_away"]


async def test_nearby_events_empty_is_honest(monkeypatch):
    from ca_roads_demo import states as expansion

    async def none(client, box, want):
        return []

    monkeypatch.setattr(expansion, "markers_for_bbox", none)
    out = await server.get_nearby_events(center="46.8,-100.78")
    assert out["count"] == 0 and "coverage" in out["message"]


async def test_nearby_events_rejects_bad_center():
    out = await server.get_nearby_events(center="not-a-point")
    assert "error" in out
