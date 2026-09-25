"""Refresh the screenshots the repo shows on GitHub and on the site.

Run against the live site:
  pip install playwright && playwright install chromium
  python scripts/capture_shots.py --out docs/shots [--only NAME,NAME]

.github/workflows/screenshots.yml runs this and opens a pull request, so
the images in the README do not quietly age out of date again.

Several shots include the "data as of" chip, so the wall clock is visible
in them. Run this in the morning, which is why it is scheduled rather
than run whenever a change lands.
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = "https://commutescout.com"
# Wide enough that the map's side panel and the layer filters both show,
# at 2x so the PNG stays sharp on a high-density screen.
VIEWPORT = {"width": 1440, "height": 900}
SCALE = 2


def settle(page, ms: int = 3500) -> None:
    """Let tiles, markers and fonts land. The map fetches a snapshot and
    then draws; networkidle alone returns before the draw."""
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(ms)


def dismiss_overlays(page) -> None:
    """Close anything that covers the view: cookie bars, the tour, a
    first-run tip. Missing selectors are fine, this is best effort."""
    for sel in ("button:has-text('Got it')", "button:has-text('Accept')",
                "button:has-text('Dismiss')", "[aria-label='Close']"):
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=800):
                el.click(timeout=1500)
                page.wait_for_timeout(400)
        except Exception:
            pass


def close_popups(page) -> None:
    """Shut anything the map opened over itself. Searching drops a pin
    and opens its card, which lands in the middle of the view and hides
    the thing the shot is meant to show."""
    for sel in (".leaflet-popup-close-button", "[aria-label='Close popup']"):
        for _ in range(3):
            try:
                el = page.locator(sel).first
                if not el.is_visible(timeout=600):
                    break
                el.click(timeout=1200)
                page.wait_for_timeout(250)
            except Exception:
                break
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def search_to(page, place: str, zoom_out: int = 3) -> None:
    """Frame the map on a place, the way a visitor does.

    Searching is the reliable way to reach a known city, but it leaves
    two things behind that ruin a screenshot: a result card over the
    centre of the map, and a street-level zoom where a metro's worth of
    incidents collapses to two or three dots. Both are undone here.

    The focus parameter was the obvious alternative and is worse: it
    points at one past incident and opens a "this alert has cleared"
    card instead.
    """
    box = page.locator("input[placeholder*='Search a place']").first
    box.click()
    box.fill(place)
    page.wait_for_timeout(1500)
    page.keyboard.press("Enter")
    page.wait_for_timeout(2500)
    close_popups(page)
    for _ in range(zoom_out):
        try:
            out_button = "a.leaflet-control-zoom-out, button[title='Zoom out']"
            page.locator(out_button).first.click(timeout=1200)
            page.wait_for_timeout(500)
        except Exception:
            break
    close_popups(page)


def shot_map(page, out: Path) -> None:
    """The live map over a busy metro, layers and counts visible."""
    page.goto(f"{BASE}/map", wait_until="domcontentloaded")
    settle(page, 5000)
    dismiss_overlays(page)
    search_to(page, "Los Angeles, CA")
    settle(page, 6000)
    dismiss_overlays(page)
    close_popups(page)
    page.screenshot(path=out / "map.png")


def shot_planner(page, out: Path) -> None:
    """The route planner with two options and live conditions."""
    page.goto(f"{BASE}/map", wait_until="domcontentloaded")
    settle(page, 4000)
    dismiss_overlays(page)
    # The planner is driven from the two address boxes, then Plan route.
    # The first autocomplete suggestion is taken so the geocode resolves
    # to a real place rather than leaving the field unvalidated.
    for field, text in (("from", "San Jose, CA"), ("to", "South Lake Tahoe, CA")):
        page.fill(f"#{field}", text)
        page.wait_for_timeout(1500)
        try:
            page.locator(f"#{field}sugg > *").first.click(timeout=3000)
        except Exception:
            page.keyboard.press("Enter")
        page.wait_for_timeout(600)
    page.click("#planbtn")
    settle(page, 9000)
    page.screenshot(path=out / "planner.png")


def shot_answer(page, out: Path) -> None:
    """The assistant answering from the live feeds. This one costs a real
    model call, which is why the capture runs monthly rather than on
    every change."""
    page.goto(f"{BASE}/map", wait_until="domcontentloaded")
    settle(page, 4000)
    dismiss_overlays(page)
    page.click("text=Ask")
    page.wait_for_timeout(800)
    page.fill("#q", "Do I need chains to get to Tahoe today?")
    page.click("#go")
    # The answer streams in. The loader hides when the first token
    # arrives, not when the last one does, so waiting on it alone caught
    # a sentence cut in half. Wait for the text to stop growing.
    with contextlib.suppress(Exception):
        page.wait_for_selector("#loader", state="hidden", timeout=90000)
    last, stable = -1, 0
    for _ in range(60):
        page.wait_for_timeout(1000)
        now = len(page.locator("#result").inner_text())
        stable = stable + 1 if now == last else 0
        last = now
        if stable >= 3:
            break
    page.wait_for_timeout(1500)
    page.screenshot(path=out / "answer.png")


def shot_marketplace(page, out: Path) -> None:
    """The plugin marketplace, which nothing in the repo shows today."""
    page.goto(f"{BASE}/marketplace", wait_until="domcontentloaded")
    settle(page, 4000)
    page.screenshot(path=out / "marketplace.png")


def shot_developers(page, out: Path) -> None:
    """The API page: the contract a developer lands on."""
    page.goto(f"{BASE}/developers", wait_until="domcontentloaded")
    settle(page, 3000)
    page.screenshot(path=out / "developers.png")


def shot_hero(page, out: Path) -> None:
    """The marketing site's hero: a wide, multi-state view, so covering
    37 states is visible rather than asserted."""
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(f"{BASE}/map", wait_until="domcontentloaded")
    settle(page, 5000)
    dismiss_overlays(page)
    # Far enough out that several states are on screen at once. A
    # search lands at street level, and the hero is meant to show the
    # spread of the coverage, not one intersection in Reno.
    search_to(page, "Reno, NV", zoom_out=9)
    settle(page, 9000)
    close_popups(page)
    # 3200 px of PNG was 1.7 MB for a slot 1024 px wide. WebP at 2048
    # is about 150 KB and indistinguishable at that size.
    page.screenshot(path=out / "hero-map.png")
    with Image.open(out / "hero-map.png") as im:
        im = im.convert("RGB")
        im = im.resize((2048, round(im.height * 2048 / im.width)), Image.LANCZOS)
        im.save(out / "hero-map.webp", "WEBP", quality=82, method=6)
    (out / "hero-map.png").unlink()
    page.set_viewport_size(VIEWPORT)


SHOTS = {
    "map": shot_map,
    "planner": shot_planner,
    "answer": shot_answer,
    "marketplace": shot_marketplace,
    "developers": shot_developers,
    "hero": shot_hero,
}

# The marketing hero is not a README image and does not live in
# docs/shots; it went stale for months because the capture only knew
# about one folder.
#
# The link-preview card (src/ca_roads_demo/static/shots/og.png) is not
# captured at all any more. As a raw screenshot it caught the search
# dropdown over a third of the map and clipped the version label under
# the logo, and at 1200x630 a busy map reads as noise in a chat preview.
# It is now a designed card, adapted from the repository's social
# preview, and changes only by hand.
ELSEWHERE = {
    "hero-map.webp": "site/public/shots/hero-map.webp",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="shots")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    wanted = [n for n in (args.only.split(",") if args.only else SHOTS) if n in SHOTS]

    failures = []
    with sync_playwright() as pw:
        # CI installs Playwright's own Chromium; a laptop usually has
        # Google Chrome already and no browser download.
        try:
            browser = pw.chromium.launch(channel="chrome")
        except Exception:
            browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE,
                                  color_scheme="light",
                                  timezone_id="America/Los_Angeles")
        page = ctx.new_page()
        for name in wanted:
            try:
                SHOTS[name](page, out)
                # Most shots write <name>.png; the hero writes the file
                # name the site expects instead.
                written = out / ("hero-map.webp" if name == "hero" else f"{name}.png")
                size = written.stat().st_size
                print(f"  {written.name}  {size // 1024} KB")
                if size < 20_000:
                    failures.append(f"{name}: only {size} bytes, probably blank")
            except Exception as exc:  # noqa: BLE001 - one shot never stops the rest
                failures.append(f"{name}: {type(exc).__name__}: {exc}")
        browser.close()
    # Copy the two that belong elsewhere, so one run refreshes every
    # image in the repository rather than most of them.
    repo = Path(__file__).resolve().parent.parent
    for name, dest in ELSEWHERE.items():
        src = out / name
        if src.exists():
            target = repo / dest
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(src.read_bytes())
            print(f"  {dest}")
    for f in failures:
        print("FAILED", f, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
