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
    "toval", "planbtn", "departmode", "departat", "printwrap", "routealts",
    "routesum", "viachips", "printbtn", "exportbtn", "gpxbtn", "kmlbtn",
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


def test_rail_has_the_five_tools_plus_data_once_each():
    rail = re.search(r'<nav class="rail"[^>]*>(.*?)</nav>', HTML, re.S).group(1)
    tools = re.findall(r'data-tool="([a-z]+)"', rail)
    assert tools == ["route", "ask", "layers", "watch", "alerts", "about"]
    # Watch is a link to its page until it is embedded; the rest are buttons.
    assert re.search(r'<a class="tool" href="/watch" data-tool="watch"', rail)
    assert rail.count("<button") == 5
    for name in ("Route", "Ask", "Layers", "Watch", "Alerts", "Data"):
        assert f"<span>{name}</span>" in rail


def test_one_pane_per_tool_and_only_route_open_at_load():
    panes = re.findall(r'<section id="([a-z-]+)" data-tool="([a-z]+)"([^>]*)>', HTML)
    assert [t for _, t, _ in panes] == ["route", "ask", "layers", "alerts", "about"]
    assert [i for i, t, a in panes if 'class="on"' in a] == ["pane-plan"]


def test_layers_live_in_the_panel_not_on_the_map():
    assert 'id="filters"' in _section("layers")
    mapcard = HTML[HTML.index('id="mapcard"'):]
    assert 'id="filters"' not in mapcard
    assert 'class="legend"' not in HTML, "the Layers pane lists every color; no second legend"
    assert 'id="layersbtn"' not in HTML and "layersbtn" not in APP


def test_counts_moved_into_the_alerts_pane_and_the_band_is_gone():
    alerts = _section("alerts")
    for i in ("k-inc", "k-clo", "k-cc", "k-wf", "k-cam", "k-st"):
        assert f'id="{i}"' in alerts
    before_shell = HTML[:HTML.index('<div class="shell"')]
    assert 'class="kpis"' not in before_shell


def test_exports_fold_into_one_menu_and_share_stays_primary():
    route = _section("route")
    menu = re.search(r'<details class="sharemenu">(.*?)</details>', route, re.S).group(1)
    for i in ("gpxbtn", "kmlbtn", "exportbtn", "printbtn"):
        assert f'id="{i}"' in menu
    assert 'id="sharebtn" class="pri"' in route and 'id="sharebtn"' not in menu
    assert 'id="clearroutebtn"' not in menu


def test_legal_text_lives_behind_the_data_tool():
    about = _section("about")
    assert 'class="legalfoot"' in about and "Independent" in about
    assert HTML.count('class="legalfoot"') == 1


def test_no_second_copy_of_any_control():
    # One planner, one question form, one layer list, one legal block.
    for needle in ('id="planbtn"', 'id="form"', 'id="filters"', 'class="legalfoot"',
                   'class="rail"', 'id="panelresize"', 'id="railresize"'):
        assert HTML.count(needle) == 1, needle


def test_resize_bounds_and_persistence_follow_the_spec():
    assert "--rail-w:64px; --panel-w:360px" in CSS
    assert re.search(r"'cs-rail-w': \{ min: 56, max: 88", APP)
    assert re.search(r"'cs-panel-w': \{ min: 300, max: \(\) => Math\.min\(520, "
                     r"Math\.round\(window\.innerWidth \* 0\.4\)\)", APP)
    for key in ("cs-tool", "cs-rail-w", "cs-panel-w"):
        assert key in APP
    assert "panelhidden" not in APP and "paneltab" not in APP and "paneltab" not in CSS
    # Rail handle, panel handle, and the phone sheet's grab handle.
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
    assert "layersbtn" not in CSS


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_scripts_parse():
    for name in ("map-assistant.js", "map-app.js"):
        r = subprocess.run(["node", "--check", str(STATIC / name)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
