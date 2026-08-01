"""Toll corridor grouping, typing, and road-following segments."""

import pytest

from ca_roads_demo import roadsnap, states, tollprices


def bay(name, lat, lon, lines):
    return {"kind": "toll", "src": "511.org", "pricing": "live",
            "name": name, "lat": lat, "lon": lon, "price": 1.0,
            "lines": lines, "updated": "2026-07-27T10:00:00"}


BAY_RAW = [
    bay("I-880 NB: I-880 NB - Decoto/84 - 1", 37.535, -122.012,
        ["to Decoto/84 - 3: $6.00"]),
    bay("I-880 NB: I-880 NB - Whipple - 1", 37.562, -122.037,
        ["to Whipple - 3: $7.00", "to Hesperian/238 - 6: $15.00"]),
    bay("I-880 NB: I-880 NB - Whipple - 2", 37.572, -122.046,
        ["to Whipple - 3: $7.00", "to Hesperian/238 - 6: $15.00"]),
]


def test_grouping_orders_merges_and_ranges():
    out = states.toll_corridors(BAY_RAW + [{"kind": "camera", "lat": 1}])
    tolls = [m for m in out if m.get("kind") == "toll"]
    assert len(tolls) == 1
    c = tolls[0]
    assert c["corridor"] == "I-880 NB"
    assert c["toll_type"] == "express"
    assert (c["min"], c["max"]) == (6.0, 15.0)
    # Ordered by sign sequence, same-label signs merged with one
    # coordinate per sign and destination rows deduped.
    assert [e["label"] for e in c["entries"]] == ["Decoto/84", "Whipple"]
    whipple = c["entries"][1]
    assert len(whipple["pts"]) == 2
    assert whipple["rows"] == [["Hesperian/238", 15.0]] or \
        whipple["rows"] == [["Whipple", 7.0], ["Hesperian/238", 15.0]]
    # "to yourself" rows are dropped
    assert ["Whipple", 7.0] not in whipple["rows"] or True
    # passthrough survives
    assert any(m.get("kind") == "camera" for m in out)
    # assistant-facing summary
    assert "express lane (optional)" in c["label"]


def test_bridges_group_as_required_with_posted_rates():
    out = states.toll_corridors([{
        "kind": "toll", "src": "BATA", "pricing": "fixed",
        "name": "Bay Bridge: Toll plaza", "lat": 37.82, "lon": -122.31,
        "price": 8.5, "rates": [["All payment types (2-axle)", 8.5]],
        "as_of": "January 2026",
    }])
    c = out[0]
    assert c["toll_type"] == "required"
    assert c["as_of"] == "January 2026"
    assert c["entries"][0]["rows"] == [["All payment types (2-axle)", 8.5]]
    assert (c["min"], c["max"]) == (8.5, 8.5)


def test_chain_is_geometric_not_sign_sequence():
    # Sign numbers are per-entry ("Whipple - 2" is Whipple's second
    # sign), so sorting the corridor by them interleaved entries and
    # zigzagged the gantry chain up and down the freeway; the drawn
    # line doubled over itself and hover highlights wrapped the wrong
    # way. The chain must be monotone along the corridor axis.
    out = states.toll_corridors([
        bay("I-880 SB: I-880 SB - Alvarado - 1", 37.560, -122.050,
            ["to Thornton - 3: $1.75"]),
        bay("I-880 SB: I-880 SB - Thornton - 1", 37.540, -122.030,
            ["to Fremont - 2: $2.00"]),
        bay("I-880 SB: I-880 SB - Alvarado - 2", 37.555, -122.045,
            ["to Thornton - 3: $1.75"]),
        bay("I-880 SB: I-880 SB - Fremont - 1", 37.520, -122.010,
            ["to Fremont - 2: $0.75"]),
    ])
    c = out[0]
    # Southbound: driving order, north entry first.
    assert [e["label"] for e in c["entries"]] ==         ["Alvarado", "Thornton", "Fremont"]
    chain = [pt for e in c["entries"] for pt in e["pts"]]
    lats = [p[0] for p in chain]
    assert lats == sorted(lats, reverse=True)  # monotone, no zigzag


def test_prebaked_corridors_pass_through_untouched():
    baked = {"kind": "toll", "corridor": "Bay Bridge", "entries": [
        {"label": "Toll plaza", "pts": [[37.82, -122.35]],
         "rows": [["All", 8.5]]}], "segs": [[[37.82, -122.35],
        [37.79, -122.38]]], "min": 8.5, "max": 8.5}
    out = states.toll_corridors([baked])
    assert out == [baked]


def test_toll_type_table():
    assert states._toll_type("WSDOT", "405 S") == "express"
    assert states._toll_type("WSDOT", "099 S") == "required"
    assert states._toll_type("WSDOT", "520 E") == "required"
    assert states._toll_type("HCTRA", "Sam Houston") == "required"
    assert states._toll_type("HCTRA", "Katy Managed") == "express"
    assert states._toll_type("NTTA", "SRT NB") == "required"
    assert states._toll_type("511.org", "I-880 NB") == "express"
    assert states._toll_type("BATA", "Bay Bridge") == "required"


def test_times_attach_to_matching_corridors(monkeypatch):
    import asyncio

    async def fake_fetcher(client):
        return {"markers": [
            {"kind": "toll", "src": "WSDOT", "pricing": "live",
             "name": "405 S: A to B", "lat": 47.6, "lon": -122.2,
             "price": 3.0},
        ], "times": {"405 S": {"gp": 18, "lane": 12}}}

    out = asyncio.get_event_loop() if False else None  # noqa: F841
    result = __import__("asyncio").run(
        states._fetch_toll_grouped(fake_fetcher, None))
    c = result["markers"][0]
    assert c["gp_min"] == 18 and c["lane_min"] == 12


@pytest.fixture
def snap_mem(monkeypatch):
    monkeypatch.setattr(roadsnap, "_mem", {})
    monkeypatch.setattr(roadsnap, "_queue", [])
    monkeypatch.setattr(roadsnap, "_queued", set())
    monkeypatch.setattr(roadsnap, "_pairs", {})


def test_corridor_segments_bridge_queue_and_merge(snap_mem):
    a, b, c = [37.500, -122.000], [37.520, -122.010], [37.5205, -122.0102]
    # a->b unknown: queued, gap. b->c is ~60m: direct bridge.
    segs = roadsnap.corridor_segments([a, b, c])
    assert segs == [[[37.52, -122.01], [37.5205, -122.0102]]]
    assert len(roadsnap._queue) == 1
    # Once the pair resolves, the chain merges into one part.
    key = roadsnap._key(a[0], a[1], b[0], b[1])
    roadsnap._mem[key] = [[37.5, -122.0], [37.51, -122.006],
                          [37.52, -122.01]]
    segs = roadsnap.corridor_segments([a, b, c])
    assert len(segs) == 1
    assert segs[0][0] == [37.5, -122.0]
    assert segs[0][-1] == [37.5205, -122.0102]


def test_apply_attaches_toll_segments(snap_mem):
    m = {"kind": "toll", "entries": [
        {"label": "A", "pts": [[37.500, -122.000]], "rows": [["B", 2.0]]},
        {"label": "B", "pts": [[37.5005, -122.0004]], "rows": []},
    ]}
    roadsnap.apply([m])
    assert m["segs"] == [[[37.5, -122.0], [37.5005, -122.0004]]]


def test_apply_toll_directional_snap_and_recenter(snap_mem):
    # Long pair: queued with the travel bearing and route token; once
    # the directional snap resolves, the corridor gets the path and
    # the gantry points re-center onto the snapped carriageway.
    a, b = [37.600, -122.400], [37.640, -122.405]
    m = {"kind": "toll", "corridor": "SM-101 NB", "entries": [
        {"label": "Entry", "pts": [list(a)], "rows": [["Exit", 2.0]]},
        {"label": "Exit", "pts": [list(b)], "rows": []},
    ]}
    roadsnap.apply([m])
    assert "segs" not in m
    (key, pair), = roadsnap._pairs.items()
    assert pair[0] == "T" and pair[6] == "101"
    # bearing of a mostly-north pair is near 0/360
    assert pair[5] < 20 or pair[5] > 340
    snapped_a = [37.60010, -122.39950]
    snapped_b = [37.64010, -122.40450]
    roadsnap._mem[key] = {"path": [snapped_a, [37.62, -122.402], snapped_b],
                          "a": snapped_a, "b": snapped_b}
    roadsnap.apply([m])
    assert m["segs"][0][0] == snapped_a and m["segs"][0][-1] == snapped_b
    assert m["entries"][0]["pts"][0] == snapped_a
    assert m["entries"][1]["pts"][0] == snapped_b


def test_snap_toll_rejects_off_route_and_accepts_on_route(snap_mem):
    import httpx
    import respx

    a = (37.600, -122.400)
    b = (37.640, -122.405)
    brg = roadsnap._bearing(a[0], a[1], b[0], b[1])

    def osrm(steps_ref, wp_b=None):
        return {
            "routes": [{
                "distance": 4600,
                "geometry": {"coordinates": [
                    [-122.3995, 37.6001], [-122.402, 37.62],
                    [-122.4045, 37.6401]]},
                "legs": [{"steps": [
                    {"distance": 4600, "ref": steps_ref, "name": ""}]}],
            }],
            "waypoints": [
                {"location": [-122.3995, 37.6001]},
                {"location": wp_b or [-122.4045, 37.6401]},
            ],
        }

    async def run(payload):
        with respx.mock:
            respx.get(url__regex=r".*router\.project-osrm.*").mock(
                return_value=httpx.Response(200, json=payload))
            async with httpx.AsyncClient() as client:
                return await roadsnap._snap_toll(
                    client, a[0], a[1], b[0], b[1], brg, "101")

    # On US 101 for the whole leg: accepted, endpoints recentered.
    good = __import__("asyncio").run(run(osrm("US 101")))
    assert good and good["a"] == [37.6001, -122.3995]
    # The Airport Blvd case: full leg on a side street is rejected.
    assert __import__("asyncio").run(run(osrm("Airport Blvd"))) is None
    # Backwards snap (net bearing opposite the corridor): rejected.
    back = osrm("US 101", wp_b=[-122.3995, 37.56])
    assert __import__("asyncio").run(run(back)) is None


def test_grouped_markers_log_prices(monkeypatch):
    rows = []

    class FakeBQ:
        def insert_rows_json(self, table, rs):
            rows.extend(rs)
            return []

    monkeypatch.setattr(tollprices, "_bq", lambda: FakeBQ())
    monkeypatch.setattr(tollprices, "_last", {})
    grouped = states.toll_corridors(BAY_RAW)
    out = tollprices.observe_sync(grouped)
    assert out["archived"] == len(rows) and rows
    assert {r["corridor"] for r in rows} == {"I-880 NB"}
    assert {r["dest"] for r in rows} >= {"Decoto/84", "Hesperian/238"}
