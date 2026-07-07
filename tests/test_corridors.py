from ca_roads.models import ChainControl, ChpIncident, RoadEvent
from ca_roads_mcp import corridors as corr


def find(corridor_id):
    return next(c for c in corr.CORRIDORS if c.id == corridor_id)


def test_resolve_sacramento_to_reno_is_i80():
    match = corr.resolve_corridor("Sacramento", "Reno")
    assert match is not None
    assert match.corridor.id == "i80-sac-reno"
    assert not match.reversed


def test_resolve_reversed():
    match = corr.resolve_corridor("Reno", "Sacramento")
    assert match.corridor.id == "i80-sac-reno"
    assert match.reversed


def test_resolve_tahoe_prefers_us50():
    match = corr.resolve_corridor("Sacramento", "Tahoe")
    assert match.corridor.id == "us50-sac-tahoe"


def test_resolve_san_jose_to_santa_cruz_is_sr17():
    match = corr.resolve_corridor("San Jose", "Santa Cruz")
    assert match.corridor.id == "sr17"


def test_resolve_unknown_places():
    assert corr.resolve_corridor("Boise", "Portland") is None


def test_corridor_districts_i80():
    districts = corr.corridor_districts(find("i80-sac-reno"))
    assert 3 in districts  # Sacramento / Sierra
    assert 7 not in districts  # not Los Angeles


def test_distance_to_corridor_on_and_off_route():
    i80 = find("i80-sac-reno")
    # Truckee is on the corridor.
    dist, along = corr.distance_to_corridor(i80, 39.33, -120.18)
    assert dist < 2_000
    assert along > 100_000  # well past Sacramento
    # South Lake Tahoe is tens of km off I-80.
    dist_slt, _ = corr.distance_to_corridor(i80, 38.94, -119.98)
    assert dist_slt > 20_000


def make_chain_event(lat, lon, route):
    record = ChainControl(
        index="x", district=3, route=route, county="", direction="",
        location_name="loc", nearby_place="", lat=lat, lon=lon,
        in_service=True, status="R-2", status_description="",
        status_updated_at=None,
    )
    return RoadEvent(
        source="chains", id="cc_x", family="chains", lat=lat, lon=lon,
        summary=f"Chains R-2 on {route}", reported_at=None, record=record,
    )


def make_chp_event(lat, lon, location):
    record = ChpIncident(
        id="1", log_type="1125-Traffic Hazard", location=location, area="",
        lat=lat, lon=lon, reported_at=None,
    )
    return RoadEvent(
        source="chp", id="chp_1", family="incident", lat=lat, lon=lon,
        summary=location, reported_at=None, record=record,
    )


def test_events_on_corridor_route_field_must_match():
    i80 = find("i80-sac-reno")
    on_i80 = make_chain_event(39.32, -120.33, "I-80")  # Donner Summit
    on_sr20 = make_chain_event(39.32, -120.33, "SR-20")  # same point, wrong route
    placed = corr.events_on_corridor(i80, [on_i80, on_sr20])
    assert [p.event.id for p in placed] == ["cc_x"]
    assert placed[0].event.record.route == "I-80"


def test_events_on_corridor_chp_text_matching():
    i80 = find("i80-sac-reno")
    # ~6 km off the centerline near Auburn: kept only if text names I-80.
    named = make_chp_event(38.90, -120.99, "I80 E / Bell Rd")
    other_hwy = make_chp_event(38.90, -120.99, "SR49 / Bell Rd")
    unnamed_far = make_chp_event(38.90, -120.99, "Bell Rd / Musso Rd")
    placed = corr.events_on_corridor(i80, [named, other_hwy, unnamed_far])
    assert [p.event.summary for p in placed] == ["I80 E / Bell Rd"]


def test_events_on_corridor_ordering_and_reversal():
    i80 = find("i80-sac-reno")
    near_sac = make_chp_event(38.75, -121.28, "I80 E / Douglas Blvd")
    near_truckee = make_chp_event(39.33, -120.18, "I80 W / Donner Pass Rd")
    placed = corr.events_on_corridor(i80, [near_truckee, near_sac])
    assert [p.event.summary for p in placed] == [
        "I80 E / Douglas Blvd", "I80 W / Donner Pass Rd",
    ]
    placed_rev = corr.events_on_corridor(
        i80, [near_truckee, near_sac], reversed_direction=True
    )
    assert [p.event.summary for p in placed_rev] == [
        "I80 W / Donner Pass Rd", "I80 E / Douglas Blvd",
    ]


def test_fires_use_wide_buffer_and_no_route_test():
    i80 = find("i80-sac-reno")
    fire = RoadEvent(
        source="wfigs", id="fire_1", family="fire",
        lat=39.20, lon=-120.60,  # ~12 km off the I-80 line near Emigrant Gap
        summary="Wildfire: TEST", reported_at=None, record=None,
    )
    placed = corr.events_on_corridor(i80, [fire])
    assert len(placed) == 1


def test_resolve_ext_snaps_landmark_to_corridor():
    # Alice's Restaurant (SR-84/Skyline, Woodside) is on no alias list, but
    # its coordinates snap to the I-280 Peninsula corridor.
    match = corr.resolve_corridor_ext(
        "San Jose", "Alice's Restaurant", None, (37.417, -122.276)
    )
    assert match is not None
    assert match.corridor.id == "i280"


def test_clip_geometry_spans_only_the_window():
    i280 = find("i280")
    total = corr.total_length(i280)
    # From the San Jose end back toward Woodside (mid-corridor).
    _, along_woodside = corr.distance_to_corridor(i280, 37.417, -122.276)
    pts = corr.clip_geometry(i280, total, along_woodside)
    # Travel order: starts near San Jose, ends near Woodside; SF (37.77)
    # never appears.
    assert pts[0][0] < 37.45
    assert abs(pts[-1][0] - 37.40) < 0.12
    assert max(lat for lat, lon in pts) < 37.6


def test_point_at_endpoints():
    i280 = find("i280")
    assert corr.point_at(i280, 0) == i280.waypoints[0]
    assert corr.point_at(i280, corr.total_length(i280) + 999) == i280.waypoints[-1]


def test_alias_matching_is_whole_phrase():
    # "17288 Skyline Blvd, Woodside" must resolve via the word "woodside"
    # (I-280), never via the digits "17" hijacking SR-17.
    match = corr.resolve_corridor("San Jose", "17288 Skyline Blvd, Woodside")
    assert match.corridor.id == "i280"
    # "Palo Alto" must not match the "la" alias of the US-101 corridor.
    match = corr.resolve_corridor("Palo Alto", "Los Angeles")
    assert match is None or "la" not in match.corridor.aliases_a
    # Whole words still work.
    assert corr.resolve_corridor("SF", "LA").corridor.id == "us101-sf-la"
