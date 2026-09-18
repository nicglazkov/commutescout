"""Server-side route planning: full closures become exclusions, the
candidates are re-ranked by what lies on them, presets map to Valhalla
options, and a failed exclusion run retries plainly and says so."""

import pytest

from ca_roads_demo import routing

# A straight east-west line along 37.5N, about 44 km long.
LINE = [[37.5, -122.4 + i * 0.005] for i in range(100)]


def _trip(points, seconds, length_mi=None):
    """A Valhalla-shaped trip whose shape is a precision-6 polyline."""
    def enc(pts):
        out = []
        last = (0, 0)
        for lat, lon in pts:
            for v, lv in ((round(lat * 1e6), last[0]), (round(lon * 1e6), last[1])):
                d = v - lv
                d = ~(d << 1) if d < 0 else d << 1
                while d >= 0x20:
                    out.append(chr((0x20 | (d & 0x1F)) + 63))
                    d >>= 5
                out.append(chr(d + 63))
            last = (round(lat * 1e6), round(lon * 1e6))
        return "".join(out)
    return {"legs": [{"shape": enc(points)}],
            "summary": {"time": seconds, "length": length_mi or 27.0}}


def test_on_route_uses_the_segment_not_just_the_vertices():
    # Halfway between two vertices, 50 m off the line: on it.
    assert routing.on_route(37.5 + 50 / 111_320, -122.4 + 0.0025, LINE)
    # 600 m off the line: not on it.
    assert not routing.on_route(37.5 + 600 / 111_320, -122.2, LINE)
    assert not routing.on_route(37.5, -121.0, LINE)  # past the end


def test_exclusions_sample_along_full_closures_and_cap_at_fifty():
    path = [[37.5, -122.4 + i * 0.01] for i in range(6)]  # ~4.4 km
    markers = [
        {"kind": "lane_closure", "cls": "full-roadway", "lat": 37.5, "lon": -122.4,
         "path": path},
        {"kind": "lane_closure", "cls": "lane", "lat": 37.6, "lon": -122.4},
        {"kind": "lane_closure", "cls": "full-roadway", "lat": 38.0, "lon": -121.0,
         "end": [38.01, -121.0]},
        {"kind": "chain_control", "status": "R-2", "lat": 39.0, "lon": -120.0},
    ]
    excl = routing.exclusions(markers)
    lats = {e["lat"] for e in excl}
    assert 37.5 in lats and 38.0 in lats and 38.01 in lats and 39.0 not in lats
    # Both ends plus one point every 1.5 km along the 4.4 km path.
    assert sum(1 for e in excl if e["lat"] == 37.5) == 4
    assert routing.exclusions(markers, avoid_chains=True)[-1]["lat"] == 39.0
    many = [{"kind": "lane_closure", "cls": "full-roadway", "lat": 40 + i * 0.01,
             "lon": -120.0} for i in range(80)]
    assert len(routing.exclusions(many)) == routing.EXCLUDE_CAP


def test_score_counts_only_what_sits_on_the_line():
    markers = [
        {"kind": "incident", "type": "1183-Trfc Collision-Unkn Inj", "lat": 37.5001,
         "lon": -122.3},
        {"kind": "incident", "type": "1183-Trfc Collision-Unkn Inj", "lat": 37.5001,
         "lon": -122.25},
        # 2.2 km off the line: not counted.
        {"kind": "incident", "type": "FIRE-Report of Fire", "lat": 37.52, "lon": -122.3},
        {"kind": "lane_closure", "cls": "lane", "lat": 37.5, "lon": -122.1},
        {"kind": "lane_closure", "cls": "one-way-traffic", "lat": 37.5, "lon": -122.15},
        {"kind": "lane_closure", "cls": "alternating-lanes", "lat": 37.5, "lon": -122.12},
        {"kind": "chain_control", "status": "R-2", "lat": 37.5, "lon": -122.0},
        {"kind": "chain_control", "status": "None", "lat": 37.5, "lon": -122.05},
    ]
    s = routing.score(LINE, markers)
    assert s["penalty_min"] == 6 + 6 + 4 + 5 + 5 + 12
    labels = [h["label"] for h in s["hassles"]]
    assert labels == ["1 R-2 chain control", "2 collisions", "2 one-way stretches",
                      "1 lane closure"]


def test_full_closure_left_on_the_line_is_charged_hard():
    markers = [{"kind": "lane_closure", "cls": "full-roadway", "lat": 37.5, "lon": -122.2}]
    s = routing.score(LINE, markers)
    assert s["penalty_min"] == 45 and s["hassles"][0]["label"] == "1 full closure"


@pytest.mark.asyncio
async def test_plan_ranks_by_time_plus_hassle_and_sends_exclusions():
    clean = [[37.6, -122.4 + i * 0.005] for i in range(100)]
    calls = []

    async def fetch(body):
        calls.append(body)
        return {"trip": _trip(LINE, 3000), "alternates": [{"trip": _trip(clean, 3300)}]}

    markers = [
        {"kind": "incident", "type": "1183-Trfc Collision", "lat": 37.5, "lon": -122.3},
        {"kind": "incident", "type": "1183-Trfc Collision", "lat": 37.5, "lon": -122.2},
        {"kind": "lane_closure", "cls": "full-roadway", "lat": 38.5, "lon": -121.0},
    ]
    out = await routing.plan(fetch, markers, [{"lat": 37.5, "lon": -122.4},
                                              {"lat": 37.5, "lon": -121.9}])
    assert calls[0]["alternates"] == 2
    assert calls[0]["exclude_locations"] == [{"lat": 38.5, "lon": -121.0}]
    assert out["excluded"] == 1 and out["note"] is None
    # The 50-minute line carries two collisions (12 min); the 55-minute
    # clean line wins.
    assert [r["score_s"] for r in out["routes"]] == [3300, 3720]
    assert out["routes"][1]["hassles"][0]["label"] == "2 collisions"
    assert out["routes"][0]["hassles"] == []


@pytest.mark.asyncio
async def test_plan_retries_without_exclusions_and_says_so():
    seen = []

    async def fetch(body):
        seen.append("exclude_locations" in body)
        if "exclude_locations" in body:
            return None
        return {"trip": _trip(LINE, 3000)}

    markers = [{"kind": "lane_closure", "cls": "full-roadway", "lat": 37.5, "lon": -122.2}]
    out = await routing.plan(fetch, markers, [{"lat": 37.5, "lon": -122.4},
                                              {"lat": 37.5, "lon": -121.9}])
    assert seen == [True, False]
    assert out["excluded"] == 0 and "full closure" in out["note"]
    assert out["routes"][0]["hassles"][0]["kind"] == "full closure"


@pytest.mark.asyncio
async def test_presets_map_to_valhalla_options():
    bodies = []

    async def fetch(body):
        bodies.append(body)
        return {"trip": _trip(LINE, 3000)}

    locs = [{"lat": 37.5, "lon": -122.4}, {"lat": 37.5, "lon": -121.9}]
    for preset in ("no_highways", "no_tolls", "shortest", "avoid_chains", "bogus"):
        await routing.plan(fetch, [], locs, preset)
    assert bodies[0]["costing_options"] == {"auto": {"use_highways": 0}}
    assert bodies[1]["costing_options"] == {"auto": {"use_tolls": 0}}
    assert bodies[2]["shortest"] is True
    assert "costing_options" not in bodies[3] and "exclude_locations" not in bodies[3]
    assert "shortest" not in bodies[4]  # unknown preset falls back to fastest
    # Three points: no alternates (Valhalla only offers them for two).
    await routing.plan(fetch, [], locs + [{"lat": 37.6, "lon": -121.8}])
    assert bodies[-1]["alternates"] == 0


def test_unconfirmed_community_closures_never_steer_the_router():
    def closure(**extra):
        return {"kind": "plugin", "flare_kind": "ROAD_CLOSED", "lat": 37.5, "lon": -122.0, **extra}

    def excluded(**extra):
        return len(routing.exclusions([closure(**extra)]))

    # One signed-in report, nobody has confirmed it: drawn on the map, ignored here.
    assert excluded(source_id="commutescout", tier="approved", confirmations=0) == 0
    assert excluded(source_id="commutescout", tier="approved", confirmations=1) == 0
    # Two other people confirmed it.
    assert excluded(source_id="commutescout", tier="approved", confirmations=2) == 1
    # A plugin nobody reviewed gets no veto on its own; confirmations still count.
    assert excluded(source_id="sabreplus", tier="unreviewed", confirmations=0) == 0
    assert excluded(source_id="sabreplus", tier="unreviewed", confirmations=3) == 1
    # A reviewed plugin's closure counts on its own.
    assert excluded(source_id="official", tier="approved", confirmations=0) == 1
    # Missing fields mean untrusted.
    assert excluded() == 0
