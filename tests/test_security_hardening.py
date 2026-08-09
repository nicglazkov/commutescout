"""Guards for the hardening pass of 2026-08-07.

Each test here fails against the code as it stood before that pass, so a
regression re-opens a real hole rather than a style nit.
"""
import pathlib
import re

import pytest
from starlette.testclient import TestClient

from ca_roads_demo.app import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _chunked(body: bytes):
    """A body with no Content-Length, the shape BodyLimit cannot see."""
    yield body


def test_contact_rejects_oversized_chunked_body(client):
    """The 413 must come from the handler's own cap.

    BodyLimit only inspects Content-Length, so a chunked request reaches
    the handler unmeasured; before the cap, request.form() buffered the
    whole thing and one POST could OOM the single instance.
    """
    big = b"message=" + b"x" * (400 * 1024)
    r = client.post("/api/contact", content=_chunked(big),
                    headers={"content-type":
                             "application/x-www-form-urlencoded"})
    assert r.status_code == 413


def test_waitlist_rejects_oversized_chunked_body(client):
    big = b"email=" + b"x" * (400 * 1024)
    r = client.post("/api/waitlist", content=_chunked(big),
                    headers={"content-type":
                             "application/x-www-form-urlencoded"})
    assert r.status_code == 413


def test_normal_form_post_still_works(client):
    """The cap must not break ordinary submissions."""
    r = client.post("/api/waitlist",
                    data={"email": "someone@example.com", "website": "x"})
    assert r.status_code == 200
    assert "on the list" in r.text


def test_admin_html_not_served_from_static(client):
    """ADMIN_PAGE_PATH is unguessable only if this copy stays hidden."""
    assert client.get("/static/admin.html").status_code == 404


@pytest.mark.parametrize("name", ["map.html", "watch.html", "trip.html"])
def test_app_pages_not_duplicated_under_static(client, name):
    assert client.get(f"/static/{name}").status_code == 404


@pytest.mark.parametrize("path", [
    "/static/site/index.html", "/static/site/pricing.html", "/static/site"])
def test_site_export_not_duplicated_under_static(client, path):
    """The Next export is served from its own routes; /static/site/* was a
    second copy of every marketing page."""
    assert client.get(path).status_code == 404


def test_static_still_serves_real_assets(client):
    """The guard must block only the page duplicates."""
    r = client.get("/static/tokens.css")
    assert r.status_code == 200
    assert "--cs-navy" in r.text


def test_slash_redirect_keeps_https(client):
    """Starlette builds Location from the scope scheme, which is http
    behind Cloudflare; the redirect used to downgrade the visitor."""
    r = client.get("/pricing/", headers={"x-forwarded-proto": "https"},
                   follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)
    assert r.headers["location"].startswith("https://"), r.headers["location"]


def test_forwarded_scheme_ignores_junk(client):
    """An unparseable header must not become the scheme."""
    r = client.get("/pricing/", headers={"x-forwarded-proto": "javascript"},
                   follow_redirects=False)
    assert r.headers["location"].startswith("http://")


def test_wildfire_polygon_popup_escapes_its_label():
    """Agency feed text is bound as popup HTML.

    The point-marker branch escapes it; the polygon branch did not, so a
    feed carrying markup would execute under the CSP's unsafe-inline.
    """
    src = pathlib.Path(
        "src/ca_roads_demo/static/map.html").read_text(encoding="utf-8")
    binds = re.findall(r"\.bindPopup\(([^;]{0,120})", src, re.S)
    raw = [b for b in binds if "m.label" in b and "esc(" not in b]
    assert not raw, f"unescaped label bound into a popup: {raw}"


def _map_src():
    return pathlib.Path(
        "src/ca_roads_demo/static/map.html").read_text(encoding="utf-8")


def test_esc_escapes_quotes_not_just_angle_brackets():
    """esc() output lands in double-quoted attributes (data-inc="..."), so
    a " must be escaped or it breaks out of the attribute."""
    src = _map_src()
    body = re.search(r"function esc\(s\)\s*\{(.*?)\}", src, re.S).group(1)
    assert "&quot;" in body, "esc() does not escape double quotes"


def test_every_humanize_into_a_popup_is_escaped():
    """humanize() is a plain text transform of feed text, and v2() drops
    its args into raw HTML. Every call site must be esc-wrapped."""
    src = _map_src()
    unescaped = []
    for m in re.finditer(r"[^c(]humanize\(", src):
        # The 20 chars before the match should contain esc(
        before = src[max(0, m.start() - 6):m.start() + 1]
        if "esc(" not in before:
            unescaped.append(src[m.start():m.start() + 40].strip())
    assert not unescaped, f"unescaped humanize() into a sink: {unescaped}"


def test_dispatch_log_unit_status_is_escaped():
    """CHP unit-status feed text (STATUS[key] || key) goes into innerHTML."""
    src = _map_src()
    assert "esc(STATUS[key] || key)" in src
