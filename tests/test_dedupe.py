from ca_roads.dedupe import dedupe
from ca_roads.models import RoadEvent


def event(source, family, lat, lon, id_suffix="1"):
    return RoadEvent(
        source=source,
        id=f"{source}_{id_suffix}",
        family=family,
        lat=lat,
        lon=lon,
        summary=f"{source} {family}",
        reported_at=None,
    )


def test_cross_source_duplicate_keeps_higher_priority():
    chp = event("chp", "closure", 38.5000, -121.5000)
    lcs = event("lcs", "closure", 38.5001, -121.5001)  # ~14 m away
    assert dedupe([lcs, chp]) == [chp]
    assert dedupe([chp, lcs]) == [chp]


def test_same_source_never_merges():
    a = event("chp", "accident", 38.5000, -121.5000, "a")
    b = event("chp", "accident", 38.5000, -121.5000, "b")
    assert len(dedupe([a, b])) == 2


def test_different_family_never_merges():
    fire = event("wfigs", "fire", 38.5, -121.5)
    incident = event("chp", "incident", 38.5, -121.5)
    assert len(dedupe([fire, incident])) == 2


def test_far_apart_never_merges():
    a = event("chp", "closure", 38.5, -121.5)
    b = event("lcs", "closure", 38.51, -121.5)  # ~1.1 km apart
    assert len(dedupe([a, b])) == 2


def test_empty_and_single():
    assert dedupe([]) == []
    only = event("chp", "incident", 38.5, -121.5)
    assert dedupe([only]) == [only]
