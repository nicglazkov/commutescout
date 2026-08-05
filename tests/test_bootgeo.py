"""Approximate visitor location from edge headers into the page."""

from starlette.testclient import TestClient

from ca_roads_demo.app import _visitor_view, app


class FakeReq:
    def __init__(self, headers):
        self.headers = headers


def test_visitor_view_reads_and_rounds_edge_headers():
    # Transform-rule headers (what the zone actually sends)...
    v = _visitor_view(FakeReq({"x-visitor-lat": "37.7749295",
                               "x-visitor-lon": "-122.4194155"}))
    assert v == {"lat": 37.77, "lon": -122.42, "zoom": 10, "src": "edge"}
    # ...and the managed-transform names, if those are ever enabled.
    v = _visitor_view(FakeReq({"cf-iplatitude": "47.6062",
                               "cf-iplongitude": "-122.3321"}))
    assert v == {"lat": 47.61, "lon": -122.33, "zoom": 10, "src": "edge"}


def test_visitor_view_rejects_missing_bogus_and_null_island():
    assert _visitor_view(FakeReq({})) is None
    assert _visitor_view(FakeReq({"cf-iplatitude": "nope",
                                  "cf-iplongitude": "-122.4"})) is None
    # A visitor Cloudflare cannot place gets empty header values.
    assert _visitor_view(FakeReq({"x-visitor-lat": "",
                                  "x-visitor-lon": ""})) is None
    assert _visitor_view(FakeReq({"cf-iplatitude": "99.0",
                                  "cf-iplongitude": "-122.4"})) is None
    # 0,0 means "the header exists but the lookup failed"
    assert _visitor_view(FakeReq({"cf-iplatitude": "0.0",
                                  "cf-iplongitude": "0.0"})) is None


def test_index_serves_island_only_with_headers():
    client = TestClient(app)
    plain = client.get("/map")
    assert plain.status_code == 200
    assert 'id="bootgeo"' not in plain.text

    located = client.get("/map", headers={"cf-iplatitude": "47.6062",
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


def _index_html():
    import pathlib
    return pathlib.Path(
        "src/ca_roads_demo/static/map.html").read_text(encoding="utf-8")


def test_saved_view_is_per_tab_not_per_browser():
    """The restored map view MUST live in sessionStorage.

    sessionStorage survives a reload and dies with the tab, which is the
    whole behaviour: reloading keeps the area you moved to, a brand new
    tab still opens on where you are. Switching this to localStorage
    would silently break the second half, because someone who scrolled
    to Chicago yesterday would get Chicago again today instead of their
    own commute.
    """
    import re

    html = _index_html()
    key = re.search(r"const VIEW_KEY = '([^']+)'", html).group(1)
    # Every read and write of the view key goes through sessionStorage.
    for m in re.finditer(r"(\w+Storage)\.(?:get|set|remove)Item\(VIEW_KEY",
                         html):
        assert m.group(1) == "sessionStorage", m.group(0)
    assert f"sessionStorage.getItem({'VIEW_KEY'})" in html \
        or "sessionStorage.getItem(VIEW_KEY)" in html
    assert "sessionStorage.setItem(VIEW_KEY" in html
    assert key
    # And nothing else stores a map view in localStorage.
    assert "localStorage.setItem(VIEW_KEY" not in html


def test_saved_view_is_validated_before_use():
    """A stale or hand-edited value must not strand the map off-world."""
    html = _index_html()
    fn = html.split("function readSavedView()", 1)[1].split("\nfunction", 1)[0]
    assert "85" in fn and "180" in fn        # latitude / longitude bounds
    assert "Number.isFinite" in fn
    assert "17" in fn                        # max zoom the basemap serves


def test_view_write_is_deferred_off_the_gesture_path():
    """The write is coalesced and runs at idle: panning must not pay a
    synchronous storage write per gesture."""
    html = _index_html()
    assert "requestIdleCallback(run, { timeout: 1000 })" in html
    # requestIdleCallback's second argument is an options object; passing
    # a number there throws, which has bitten this file before.
    import re
    for m in re.finditer(r"requestIdleCallback\([^,)]+,\s*([^)]+)\)", html):
        assert m.group(1).strip().startswith("{"), m.group(0)
