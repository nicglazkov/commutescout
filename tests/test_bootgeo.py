"""Approximate visitor location from edge headers into the page."""

from starlette.testclient import TestClient

from ca_roads_demo.app import _visitor_view, app


class FakeReq:
    def __init__(self, headers):
        self.headers = headers


def test_visitor_view_reads_and_rounds_edge_headers():
    v = _visitor_view(FakeReq({"cf-iplatitude": "37.7749295",
                               "cf-iplongitude": "-122.4194155"}))
    assert v == {"lat": 37.77, "lon": -122.42, "zoom": 10, "src": "edge"}


def test_visitor_view_rejects_missing_bogus_and_null_island():
    assert _visitor_view(FakeReq({})) is None
    assert _visitor_view(FakeReq({"cf-iplatitude": "nope",
                                  "cf-iplongitude": "-122.4"})) is None
    assert _visitor_view(FakeReq({"cf-iplatitude": "99.0",
                                  "cf-iplongitude": "-122.4"})) is None
    # 0,0 means "the header exists but the lookup failed"
    assert _visitor_view(FakeReq({"cf-iplatitude": "0.0",
                                  "cf-iplongitude": "0.0"})) is None


def test_index_serves_island_only_with_headers():
    client = TestClient(app)
    plain = client.get("/")
    assert plain.status_code == 200
    assert 'id="bootgeo"' not in plain.text

    located = client.get("/", headers={"cf-iplatitude": "47.6062",
                                       "cf-iplongitude": "-122.3321"})
    assert located.status_code == 200
    assert '<script type="application/json" id="bootgeo">' in located.text
    assert '"lat": 47.61' in located.text
    assert located.headers["cache-control"] == "private, no-store"
    # The island replaces the slot exactly once and leaves the page whole.
    assert located.text.count('id="bootgeo"') == 1
    assert "<!--BOOT_GEO-->" not in located.text
    # Nothing else changed: the injected page is the same document plus
    # the island (comparing newline-normalized, since the template is
    # read with universal newlines while the static file keeps CRLF).
    norm = plain.text.replace("\r\n", "\n")
    stripped = located.text.replace(
        '<script type="application/json" id="bootgeo">'
        '{"lat": 47.61, "lon": -122.33, "zoom": 10, "src": "edge"}</script>',
        "<!--BOOT_GEO-->")
    assert stripped == norm
