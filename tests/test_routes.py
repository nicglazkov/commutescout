import pytest

from ca_roads_mcp.routes import matches_route, normalize_route, routes_mentioned


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("17", "SR-17"),
        ("80", "I-80"),
        ("50", "US-50"),
        ("101", "US-101"),
        ("99", "SR-99"),
        ("I-80", "I-80"),
        ("i80", "I-80"),
        ("Interstate 5", "I-5"),
        ("US 50", "US-50"),
        ("u.s. 101", "US-101"),
        ("SR-1", "SR-1"),
        ("CA-1", "SR-1"),
        ("Hwy 17", "SR-17"),
        ("Highway 50", "US-50"),
        ("Route 88", "SR-88"),
        ("880", "I-880"),
        ("267", "SR-267"),
    ],
)
def test_normalize_route(raw, expected):
    assert normalize_route(raw) == expected


def test_normalize_route_rejects_non_routes():
    assert normalize_route("") is None
    assert normalize_route(None) is None
    assert normalize_route("Main Street") is None
    assert normalize_route("I-80 and US-50") is None


def test_routes_mentioned_in_chp_location():
    assert routes_mentioned("I80 E / Mace Blvd") == {"I-80"}
    assert routes_mentioned("US50 W / Watt Ave") == {"US-50"}
    assert routes_mentioned("SR17 NB / Summit Rd") == {"SR-17"}
    assert routes_mentioned("Hwy 99 at Elk Grove") == {"SR-99"}
    assert routes_mentioned("Jackson Rd / Mayhew Rd") == set()
    # A bare number is not a route mention.
    assert routes_mentioned("1500 Main St") == set()


def test_matches_route():
    assert matches_route("I80 E / Mace Blvd", "I-80")
    assert not matches_route("I80 E / Mace Blvd", "US-50")
    assert not matches_route("Jackson Rd / Mayhew Rd", "I-80")
