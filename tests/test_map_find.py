"""The find box on the map takes a place, an address or coordinates and
drops a pin with "Navigate here"; the From/To planner stays as it is."""

import re
from pathlib import Path

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")


def test_find_box_tops_the_floating_panel():
    # Round-3 board #3: "Search maps" sits at the top of the floating
    # panel (folded, it floats alone; on a phone, over the map). The map
    # carries no Report button and no Leaflet zoom in the top left.
    panel = HTML[HTML.index('<aside id="panel">'):HTML.index('<section id="pane-places"')]
    assert 'id="findbox"' in panel and 'role="search"' in panel
    card = re.search(
        r'<div class="map-card active" id="mapcard">(.*?)<div class="resizer" id="inspresize"',
        HTML, re.S,
    ).group(1)
    assert 'id="findbox"' not in card and 'id="reportbtn"' not in HTML
    assert HTML.count('id="find"') == 1 and HTML.count('id="findsugg"') == 1
    assert 'aria-label="Find a place on the map"' in HTML
    assert 'placeholder="Search maps"' in HTML
    assert ".findbox { position:relative }" in CSS
    assert ".findbox .val:empty, .findbox .val.ok { display:none }" in CSS
    assert "if (map.zoomControl) map.zoomControl.remove();" in APP


def test_planner_fields_stay():
    assert HTML.count('id="from"') == 1 and HTML.count('id="to"') == 1
    assert "wireAddress('from', 'fromval', 'fromsugg', true)" in APP
    assert "wireAddress('to', 'toval', 'tosugg', false)" in APP


def test_result_becomes_a_pin_with_navigate_here():
    assert "wireAddress('find', 'findval', 'findsugg', false, showFound)" in APP
    # Map v2 (2026-11): the button reads Directions, and the editor plans by
    # itself once both ends are set (no Plan button), so the pin only fills
    # the destination and opens Directions inside Places.
    assert "nav.textContent = 'Directions'" in APP
    body = APP[APP.index("function navigateTo(c) {"):]
    body = body[:body.index("\n}\n")]
    assert "toF.pick(c);" in body
    assert "openDirections();" in body


def test_coordinates_are_a_place_without_the_geocoder():
    assert "function parseCoords(s)" in APP
    assert "if (coord) { items = [coord]; active = 0; render(); return; }" in APP
    assert "if (coord) { pick(coord); return; }" in APP


def test_quick_picks_and_recents_like_the_apps():
    # Home, Work, up to 5 favorites and the last 10 destinations, each removable.
    assert "KEY: 'cs.places.v1'" in APP
    assert ".slice(0, 10)" in APP and ".slice(0, 5)" in APP
    assert "Places.noteRecent(c)" in APP
    assert "Places.remove(q.kind, q.c)" in APP
    for label in ("Save as Home", "Save as Work", "Save to favorites"):
        assert label in APP
    assert ".sugg .row.quick .rm" in CSS


def test_reports_snap_to_a_nearby_road_but_keep_the_exact_spot_on_offer():
    assert "openReportForm(await snapForReport(e.latlng), e.latlng)" in APP
    assert "fetch('/api/snap?lat='" in APP
    assert "Use the exact spot" in APP
    assert ".reportform .where" in CSS
