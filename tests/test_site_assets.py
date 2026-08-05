"""Regression test for the final-review finding: the exported marketing
pages reference /_next/... (CSS, JS chunks, woff2), /shots/*.png, and
/favicon.ico, but none of those paths had a route, so every page load
was missing its styling, scripts, and images. This walks the same HTML a
browser gets and fetches every such same-origin asset URL through the
TestClient, exactly as a real page load would.
"""
import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app

# The real build output, not a monkeypatched SITE_DIR + tmp fixture: the
# whole point of this test is pinning what the browser actually fetches.
# CI's site job always runs `npm run build` before this suite, so CI
# always exercises the real assertion below; a local run without Node
# gets a clear skip instead of a false failure.
REAL_SITE_OUT = Path(__file__).resolve().parent.parent / "site" / "out"

PAGES = ["/", "/pricing", "/about", "/contact", "/privacy", "/terms"]

# Same-origin asset references worth following through the app: the
# content-hashed Next bundle, the hero screenshots, and the favicon.
# Deliberately narrow: it does not match the /about.txt?_rsc=... RSC
# payload hrefs Next's client router also emits on Link navigation. Those
# are not served (see the DECISION comment next to the /_next and /shots
# mounts in app.py: a failed RSC fetch falls back to a full page
# navigation, which is acceptable for a 6-page marketing site), so this
# test does not expect them to resolve.
ASSET_RE = re.compile(r'(?:src|href)="(/(?:_next/|shots/|favicon\.ico)[^"]*)"')


@pytest.mark.skipif(
    not REAL_SITE_OUT.exists(),
    reason="site/out is not built; run `cd site && npm run build` first. "
    "CI's site job always builds before this suite runs.",
)
def test_every_referenced_site_asset_resolves(monkeypatch):
    monkeypatch.setattr(demo_app, "SITE_DIR", REAL_SITE_OUT)
    c = TestClient(demo_app.app)
    urls = set()
    for page in PAGES:
        r = c.get(page)
        assert r.status_code == 200, f"{page} did not serve: {r.status_code}"
        urls.update(ASSET_RE.findall(r.text))
    assert urls, "no /_next, /shots, or favicon.ico asset URLs found on any page"
    for url in sorted(urls):
        r = c.get(url)
        assert r.status_code == 200, f"{url} -> {r.status_code}"
