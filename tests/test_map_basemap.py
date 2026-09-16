"""The base-map style is chosen in the Layers pane; nothing floats over
the map for it (the Leaflet layers control drew an empty square and
requested an image that is not shipped)."""

import re
from pathlib import Path

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
ASSIST = (STATIC / "map-assistant.js").read_text(encoding="utf-8")


def test_style_radios_live_in_the_layers_pane_once():
    layers = re.search(r'<section id="pane-layers"[^>]*>(.*?)</section>', HTML, re.S).group(1)
    assert layers.count('id="basemap"') == 1 and 'role="radiogroup"' in layers
    assert HTML.count('id="basemap"') == 1
    assert "<u>Map style</u>" in layers


def test_no_leaflet_layers_control_on_the_map():
    assert "L.control.layers" not in ASSIST
    assert "leaflet-control-layers" not in CSS


def test_four_styles_and_the_saved_choice_survive():
    for name in ("'Smooth'", "'Bright'", "'Outdoors'", "'Terrain'"):
        assert name in ASSIST
    assert "localStorage.getItem('cs-basemap')" in ASSIST
    assert "localStorage.setItem('cs-basemap', name)" in ASSIST
    assert "if (!baseLayers[savedBase]) savedBase = 'Smooth';" in ASSIST
    assert "map.removeLayer(baseOn);" in ASSIST  # one base layer at a time
