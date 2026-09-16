"""Map shell step 4: on phones the panel is a bottom sheet with three
resting heights over an edge-to-edge map, and the rail is its tab bar."""

import re
from pathlib import Path

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")
ASSIST = (STATIC / "map-assistant.js").read_text(encoding="utf-8")
PHONE = CSS[CSS.index("@media (max-width: 960px) {\n  /* Phone:"):
            CSS.index("/* ── Topbar: two rows")]


def test_one_grab_handle_first_in_the_panel_hidden_on_desktop():
    assert HTML.count('id="sheetgrab"') == 1
    assert re.search(r'<aside id="panel">\s*<div class="grab" id="sheetgrab" '
                     r'role="separator"', HTML)
    assert ".grab { display:none }" in CSS
    assert ".grab { display:block" in PHONE


def test_three_stops_and_the_map_fills_the_screen():
    assert "--sheet-h:84px" in PHONE
    assert ".shell.sheet-half { --sheet-h:44% }" in PHONE
    assert ".shell.sheet-full { --sheet-h:calc(100% - var(--tab-h) - 12px) }" in PHONE
    assert ".map-card { position:absolute; inset:0; height:auto" in PHONE
    assert "56vh" not in CSS and "56dvh" not in CSS


def test_rail_is_the_tab_bar_under_the_sheet():
    assert ".rail { position:absolute; left:0; right:0; bottom:0; z-index:1201;" in PHONE
    assert "flex-direction:row" in PHONE
    assert "bottom:var(--tab-h);\n    height:var(--sheet-h); z-index:1200" in PHONE
    # Leaflet's attribution rides above the sheet instead of under it.
    assert ".map-card .leaflet-bottom { bottom:calc(var(--sheet-h) + var(--tab-h))" in PHONE


def test_sheet_state_is_one_function_and_remembered():
    assert APP.count("function setSheet(state)") == 1
    assert "const SHEET_KEY = 'cs-sheet';" in APP
    assert "const SHEET_STOPS = ['peek', 'half', 'full'];" in APP
    assert "store.set(SHEET_KEY, state)" in APP
    for ev in ("'pointerdown'", "'pointermove'", "'pointerup'", "'pointercancel'"):
        assert f"grabEl.addEventListener({ev}" in APP
    assert "e.key === 'ArrowUp'" in APP and "e.key === 'ArrowDown'" in APP


def test_tab_bar_never_collapses_the_panel_on_a_phone():
    handler = APP[APP.index("railEl.addEventListener('click'"):
                  APP.index("const saved = store.get(TOOL_KEY)")]
    assert "if (isPhone()) {" in handler
    assert "setTool(btn.dataset.tool, { toggle: false });" in handler
    assert "if (same && sheetState !== 'peek') setSheet('peek');" in handler
    assert "if (saved === '' && !isPhone())" in APP


def test_map_first_actions_fold_the_sheet():
    # Alert row, inspector and pick-on-map all need the map visible.
    assert APP.count("if (isPhone()) setSheet('peek');") == 2  # inspector, pick on map
    assert "map.on('popupopen', (e) => {\n  if (!isPhone()) return;\n  setSheet('peek');" in APP
    assert "map.once('moveend', open); map.setView(at, z);" in APP
    assert "setTool('ask', { toggle: false, reveal: true })" in ASSIST
    assert "if (opts && opts.reveal && isPhone() && sheetState === 'peek') setSheet('half');" in APP
