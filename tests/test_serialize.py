import pytest

from ca_roads_mcp.serialize import direction_hint


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Us101 N / Ccg", "northbound"),
        ("I80 W / Mace Blvd", "westbound"),
        ("SR17 S / Summit Rd", "southbound"),
        ("US50 E / Echo Summit", "eastbound"),
        ("NB 101 at Trimble", "northbound"),
        ("SB101 JSO Story Rd", None),  # no standalone token, ambiguous
        ("Jackson Rd / Mayhew Rd", None),
        ("I5 / Grapevine Rd", None),  # route present, no direction letter
    ],
)
def test_direction_hint(location, expected):
    assert direction_hint(location) == expected


def test_visitor_hash_rotates_and_anonymizes():
    from ca_roads_mcp.telemetry import visitor_hash

    a = visitor_hash("203.0.113.7")
    assert a == visitor_hash("203.0.113.7")  # stable within the day
    assert a != visitor_hash("203.0.113.8")
    assert "203" not in a and len(a) == 12
