"""Map shell: the spec's remaining pieces. The inspector resizes between
300 and 480px and carries an actions row; route questions live in Ask;
the Watch tool can start from a marker."""

import re
from pathlib import Path

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")
WATCH_JS = (STATIC / "watch-app.js").read_text(encoding="utf-8")


def test_inspector_has_its_own_handle_with_spec_bounds():
    assert HTML.count('id="inspresize"') == 1
    assert re.search(r'id="inspresize" role="separator"[^>]*hidden>', HTML)
    assert "'cs-insp-w': { min: 300, max: 480, prop: '--insp-user' }" in APP
    assert "wireResizer('inspresize', 'cs-insp-w'," in APP
    # The user's width applies only while the pane is open.
    assert ".shell.insp { --insp-gap:6px; --insp-w:var(--insp-user, 340px) }" in CSS
    narrow = CSS[CSS.index("@media (max-width: 1279px)"):]
    assert "#inspresize { display:none }" in narrow


def test_inspector_actions_share_only_what_a_focus_link_can_find():
    assert "function inspectorActions(m, g)" in APP
    assert "'/map?focus=' + m.lat.toFixed(5) + ',' +" in APP
    assert "function focusKind(g)" in APP and "FOCUS_GROUPS[k].includes(g)" in APP
    assert "watch.textContent = 'Watch this stretch';" in APP
    assert "w.watchHere(m.lat, m.lon)" in APP
    assert "inspBody.appendChild(inspectorActions(m, g));" in APP


def test_watch_module_accepts_a_center_from_the_map():
    assert "function watchHere(lat, lon)" in WATCH_JS
    assert "if (!pendingCenter || !me || me.status !== 'approved') return;" in WATCH_JS
    assert WATCH_JS.count("applyPending();") == 2  # on request, and once approved
    assert "return { setVisible, refresh, reloadWatches, watchHere };" in WATCH_JS


def test_route_questions_live_in_ask_hidden_until_a_route_exists():
    ask = re.search(r'<section id="pane-ask"[^>]*>(.*?)</section>', HTML, re.S).group(1)
    plan = re.search(r'<section id="pane-plan"[^>]*>(.*?)</section>', HTML, re.S).group(1)
    assert 'id="routeasks-wrap" style="display:none"' in ask
    assert "routeasks" not in plan
    assert HTML.count('id="routeasks"') == 1
    assert "Deepest detail in California" not in HTML
