"""The planner asks the server first (closure-aware, ranked), falls back
to plain routing, and offers one-tap presets plus a hassle line per
alternative."""

import re
from pathlib import Path

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")


def test_presets_are_one_group_of_five_in_the_planner():
    plan = re.search(r'<section id="pane-plan"[^>]*>(.*?)</section>', HTML, re.S).group(1)
    group = re.search(r'<div class="routepresets" id="routepresets"[^>]*>(.*?)</div>', plan, re.S)
    assert group, "presets live in the Route pane"
    presets = re.findall(r'data-preset="([a-z_]+)"', group.group(1))
    assert presets == ["fastest", "no_highways", "no_tolls", "shortest", "avoid_chains"]
    assert group.group(1).count('class="on"') == 1
    assert HTML.count('id="routepresets"') == 1 and HTML.count('id="plannote"') == 1


def test_server_first_then_plain_routing():
    assert "async function serverDirections(points, preset)" in APP
    assert "fetch('/api/route'" in APP
    fallback = APP[APP.index("async function anyDirections(points)"):]
    fallback = fallback[:fallback.index("}\n", fallback.index("valhallaDirections(points)")) + 2]
    assert "serverDirections(points, routePreset)" in fallback
    assert "return await valhallaDirections(points)" in fallback


def test_alternatives_carry_a_hassle_line_and_presets_replan():
    assert "'On it: ' + r.hassles.map((h) => h.label).join(', ')" in APP
    assert "'Clear right now'" in APP
    assert "routePreset = btn.dataset.preset;" in APP
    assert "if (lastEnds) await replanVias();" in APP
    assert "note.hidden = !planNote;" in APP
    assert ".routepresets button.on" in CSS and ".routealts button em.warn" in CSS


def test_conditions_list_reads_marker_data_not_layer_groups():
    block = APP[APP.index("function renderRouteConditions"):APP.index("function buildRouteAsks")]
    assert "ambient[g].eachLayer" not in block
    assert "for (const it of (items[g] || []))" in block
    assert "popEl.innerHTML = popupFor(m, g);" in block


def test_eta_is_reweighted_by_measured_speeds():
    assert HTML.count('id="routeeta"') == 1
    assert "function showTrafficEta(route, pts, bounds, flow)" in APP
    assert "showTrafficEta(route, pts, bounds, flow);" in APP
    # Only slower stretches lengthen the trip; a fast stretch never shortens it.
    assert "(f && f.ratio && f.ratio < 1) ? len / Math.max(0.25, f.ratio) : len" in APP
    assert "if (!total || sampled / total < 0.5) { box.hidden = true; return; }" in APP
