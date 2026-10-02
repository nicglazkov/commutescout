"""Plugin alerts are told apart on the map: a badge whose picture is the
kind of alert and whose color is the plugin, one switch per plugin in
Layers, and a filter between official sources and plugins."""

from pathlib import Path

from ca_roads import flare

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")
BADGES = (STATIC / "plugin-badges.js").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")


def test_the_badge_script_loads_before_the_map_code():
    assert HTML.index("/static/plugin-badges.js") < HTML.index("/static/map-app.js")


def test_every_flare_kind_gets_a_picture():
    """A kind with no category would draw as the fallback dot; that is
    only right for the two kinds that really are 'other'."""
    prefixes = ("POLICE", "CRASH", "CAMERA", "JAM", "WEATHER", "ROAD_CLOSED",
                "LANE_CLOSED", "RAMP_CLOSED", "CHAINS", "HAZARD")
    for p in prefixes:
        assert f"'{p}" in BADGES, p
    uncategorized = sorted(k for k in flare.KINDS if not k.startswith(prefixes))
    assert uncategorized == ["MAP_ISSUE", "OTHER"]
    for cat in ("police", "crash", "hazard", "camera", "jam", "weather", "closed", "chains",
                "other"):
        assert f"\n    {cat}: '" in BADGES, cat


def test_plugins_are_asked_for_at_every_zoom_and_shrink_when_far():
    """The server decides what a view gets (a shared plugin's cameras at
    any zoom, a community plugin's alerts only up close); the page no
    longer refuses to ask."""
    assert "PLUGIN_VIEW_MAX_DEG" not in APP
    assert "el.classList.toggle('pz-low', z < 8)" in APP
    assert ".pz-low .pbadge-pin .pbadge svg { display:none }" in CSS


def test_plugin_alerts_are_badges_and_never_gpu_dots():
    assert "icon: csPlugin.icon(m)" in APP
    assert "if (g === 'plugin') continue;" in APP          # kept out of the dot layer
    assert "cullPolysOnly(), cullPlugins(), GL.rebuild()" in APP
    assert ".pbadge" in CSS


def test_the_popup_leads_with_the_plugin():
    assert "v2(csPlugin.color(csPlugin.sourceId(m)), esc(m.source || 'Plugin')," in APP


def test_layers_has_one_switch_per_plugin_sharing_the_marketplace_key():
    assert 'id="pluginlist"' in HTML
    assert "data-plugin=" in APP
    # The same key the marketplace's Install button writes.
    assert "localStorage.setItem('cs.plugins.off', off.join(','))" in APP
    # Set up before the first fetch can call it.
    assert APP.index("const pluginRows = new Map()") < APP.index("async function refreshPlugins()")


def test_official_or_plugins_filter_drives_the_same_checkboxes():
    assert 'id="srcfilter"' in HTML
    for value in ("all", "official", "plugins"):
        assert f'name="srcfilter" value="{value}"' in HTML
    assert "box.dispatchEvent(new Event('change'))" in APP
