"""Map shell step 3: the Alerts tool lists what is in view, worst first,
and any popup can open a wider inspector on demand. Popups stay popups."""

import re
from pathlib import Path

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")


def test_inspector_pane_exists_once_and_starts_hidden():
    assert HTML.count('id="inspector"') == 1
    assert re.search(r'<aside class="inspector" id="inspector" hidden', HTML)
    for i in ("insptitle", "inspclose", "inspbody"):
        assert HTML.count(f'id="{i}"') == 1, i


def test_alerts_pane_lists_the_view_under_the_counts():
    alerts = re.search(r'<section id="pane-alerts"[^>]*>(.*?)</section>', HTML, re.S).group(1)
    assert 'id="kpis"' in alerts and 'id="alertlist"' in alerts
    assert alerts.index('id="kpis"') < alerts.index('id="alertlist"')


def test_popups_get_one_inspector_button_at_open_time():
    # Added on popupopen, never inside the builders: they stay untouched.
    assert APP.count("'Show in inspector'") == 1
    assert "box.querySelector('.inspbtn')" in APP  # never twice on one popup
    builders = APP[APP.index("function popupFor(m, g)"):APP.index("function pointMarker")]
    assert "inspbtn" not in builders


def test_dispatch_log_wiring_is_one_function_used_by_both():
    assert APP.count("function wireDispatchLog(el, popup)") == 1
    assert "map.on('popupopen', (e) => wireDispatchLog(e.popup.getElement(), e.popup))" in APP
    assert "wireDispatchLog(inspBody, null)" in APP


def test_inspector_docks_wide_and_overlays_narrow():
    assert "--insp-w:0px" in CSS
    assert ".shell.insp { --insp-gap:6px; --insp-w:var(--insp-user, 340px) }" in CSS
    narrow = CSS[CSS.index("@media (max-width: 1279px)"):]
    assert ".shell.insp { --insp-w:0px; --insp-gap:0px }" in narrow
    assert "position:absolute; right:0; top:0; bottom:0" in narrow
    phone = CSS[CSS.index("@media (max-width: 960px)"):]
    assert ".inspector { position:fixed; left:0; right:0" in phone


def test_alerts_rank_full_closures_first_and_respect_layers():
    sev = re.search(r"const SEVERITY = \{(.*?)\};", APP, re.S).group(1)
    order = re.findall(r"(\w+): (\d)", sev)
    assert order[0] == ("clo_full", "0")
    assert dict(order)["inc_collision"] == "1" and dict(order)["inc_other"] == "5"
    assert "function groupOn(g)" in APP and "input[data-group=" in APP
    assert "function alertRow(m, g)" in APP and "humanize(m.type)" in APP
    assert "map.on('moveend zoomend', scheduleAlerts)" in APP
    assert "const ALERT_CAP = 60;" in APP


def test_alert_row_click_opens_the_same_popup_builder():
    block = APP[APP.index("function refreshAlerts()"):APP.index("function scheduleAlerts()")]
    assert ".setContent(popupFor(m, r.it.g))" in block
    assert "p.__m = m; p.__g = r.it.g;" in block  # so the popup enhancers recognize it


def test_escape_and_close_button_close_the_inspector():
    assert "document.getElementById('inspclose').addEventListener('click', closeInspector)" in APP
    assert "if (e.key === 'Escape') closeInspector();" in APP
