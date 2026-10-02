"""The base-map style is chosen in the Layers pane; nothing floats over
the map for it (the Leaflet layers control drew an empty square and
requested an image that is not shipped)."""

import re
from pathlib import Path

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
ASSIST = (STATIC / "map-assistant.js").read_text(encoding="utf-8")
BASEMAP = (STATIC / "basemap.js").read_text(encoding="utf-8")


def test_style_radios_live_in_the_layers_pane_once():
    layers = re.search(r'<section id="pane-layers"[^>]*>(.*?)</section>', HTML, re.S).group(1)
    assert layers.count('id="basemap"') == 1 and 'role="radiogroup"' in layers
    assert HTML.count('id="basemap"') == 1
    assert "<u>Map style</u>" in layers


def test_no_leaflet_layers_control_on_the_map():
    assert "L.control.layers" not in ASSIST
    assert "leaflet-control-layers" not in CSS


def test_the_styles_and_the_saved_choice_survive():
    for name in ("Positron", "Bright", "Slate", "Gray", "Dark"):
        assert f"{name}: " in BASEMAP, name
    assert "CS_BASEMAP_DEFAULT = 'Positron'" in BASEMAP
    # The picker shows a picture of each style, not just its name.
    assert "csBasemapThumb(name)" in ASSIST
    assert "localStorage.getItem('cs-basemap')" in ASSIST
    assert "localStorage.setItem('cs-basemap', name)" in ASSIST
    # A saved choice that is no longer offered (Smooth, Light) falls back.
    assert "if (!baseLayers[savedBase]) savedBase = CS_BASEMAP_DEFAULT;" in ASSIST
    assert "map.removeLayer(baseOn);" in ASSIST  # one base layer at a time


def test_the_base_map_is_ours_with_a_fallback():
    """Every style comes from the server's style endpoint; a browser
    without WebGL still gets a map."""
    assert "/api/map/style.json?flavor=" in BASEMAP
    assert "canDrawOwn()" in BASEMAP and "alidade_smooth" in BASEMAP
    for page in ("map.html", "trip.html", "watch.html"):
        text = (STATIC / page).read_text(encoding="utf-8")
        assert "/static/basemap.js" in text, page
        assert "tiles.stadiamaps.com/tiles/" not in text, page
        # Leaflet first, then MapLibre, PMTiles and the bridge, then ours.
        order = [text.index('<script src="/static/' + x) for x in (
            "vendor/leaflet.js", "vendor/maplibre-gl-csp.js", "vendor/pmtiles.js",
            "vendor/leaflet-maplibre-gl.js", "basemap.js")]
        assert order == sorted(order), page


def test_the_service_worker_leaves_map_files_alone():
    """Byte-range reads cannot go in the Cache API; they pass through."""
    sw = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert "url.pathname.startsWith(MAP_PREFIX)) return;" in sw


def test_the_worker_address_changes_with_every_deploy():
    """A worker obeys the security policy sent with its own file. Under a
    fixed address that file, and so that policy, stayed cached for a week
    at the CDN and in browsers: a new tile host was allowed on the page
    and refused in the worker, and the default map drew nothing."""
    assert "maplibre-gl-csp-worker.js?v=' + REV" in BASEMAP
    assert "document.currentScript.src" in BASEMAP
    html = (STATIC / "map.html").read_text(encoding="utf-8")
    assert '/static/basemap.js?v=__ASSET_V__' in html
    # The preload names the same address, or it fetches the worker twice.
    assert 'as="worker" href="/static/vendor/maplibre-gl-csp-worker.js?v=__ASSET_V__"' in html


def test_the_style_is_asked_for_before_the_map_code_loads():
    html = (STATIC / "map.html").read_text(encoding="utf-8")
    head = html[:html.index("</head>")]
    assert '<script src="/static/basemap-early.js?v=__ASSET_V__"></script>' in head
    assert 'rel="preconnect" href="https://tiles.openfreemap.org"' in head
    early = (STATIC / "basemap-early.js").read_text(encoding="utf-8")
    assert "link.as = 'fetch'" in early and "/api/map/style.json?flavor=" in early
    # The names the early script maps must be the picker's.
    for name in ("Positron", "Bright", "Slate", "Gray", "Dark"):
        assert f"{name}: '" in early, name
