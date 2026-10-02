"""map.html links its stylesheet and scripts with a content stamp, so a
deploy never pairs new HTML with an hour-old cached script."""

import re
from pathlib import Path

from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app

STATIC = Path("src/ca_roads_demo/static")


def test_map_html_has_no_inline_style_or_app_script():
    html = (STATIC / "map.html").read_text(encoding="utf-8")
    assert "<style>" not in html
    inline = [s for s in re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", html)
              if "application/ld+json" not in s]
    assert inline == [], inline
    for name in ("map.css", "map-assistant.js", "map-app.js"):
        assert f"/static/{name}?v=__ASSET_V__" in html


def test_served_page_stamps_assets_by_content(monkeypatch):
    client = TestClient(demo_app.app)
    html = client.get("/map").text
    stamps = set(re.findall(r'/static/map[a-z-]*\.(?:css|js)\?v=([0-9a-f]{10})', html))
    assert len(stamps) == 1, stamps
    assert "__ASSET_V__" not in html
    assert client.get("/map").headers["Cache-Control"] == "no-cache"
    # The stamp follows the bytes of every file the page stamps, read
    # from the page itself, and the security policy the worker obeys.
    demo_app._INDEX_CACHE.clear()
    monkeypatch.setattr(demo_app.SecurityHeaders, "CSP", demo_app.SecurityHeaders.CSP + "; x")
    html2 = client.get("/map").text
    assert set(re.findall(r'\?v=([0-9a-f]{10})', html2)) != stamps


def test_every_stamped_file_is_in_the_stamp(tmp_path, monkeypatch):
    """A hand-kept list once missed basemap.js: a release that changed
    only that file kept its address, and the CDN kept the old copy."""
    for page in ("map.html", "watch.html"):
        (tmp_path / page).write_text((STATIC / page).read_text(encoding="utf-8"), encoding="utf-8")
    names = set(demo_app._ASSET_REF.findall((STATIC / "map.html").read_text(encoding="utf-8")))
    assert {"basemap.js", "basemap-early.js", "plugin-badges.js", "map-app.js",
            "vendor/maplibre-gl-csp-worker.js"} <= names
    watch = (STATIC / "watch.html").read_text(encoding="utf-8")
    for n in names | set(demo_app._ASSET_REF.findall(watch)):
        (tmp_path / n).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / n).write_bytes((STATIC / n).read_bytes())
    monkeypatch.setattr(demo_app, "STATIC_DIR", tmp_path)
    before = demo_app._stamped_template("map.html", {})
    (tmp_path / "basemap.js").write_text("// changed", encoding="utf-8")
    after = demo_app._stamped_template("map.html", {})
    stamp = lambda text: re.search(r"basemap\.js\?v=([0-9a-f]{10})", text).group(1)  # noqa: E731
    assert stamp(before) != stamp(after)


def test_assets_are_served_and_not_blocked():
    client = TestClient(demo_app.app)
    for name, ctype in (("map.css", "text/css"), ("map-assistant.js", "javascript"),
                        ("map-app.js", "javascript")):
        r = client.get(f"/static/{name}?v=abc")
        assert r.status_code == 200 and ctype in r.headers["content-type"], name
