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
    for name in ("Light", "Gray", "Dark", "Outdoors", "Terrain"):
        assert f"{name}: " in BASEMAP, name
    assert "localStorage.getItem('cs-basemap')" in ASSIST
    assert "localStorage.setItem('cs-basemap', name)" in ASSIST
    # A saved choice that no longer exists (Smooth, Bright) falls back.
    assert "if (!baseLayers[savedBase]) savedBase = CS_BASEMAP_DEFAULT;" in ASSIST
    assert "map.removeLayer(baseOn);" in ASSIST  # one base layer at a time


def test_the_base_map_is_ours_with_a_fallback():
    """Light, Gray and Dark draw from our own map files; a browser
    without WebGL still gets a map."""
    assert "/api/map/style.json?flavor=" in BASEMAP
    assert "canDrawOwn()" in BASEMAP and "alidade_smooth" in BASEMAP
    for page in ("map.html", "trip.html", "watch.html"):
        text = (STATIC / page).read_text(encoding="utf-8")
        assert "/static/basemap.js" in text, page
        assert "tiles.stadiamaps.com/tiles/" not in text, page
        # Leaflet first, then MapLibre, PMTiles and the bridge, then ours.
        order = [text.index(x) for x in ("vendor/leaflet.js", "vendor/maplibre-gl-csp.js",
                                         "vendor/pmtiles.js", "vendor/leaflet-maplibre-gl.js",
                                         "/static/basemap.js")]
        assert order == sorted(order), page


def test_the_service_worker_leaves_map_files_alone():
    """Byte-range reads cannot go in the Cache API; they pass through."""
    sw = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert "url.pathname.startsWith(MAP_PREFIX)) return;" in sw
