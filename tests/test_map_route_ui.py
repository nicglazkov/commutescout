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
    # Map v2 (2026-11): the five preset pills became quiet Options, Google
    # Maps style: Route by (Fastest or Shortest) and Avoid (highways, tolls,
    # chain controls) as real checkboxes, so they combine. Same five choices.
    plan = re.search(r'<section id="pane-plan"[^>]*>(.*?)</section>', HTML, re.S).group(1)
    opts = re.search(r'<div class="diropts" id="diropts"[^>]*>(.*?)\n      </div>', plan, re.S)
    assert opts, "options live in the Directions pane"
    assert re.findall(r'name="routeby" value="([a-z]+)"', opts.group(1)) == ["fastest", "shortest"]
    assert re.findall(r'data-avoid="([a-z]+)"', opts.group(1)) == ["highways", "tolls", "chains"]
    assert 'id="optsbtn"' in plan and 'aria-controls="diropts"' in plan
    assert HTML.count('id="diropts"') == 1 and HTML.count('id="plannote"') == 1


def test_routing_goes_through_the_server_only():
    """The server holds the routing key and the daily budget; the page
    never routes around a spent budget by calling the router itself."""
    # Map v2 (2026-11): the server takes an avoid list next to the preset.
    assert "async function serverDirections(points, preset, avoid)" in APP
    assert "fetch('/api/route'" in APP
    assert "valhallaDirections" not in APP and "stadiamaps.com" not in APP
    fallback = APP[APP.index("async function anyDirections(points)"):]
    fallback = fallback[:fallback.index("\n}\n") + 3]
    assert "serverDirections(points, routeBy(), routeAvoid())" in fallback


def test_alternatives_carry_a_hassle_line_and_presets_replan():
    # Map v2 (2026-11): routes are compact rows (time big, distance and via
    # small) with a badge for what is on them; changing an option replans
    # by itself through autoPlan, with no Plan button.
    assert "'<span class=\"altbadge warn\">'" in APP
    assert "'<span class=\"altbadge ok\">Clear right now</span>'" in APP
    assert "optsBox.addEventListener('change', () => {" in APP
    assert "note.hidden = !planNote;" in APP
    assert ".altrow.on::before" in CSS and ".altbadge.warn" in CSS


def test_conditions_list_reads_marker_data_not_layer_groups():
    block = APP[APP.index("function renderRouteConditions"):APP.index("function buildRouteAsks")]
    assert "ambient[g].eachLayer" not in block
    assert "for (const it of (items[g] || []))" in block
    assert "popEl.innerHTML = popupFor(m, g);" in block


def test_eta_is_reweighted_by_measured_speeds():
    # Map v2 (2026-11): no separate ETA line; the traffic time lands in the
    # selected route row (time big, "+N min traffic" beside the distance).
    assert 'id="routeeta"' not in HTML
    assert "plannedRoute.trafficMins = Math.max(free, adjusted);" in APP
    assert "' · +' + slower + ' min traffic'" in APP
    assert "function showTrafficEta(route, pts, bounds, flow)" in APP
    assert "showTrafficEta(route, pts, bounds, flow);" in APP
    # Only slower stretches lengthen the trip; a fast stretch never shortens it.
    assert "(f && f.ratio && f.ratio < 1) ? len / Math.max(0.25, f.ratio) : len" in APP
    assert "if (!total || sampled / total < 0.5) return;" in APP
