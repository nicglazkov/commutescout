import pytest

from ca_roads.geo import districts_for, haversine_meters


def test_haversine_known_distance():
    # Sacramento to South Lake Tahoe, ~140 km great-circle.
    d = haversine_meters(38.5816, -121.4944, 38.9399, -119.9772)
    assert d == pytest.approx(137_000, rel=0.05)


def test_districts_for_tahoe_includes_d3():
    assert 3 in districts_for(38.9399, -119.9772, 50_000)


def test_districts_for_bay_area():
    districts = districts_for(37.7749, -122.4194, 30_000)
    assert 4 in districts
    assert 8 not in districts


def test_large_radius_spans_multiple_districts():
    districts = districts_for(38.5816, -121.4944, 200_000)
    assert {3, 4, 10}.issubset(set(districts))
