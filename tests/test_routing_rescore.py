"""Community alerts along a route count once the route is known."""

from ca_roads_demo import routing


def test_rescore_counts_the_alerts_only_the_route_could_reveal(monkeypatch):
    # A router's line is dense; two points 44 km apart are not one.
    pts = routing._along([[37.0, -122.0], [37.0, -121.5]], 500.0)
    monkeypatch.setattr(routing, "_trip_points", lambda trip: pts)
    out = {"routes": [{"trip": {"summary": {"time": 600}}, "score_s": 600,
                       "penalty_min": 0, "hassles": []}]}
    kind = next(iter(routing.PLUGIN_PENALTY))
    alert = {"kind": "plugin", "flare_kind": kind, "lat": 37.001, "lon": -121.8}
    routing.rescore(out, [alert])
    r = out["routes"][0]
    assert r["penalty_min"] > 0 and r["score_s"] > 600 and r["hassles"]
