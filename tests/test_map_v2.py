"""Map v2 (2026-11): Places with Directions inside, a Google Maps style
route editor (stops, options, compact route rows), a rail that keeps its
width with a More menu, and a close button on every pane. String-level
checks like the other map suites: they pin the wiring a refactor could
silently drop."""

import re
from pathlib import Path

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
CSS = (STATIC / "map.css").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")
ASSIST = (STATIC / "map-assistant.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    body = APP[APP.index(f"function {name}("):]
    return body[:body.index("\n}\n")]


# ── Stops: add, remove, reorder, clear ──────────────────────────────

def test_stop_cap_matches_the_route_endpoint():
    # /api/route takes 2 to 8 locations: a start, a destination and up to
    # six stops between them. The cap and its copy must say the same.
    assert "const MAX_STOPS = 6;" in APP
    src = Path("src/ca_roads_demo/app.py").read_text(encoding="utf-8")
    assert "not 2 <= len(raw) <= 8" in src
    assert "'Up to ' + MAX_STOPS + ' stops on one route'" in APP


def test_add_stop_inserts_a_row_before_the_destination_up_to_the_cap():
    add = _fn("addStopRow")
    assert "if (stops.length >= MAX_STOPS) return null;" in add
    assert "const before = idx < stops.length ? stops[idx].row : toRow;" in add
    assert "dirPts.insertBefore(li, before);" in add
    # Each stop is a real labelled field with its own suggestions.
    assert ("'<div class=\"dirfld\"><label class=\"visually-hidden\" "
            "for=\"stop' + n + '\">Stop</label>'") in add
    assert ("wireAddress('stop' + n, 'stop' + n + 'val', 'stop' + n + 'sugg', false, "
            "() => autoPlan())") in add
    assert "const s = addStopRow(stops.length);" in APP
    # At the cap the button hides and the limit says why.
    sync = _fn("syncDirUi")
    assert "add.hidden = stops.length >= MAX_STOPS;" in sync
    assert "cap.hidden = stops.length < MAX_STOPS;" in sync
    assert 'id="addstop"' in HTML and 'id="stopcap"' in HTML


def test_remove_and_reorder_shift_values_and_replan():
    rm = _fn("removePoint")
    assert "if (fields.length <= 2) { writePoint(fields[i], null); syncDirUi(); return; }" in rm
    assert "dropLastStopRow();" in rm and "autoPlan();" in rm
    mv = _fn("movePoint")
    assert "vals.splice(j, 0, moved);" in mv and "autoPlan();" in mv
    # Remove buttons only show with three or more points, and say which.
    sync = _fn("syncDirUi")
    assert "rm.hidden = !many;" in sync
    assert "rm.setAttribute('aria-label', 'Remove the ' + role);" in sync
    # Reorder by keyboard on the handle, announced.
    assert "if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;" in APP
    assert "'Move the ' + role + '. Use the up and down arrow keys.'" in sync
    assert "dirLive.textContent = 'Moved to position '" in mv


def test_clear_empties_the_points_and_the_line_on_the_map():
    clear = _fn("clearRoute")
    for needle in ("while (stops.length) dropLastStopRow();",
                   "writePoint(fromF, null); writePoint(toF, null);",
                   "layerRoute.clearLayers();",
                   "plannedRoute = null; plannedRoutes = [];",
                   "planSeq += 1;",  # a plan still in flight never lands
                   "document.getElementById('printwrap').hidden = true;",
                   "hideRouteStrip();"):
        assert needle in clear, needle
    assert 'id="clearroutebtn" hidden>Clear route</button>' in HTML
    assert "document.getElementById('clearroutebtn').hidden = !any;" in _fn("syncDirUi")


def test_directions_plan_by_themselves():
    assert 'id="planbtn"' not in HTML
    assert "fromF.onPick = autoPlan;" in APP and "toF.onPick = autoPlan;" in APP
    assert "planTimer = setTimeout(planNow, 150);" in APP
    # The echo lines under each field and the summary sentence are gone.
    assert "val.className = 'val'; val.textContent = '';" in APP
    assert 'id="viachips"' not in HTML and 'id="rhead"' not in HTML


# ── Places and Route are one tool ───────────────────────────────────

def test_places_and_route_are_merged():
    rail = re.search(r'<nav class="rail"[^>]*>(.*?)\n  </nav>', HTML, re.S).group(1)
    assert 'data-tool="route"' not in rail and "<span>Route</span>" not in rail
    assert "const RAIL_OF = { route: 'places' };" in APP
    places = re.search(r'<section id="pane-places"[^>]*>(.*?)\n    </section>', HTML, re.S).group(1)
    assert 'id="direntry"' in places
    plan = re.search(r'<section id="pane-plan"[^>]*>(.*?)\n    </section>', HTML, re.S).group(1)
    assert 'id="rback"' in plan and 'aria-label="Back to your places"' in plan
    assert "setTool('route', { toggle: false, reveal: true });" in _fn("openDirections")
    # A place offers Directions; so does a search result and the find box.
    assert "function openPlaceMenu(btn, c)" in APP
    assert 'id="finddir"' in HTML
    assert "add('Actions', 'Directions', () => openDirections(fromF)" in APP


# ── Every pane has a named close button ─────────────────────────────

def test_every_pane_has_a_named_close_button():
    panes = re.findall(r'<section id="(pane-[a-z]+)" data-tool="([a-z]+)"[^>]*>'
                       r'(.*?)\n    </section>', HTML, re.S)
    assert len(panes) >= 8
    for pid, tool, body in panes:
        if tool == "layers":
            continue  # a popover from the map button, with its own close
        m = re.search(r'<button type="button" class="iconbtn paneclose" '
                      r'aria-label="Close ([^"]+)"', body)
        assert m, pid
        assert m.group(1).strip(), pid
    assert ("document.querySelectorAll('#panel .paneclose')"
            ".forEach((b) => b.addEventListener('click', closePanel));") in APP
    # Escape closes the panel when nothing smaller is open first.
    assert "if (e.key !== 'Escape' || e.defaultPrevented) return;" in APP
    assert ".paneclose { width:32px; height:32px;" in CSS


# ── Live, Ask ───────────────────────────────────────────────────────

def test_live_filters_by_kind_with_counts_and_drive_the_map():
    assert 'id="livefilters" role="group"' in HTML
    assert "function paintLiveFilters(counts)" in APP
    # The checkboxes are the map's layer checkboxes underneath.
    assert "box.dispatchEvent(new Event('change', { bubbles: true }));" in APP
    assert "rows.length + ' in view \\u00b7 worst first'" in APP


def test_ask_has_retry_and_cancels_a_stale_answer():
    assert 'id="askerr" role="alert" hidden' in HTML and 'id="askretry"' in HTML
    assert "const ctl = new AbortController();" in ASSIST
    assert 'enterkeyhint="send"' in HTML
    assert "function askAbout(q)" in APP
    assert 'id="inspask"' in HTML or "inspask" in APP


def test_palette_sends_typed_text_to_ask():
    # Map v2 (2026-11): a question typed in the command palette goes to
    # Ask as the question, by picking "Ask: ..." or by pressing Enter when
    # no command matches (the Ask row leads then, so Enter runs it).
    body = APP[APP.index("function renderPalette() {"):APP.index("function markPalette() {")]
    assert "run: () => askAbout(q) }" in body
    assert ("if (!commands.length && (!palPlaces.length || looksLikeQuestion(q))) "
            "palCmds.unshift(askCmd);") in body
    assert "else if (e.key === 'Enter') { e.preventDefault(); runPalette(palSel); }" in APP
    ask = APP[APP.index("function askAbout(q) {"):]
    ask = ask[:ask.index("\n}\n")]
    assert "setTool('ask', { toggle: false, reveal: true });" in ask
    assert "input.value = q.slice(0, 300);" in ask and "form.requestSubmit();" in ask


def test_along_the_way_lists_every_stop_with_its_mile_and_arrival():
    # Map v2 (2026-11): the strip had only the two ends; each stop on the
    # route is now a row at its mile, numbered as in the editor, with an
    # arrival time from the legs' own times (by distance without them).
    assert "legTimes: trip.legs.map((l) => (l.summary && l.summary.time) || null)," in APP
    assert "plannedRoute.stops = stops.map((s, k) => ({ n: k + 1, f: s.field }))" in APP
    strip = APP[APP.index("function buildRouteStrip("):APP.index("function selectStrip(")]
    assert "const km = along.at(s);" in strip
    assert "meta = 'Stop ' + h.stop.n + ' · arrive about ' + clockTxtMs(h.eta);" in strip
    assert "'<span class=\"rsend stop\" aria-hidden=\"true\">' + h.stop.n + '</span>'" in strip
    # The arrows still step through reported items only.
    assert "const stripHits = () => stripItems.map((x, i) => (x.m ? i : -1))" in APP
    # The count sits on its own line under the label.
    assert '<p class="rspos" id="rspos" aria-live="polite"></p>' in HTML
    assert ".rshead .kicker { margin:0; white-space:nowrap }" in CSS
