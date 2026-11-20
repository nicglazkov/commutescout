"""Map sidebar and details: Your places as the base view, the expandable
rail, the details pane (Basic | Advanced, lazy AI line), the route strip
and the command palette. String-level checks, like the other map suites:
they pin the wiring a refactor could silently drop."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ca_roads_demo.watch import merge_places

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")


def test_places_is_the_base_view():
    assert re.search(r'<section[^>]*id="pane-places"[^>]*class="[^"]*\bon\b', HTML) or \
        re.search(r'<section[^>]*class="[^"]*\bon\b[^"]*"[^>]*id="pane-places"', HTML)
    for el in ("ptiles", "precent", "plive", "pchips", "placesedit"):
        assert f'id="{el}"' in HTML, el
    # Saved places stay in this browser, and the page says so.
    assert "Saved in this browser. Sign in to sync with the app and your AI assistant." in HTML
    assert "setTool(known ? saved : 'places'" in APP
    # Live-in-view refreshes with the alerts, not on its own timer per pan.
    assert "refreshAlerts(); refreshPlacesLive();" in APP


def test_set_tool_reaches_late_code_by_event_not_call():
    # setTool runs at boot, before later const declarations exist.
    assert "new CustomEvent('cs-tool'" in APP
    assert "addEventListener('cs-tool'" in APP


def test_rail_expands_and_remembers_on_desktop_only():
    assert 'id="railexpand"' in HTML and 'aria-controls="railadv"' in HTML
    assert "RAIL_WIDE_KEY" in APP and "if (!isPhone()) store.set(RAIL_WIDE_KEY" in APP
    # The phone menu escapes the rail's clipping.
    assert "overflow:visible" in CSS.split(".shell.railwide .rail { padding:4px 6px")[1][:80]


def test_details_pane_has_two_modes_and_a_lazy_overview():
    assert 'role="tablist"' in HTML and 'id="insptab-basic"' in HTML and 'id="insptab-adv"' in HTML
    # The AI line sits above the mode switch and never blocks the pane.
    assert HTML.index('id="inspai"') < HTML.index('id="inspmode"')
    assert "fetch('/api/overview'" in APP
    assert "if (gen !== inspGen) return;" in APP  # a stale answer never lands
    assert "if (!text) { inspAi.hidden = true; return; }" in APP  # hidden on error
    assert "overviewCache.size > 200" in APP  # bounded
    assert "INSP_MODE_KEY = 'cs-insp-mode'" in APP or "INSP_MODE_KEY='cs-insp-mode'" in APP


def test_advanced_view_shows_timing_ids_fields_and_copyable_json():
    body = APP.split("function advancedView(m, g) {", 1)[1][:6000]
    for label in ("Timing", "Source and IDs", "Every other field", "Copy JSON"):
        assert label in body, label
    assert "snapPublished" in body  # data_as_of comes from the payload
    assert "type: 'application/json'" in body


def test_popup_is_a_peek_with_one_details_button():
    assert "classList.add('peek')" in APP
    assert "btn.className = 'detbtn inspbtn'" in APP


def test_route_strip_steps_by_mile():
    # Board #11: the strip is a vertical list in the route panel, so the
    # floating card and its reopen pill (rscard, rsopen) are gone.
    for el in ("rstrip", "rsprev", "rsnext", "rstrack", "rslegend", "rhead", "rleave"):
        assert f'id="{el}"' in HTML, el
    before, after = HTML.split('id="rstrack"', 1)
    assert 'role="listbox"' in before[-200:] + after[:200]
    assert "buildRouteStrip(latlngs, along)" in APP
    assert "hideRouteStrip()" in APP.split("function clearRoute", 1)[1][:1500]
    keys = APP.split("rstrack.addEventListener('keydown'", 1)[1][:700]
    for key in ("ArrowRight: 1", "ArrowLeft: -1", "'Home'", "'End'", "'Enter'"):
        assert key in keys, key
    assert 'id="rscard"' not in HTML and 'id="rsopen"' not in HTML
    route = HTML[HTML.index('<section id="pane-plan"'):]
    assert route.index('id="rstrip"') < route.index('id="clearroutebtn"')


def test_command_palette_is_a_modal_combobox_on_cmd_k():
    assert 'id="cpal"' in HTML and 'aria-modal="true"' in HTML and 'role="combobox"' in HTML
    assert "(e.metaKey || e.ctrlKey)" in APP and "e.key.toLowerCase() === 'k'" in APP
    assert "IS_MAC ? '⌘K' : 'Ctrl K'" in APP
    assert "aria-activedescendant" in APP
    # Esc closes the palette and nothing behind it.
    assert "closePalette(true)" in APP and "e.stopPropagation()" in APP
    cmds = APP.split("function paletteCommands() {", 1)[1][:6000]
    for group in ("Places", "Actions", "Layers", "Map style", "Theme"):
        assert f"'{group}'" in cmds, group


def test_dark_theme_and_reduced_motion():
    assert ':root[data-theme="dark"]' in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    early = (STATIC / "basemap-early.js").read_text(encoding="utf-8")
    assert "cs-theme" in early and "root.dataset.theme = theme" in early


# ── Your places follow the account ───────────────────────────────

def test_places_sync_with_the_account_like_the_apps():
    sync = APP.split("const PlaceSync = {", 1)[1][:3000]
    assert "fetch('/api/me/places', { method: 'PUT'" in sync
    assert "Authorization: 'Bearer ' + token" in sync
    # Sign-in: one merging PUT of the local list, the merged list adopted.
    assert "await this.put({ places: Places.toWire(Places.load()) })" in sync
    # A removal replaces only once this browser holds the whole list.
    assert "if (this.removal && this.synced) body.replace = true;" in sync
    assert "setTimeout(" in sync  # pushes are debounced
    # Removals are flagged as such; adds and recents merge.
    assert "this.save(p, true);" in APP.split("remove(kind, c) {", 1)[1][:400]
    assert "PlaceSync.changed(!!removal)" in APP
    # Sign-in state comes from the watch module, which owns Firebase.
    watch = (STATIC / "watch-app.js").read_text(encoding="utf-8")
    assert "new CustomEvent('cs-auth', { detail: { signedIn: !!u } })" in watch
    assert "document.addEventListener('cs-auth'" in APP
    # A browser that was signed in loads sign-in on its own when idle.
    assert "if (store.get(PLACES_ACCT_KEY) === '1')" in APP


def test_places_note_says_where_the_list_lives():
    assert "'Synced with your account.'" in APP
    assert "'Saved in this browser. Sign in to sync with the app and your AI assistant.'" in APP
    assert 'id="psync"' in HTML and 'id="psignin"' in HTML
    assert "document.getElementById('psignin').hidden = PlaceSync.signedIn;" in APP


def _places_js() -> str:
    start = APP.index("const PLACES_CAP = 20;")
    end = APP.index("// Account sync, the same protocol")
    return APP[start:end]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_wire_shape_round_trips_through_the_account_merge():
    """The map's local list goes out in the shape watch.merge_places
    keeps, and the merged list comes back into the same local shape."""
    local = {"home": {"name": "Home St", "lat": 38.5, "lon": -121.4, "at": 1_700_000_000_000},
             "work": None,
             "saved": [{"id": "s1", "name": "Gym", "lat": 38.6, "lon": -121.3,
                        "at": 1_700_000_100_000}],
             "recents": [{"id": "r1", "name": "Lodi, CA", "lat": 38.13, "lon": -121.27,
                          "at": 1_700_000_200_000}]}
    script = (
        "const mem = {}; const store = { get: (k) => mem[k], set: (k, v) => { mem[k] = v; } };"
        "const PlaceSync = { changed() {} }; const window = {};" + _places_js() +
        f"store.set(Places.KEY, {json.dumps(json.dumps(local))});"
        "const wire = Places.toWire(Places.load());"
        "const back = (list) => Places.fromWire(list);"
        "const fs = require('fs'); const input = JSON.parse(fs.readFileSync(0, 'utf8'));"
        "if (input.list) { console.log(JSON.stringify(back(input.list))); }"
        "else { console.log(JSON.stringify(wire)); }"
    )

    def run(stdin: str):
        r = subprocess.run(["node", "-e", script], input=stdin, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    wire = run("{}")
    assert {p["kind"] for p in wire} == {"home", "saved", "recent"}
    home = next(p for p in wire if p["kind"] == "home")
    assert home["id"] and home["used_at"] == 1_700_000_000  # seconds, as the apps send
    # The app saved Work; the account merges both lists.
    app_work = {"id": "w-app", "kind": "work", "name": "Office", "lat": 38.58, "lon": -121.49,
                "used_at": 1_700_000_300}
    merged = merge_places([app_work], wire)
    assert len(merged) == 4
    back = run(json.dumps({"list": merged}))
    assert back["home"]["name"] == "Home St" and back["work"]["name"] == "Office"
    assert back["work"]["at"] == 1_700_000_300_000
    assert [r["id"] for r in back["saved"]] == ["s1"]
    assert [r["id"] for r in back["recents"]] == ["r1"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_sign_out_clears_the_list_and_offline_saves_merge_on_sign_in():
    """Like the apps: signing out drops the account's places from this
    browser; places saved while signed out go up on the next sign-in."""
    start = APP.index("const PLACES_CAP = 20;")
    end = APP.index("function wireAddress(")
    script = (
        "const mem = {}; const store = { get: (k) => mem[k], set: (k, v) => { mem[k] = v; } };"
        "const window = {}; const loadWatch = () => {};"
        "class CustomEvent { constructor(t) { this.type = t; } }"
        "const document = { addEventListener() {}, dispatchEvent() {} };"
        "const sent = []; let fetch;" + APP[start:end] +
        """
        (async () => {
          const out = {};
          window.csAuth = { token: async () => 'tok' };
          fetch = async (u, o) => { const b = JSON.parse(o.body); sent.push(b);
            return { ok: true, json: async () => ({ places: b.places }) }; };
          // Signed out from the start: a save stays local, nothing is sent.
          PlaceSync.setSignedIn(false);
          Places.set('home', { name: 'Offline Home', lat: 38.5, lon: -121.4 });
          out.keptSignedOut = !!Places.load().home;
          out.sentWhileOut = sent.length;
          // Sign in: the offline save goes up in one merging PUT.
          PlaceSync.setSignedIn(true);
          await new Promise((r) => setTimeout(r, 20));
          out.firstPut = sent[0] && sent[0].places.map((p) => p.kind + ':' + p.name);
          out.firstReplace = !!(sent[0] && sent[0].replace);
          out.acct = store.get(PLACES_ACCT_KEY);
          // Sign out: the list and the flag are gone, nothing pushed.
          const before = sent.length;
          PlaceSync.setSignedIn(false);
          out.afterOut = Places.load();
          out.acctAfter = store.get(PLACES_ACCT_KEY);
          out.pushedOnOut = sent.length - before;
          console.log(JSON.stringify(out));
        })();
        """
    )
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["keptSignedOut"] and out["sentWhileOut"] == 0
    assert out["firstPut"] == ["home:Offline Home"] and out["firstReplace"] is False
    assert out["acct"] == "1"
    assert out["afterOut"] == {"home": None, "work": None, "saved": [], "recents": []}
    assert out["acctAfter"] == "" and out["pushedOnOut"] == 0
