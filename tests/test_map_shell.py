"""Map page shell: an icon rail, one panel, resizable, one control per
job (spec: docs/superpowers/specs/2026-09-16-map-rail-panel-design.md)."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")
ASSIST = (STATIC / "map-assistant.js").read_text(encoding="utf-8")

# Every id the scripts and the other test suites reach for. Renaming any
# of these silently breaks a feature, so the new shell wraps them.
PINNED_IDS = [
    "from", "to", "pickfrom", "pickto", "fromsugg", "tosugg", "fromval",
    # Map v2 (2026-11): planbtn and viachips are gone on purpose. Directions
    # plan by themselves once both ends are set, and stops are rows in the
    # editor (stop1, stop2, ...) instead of chips under it.
    "toval", "departmode", "departat", "printwrap", "routealts",
    "routesum", "printbtn", "exportbtn", "gpxbtn", "kmlbtn",
    "sharebtn", "clearroutebtn", "routeasks-wrap", "routeasks", "stepsdrop",
    "stepssummary", "steps", "routecond", "form", "q", "go", "result",
    "loader", "loadmsg", "loadtime", "status", "chips", "answer", "morebtn",
    "feedback", "filters", "allnone", "trafficlayer", "camvideo",
    "signblank", "k-inc", "k-clo", "k-cc", "k-wf", "k-cam", "k-st",
    "mapcard", "map", "maploading", "maploadingtext", "pickhint",
    "roadinfo", "sysok", "feedsok", "asof", "ver",
]


def _section(tool: str) -> str:
    m = re.search(rf'<section id="[a-z-]+" data-tool="{tool}"[^>]*>(.*?)</section>',
                  HTML, re.S)
    assert m, f"no pane for tool {tool}"
    return m.group(1)


def test_every_pinned_id_survives():
    missing = [i for i in PINNED_IDS if f'id="{i}"' not in HTML]
    assert not missing, missing
    for i in PINNED_IDS:
        assert HTML.count(f'id="{i}"') == 1, i


def test_rail_has_four_primary_tools_and_the_rest_behind_more():
    """2026-11: a slim rail (Places, Route, Live, Ask) that expands to
    labels and the less frequent tools. Round 3 (board #3/#4) moves
    Layers off the rail to a button on the map."""
    # Map v2 (2026-11): Route merged into Places (Directions open inside
    # it), and the rail no longer expands. The everyday tools and the ones
    # people reach for often stay on it at 76px; More opens a menu beside
    # it for the rare ones (Report, API keys, docs, the app).
    rail = re.search(r'<nav class="rail"[^>]*>(.*?)\n  </nav>', HTML, re.S).group(1)
    tools = re.findall(r'data-tool="([a-z]+)"', rail)
    assert tools == ["places", "alerts", "ask", "watch", "about", "settings"]
    primary, also = rail.split('<div class="railalso"')
    assert re.findall(r'data-tool="([a-z]+)"', primary) == ["places", "alerts", "ask", "watch"]
    for name in ("Places", "Live", "Ask", "Watch", "Data", "Plugins", "Commands", "Settings",
                 "More"):
        assert f"<span>{name}</span>" in rail, name
    assert 'id="railtheme">Dark mode</span>' in rail
    for act in ("theme", "palette"):
        assert f'data-act="{act}"' in also
    assert 'href="/marketplace"' in also
    assert rail.rstrip().endswith("</button>") and rail.count('id="railmore"') == 1
    assert 'aria-controls="moremenu"' in rail and 'aria-haspopup="menu"' in rail
    more = HTML[HTML.index('id="moremenu"'):HTML.index('<aside id="panel">')]
    for needle in ('data-act="report"', 'data-tool="keys"', 'href="/developers"', 'href="/app"'):
        assert needle in more, needle
    assert 'id="railexpand"' not in HTML and "cs-rail-wide" not in APP and "railwide" not in CSS


def test_one_pane_per_tool_and_only_places_open_at_load():
    # Map v2 (2026-11): API keys get their own pane (opened from More).
    panes = re.findall(r'<section id="([a-z-]+)" data-tool="([a-z]+)"([^>]*)>', HTML)
    assert [t for _, t, _ in panes] == ["places", "route", "ask", "layers", "watch", "alerts",
                                        "settings", "keys", "about"]
    assert [i for i, t, a in panes if 'class="on"' in a] == ["pane-places"]
    assert "setTool(known ? saved : 'places', { toggle: false })" in APP


def test_layers_open_from_the_map_button_as_one_list():
    # Board #3: a Layers button on the map, with how many are off, opens
    # the one layer list (the Layers section) as a popover.
    assert 'id="filters"' in _section("layers")
    mapcard = HTML[HTML.index('id="mapcard"'):]
    assert 'id="filters"' not in mapcard
    assert 'class="legend"' not in HTML, "the Layers pane lists every color; no second legend"
    assert 'id="layersbtn"' in mapcard and 'aria-controls="pane-layers"' in mapcard
    assert 'id="layersoff"' in mapcard
    assert "function setLayersOpen(open, refocus)" in APP
    assert "#filters input[data-group]:not(:checked)" in APP


def test_counts_moved_into_the_alerts_pane_and_the_band_is_gone():
    alerts = _section("alerts")
    for i in ("k-inc", "k-clo", "k-cc", "k-wf", "k-cam", "k-st"):
        assert f'id="{i}"' in alerts
    before_shell = HTML[:HTML.index('<div class="shell"')]
    assert 'class="kpis"' not in before_shell


def test_exports_fold_into_one_menu_and_share_stays_primary():
    # Map v2 (2026-11): Steps is the one visible route action; Share and the
    # exports sit together behind the route's More button, as a real menu.
    route = _section("route")
    menu = re.search(r'<div class="routemenu" id="routemenu" role="menu"[^>]*>(.*?)</div>',
                     route, re.S).group(1)
    for i in ("sharebtn", "gpxbtn", "kmlbtn", "exportbtn", "printbtn"):
        assert re.search(rf'role="menuitem" id="{i}"', menu), i
    assert 'id="stepsbtn"' in route and 'id="stepsbtn"' not in menu
    assert 'aria-haspopup="menu"' in route and 'aria-controls="routemenu"' in route
    assert 'id="clearroutebtn"' not in menu


def test_legal_text_lives_behind_the_data_tool():
    about = _section("about")
    assert 'class="legalfoot"' in about and "Independent" in about
    assert HTML.count('class="legalfoot"') == 1


def test_no_second_copy_of_any_control():
    # One planner, one question form, one layer list, one legal block.
    # Map v2 (2026-11): no Plan button any more (directions plan by
    # themselves); the one Directions editor is pinned by its point list.
    for needle in ('id="dirpts"', 'id="form"', 'id="filters"', 'class="legalfoot"',
                   'class="rail"', 'id="panelresize"', 'id="layersbtn"', 'id="livepill"'):
        assert HTML.count(needle) == 1, needle


def test_resize_bounds_and_persistence_follow_the_spec():
    # Round 3: the rail is the board's fixed 76px (wider only expanded),
    # so its drag handle and cs-rail-w are gone; the panel still drags.
    assert "--rail-w:76px; --panel-w:360px" in CSS
    assert "'cs-rail-w'" not in APP and 'id="railresize"' not in HTML
    assert re.search(r"'cs-panel-w': \{ min: 300, max: \(\) => Math\.min\(520, "
                     r"Math\.round\(window\.innerWidth \* 0\.4\)\)", APP)
    for key in ("cs-tool", "cs-panel-w"):
        assert key in APP
    assert "panelhidden" not in APP and "paneltab" not in APP and "paneltab" not in CSS
    # Panel handle, inspector handle, and the phone sheet's grab.
    assert 'role="separator"' in HTML and HTML.count('role="separator"') == 3
    assert "ArrowRight" in APP and "ArrowLeft" in APP  # keyboard resize


def test_a_question_opens_the_ask_tool():
    assert "setTool('ask', { toggle: false, reveal: true })" in ASSIST


def test_collapsing_and_selecting_tools_are_one_function():
    assert APP.count("function setTool(") == 1
    assert "aria-pressed" in APP


def test_phone_layout_keeps_the_rail_as_a_row():
    phone = CSS[CSS.index("@media (max-width: 960px)"):]
    assert re.search(r"\.rail \{[^}]*flex-direction:row", phone)
    assert ".resizer { display:none }" in phone
    # On a phone the Layers button is round (board M1).
    assert re.search(r"#layersbtn \{[^}]*border-radius:999px", phone)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_scripts_parse():
    for name in ("map-assistant.js", "map-app.js"):
        r = subprocess.run(["node", "--check", str(STATIC / name)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
