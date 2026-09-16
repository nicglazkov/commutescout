"""Map shell step 5: the Watch tool is the /watch flow embedded in the map
page. One module and one stylesheet serve both; the map page loads them
the first time the tool opens."""

import re
from pathlib import Path

from starlette.testclient import TestClient

import ca_roads_demo.app as demo_app

STATIC = Path("src/ca_roads_demo/static")
HTML = (STATIC / "map.html").read_text(encoding="utf-8")
APP = (STATIC / "map-app.js").read_text(encoding="utf-8")
WATCH_HTML = (STATIC / "watch.html").read_text(encoding="utf-8")
WATCH_JS = (STATIC / "watch-app.js").read_text(encoding="utf-8")
WATCH_CSS = (STATIC / "watch.css").read_text(encoding="utf-8")

# Every id the watch module reaches for, in both hosts.
WATCH_IDS = [
    "who", "signin", "googlebtn", "email", "emailbtn", "signinmsg", "gate",
    "gatetext", "code", "redeembtn", "gatemsg", "appzone", "mode-circle",
    "mode-polygon", "mode-route", "shapehint", "polytools", "undopt",
    "clearpts", "routerow", "rw-from", "rw-to", "rw-preview", "rw-buffer",
    "rw-bufferlabel", "radiusrow", "radius", "radiuslabel", "wname",
    "ch-push", "emailchan", "ch-email", "createbtn", "canceledit",
    "createmsg", "wcount", "usagefill", "wlist", "listmsg", "notifbtn",
    "testbtn", "devmsg", "deleteacct", "acctmsg",
]


def test_the_watch_pane_carries_every_id_the_module_uses_once():
    pane = re.search(r'<section id="pane-watch"[^>]*>(.*?)\n    </section>', HTML, re.S).group(1)
    for i in WATCH_IDS:
        assert pane.count(f'id="{i}"') == 1, i
        assert HTML.count(f'id="{i}"') == 1, i
        assert WATCH_HTML.count(f'id="{i}"') == 1, i
    assert 'id="wmap"' not in HTML  # the live map is the watch map here


def test_watch_is_a_rail_tool_with_a_pane_not_a_link():
    rail = re.search(r'<nav class="rail"[^>]*>(.*?)</nav>', HTML, re.S).group(1)
    assert re.search(r'<button type="button" class="tool" data-tool="watch"', rail)
    assert 'href="/watch"' not in rail
    assert re.search(r'<section id="pane-watch" data-tool="watch" class="watch" '
                     r'data-src="/static/watch-app\.js\?v=__ASSET_V__"', HTML)


def test_one_module_serves_both_pages():
    assert "export async function initWatch(opts)" in WATCH_JS
    assert WATCH_JS.count("function renderWatches()") == 1
    assert "function renderWatches" not in WATCH_HTML
    assert "from '/static/watch-app.js?v=__ASSET_V__'" in WATCH_HTML
    assert "initWatch({ map })" in WATCH_HTML
    # Drawing clicks count only while the tool is open on the map page.
    assert "if (!active()) return;" in WATCH_JS
    assert "history.replaceState(null, '', location.pathname)" in WATCH_JS


def test_map_page_loads_the_tool_on_first_use():
    assert "function showWatch(on)" in APP
    assert "import(pane.dataset.src)" in APP
    assert "showWatch(name === 'watch' && !collapsing);" in APP
    assert "mod.initWatch({ map, visible: false," in APP


def test_watch_styles_are_scoped_and_shared():
    assert '<link rel="stylesheet" href="/static/watch.css?v=__ASSET_V__">' in HTML
    assert '<link rel="stylesheet" href="/static/watch.css?v=__ASSET_V__">' in WATCH_HTML
    assert '<main class="watch">' in WATCH_HTML
    rules = re.findall(r"^([^@\s/][^{]*)\{", WATCH_CSS, re.M)
    unscoped = [r.strip() for r in rules if not r.startswith(".watch")
                and not r.startswith((".vhandle", ".mhandle"))]
    assert not unscoped, unscoped
    # The component rules left the page for the stylesheet.
    for needle in (".card { background", ".stepblock {", ".witem {", ".modes button"):
        assert needle not in WATCH_HTML, needle


def test_both_pages_stamp_the_shared_assets():
    client = TestClient(demo_app.app)
    for path in ("/map", "/watch"):
        r = client.get(path)
        assert r.status_code == 200
        assert "__ASSET_V__" not in r.text, path
        assert r.headers["Cache-Control"] == "no-cache"
        assert re.search(r"/static/watch-app\.js\?v=[0-9a-f]{10}", r.text), path
        assert re.search(r"/static/watch\.css\?v=[0-9a-f]{10}", r.text), path
    for name in ("watch.css", "watch-app.js"):
        assert client.get(f"/static/{name}?v=abc").status_code == 200
