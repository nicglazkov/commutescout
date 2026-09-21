"""Rebuild the animated demo in the README from the live site.

  pip install playwright pillow && playwright install chromium
  python scripts/capture_demo.py --out docs/demo.gif

The GIF is the first thing anyone sees on GitHub, and it was recorded in
July, before nationwide coverage, the plugin marketplace and the phone
apps existed. This retakes it.

Frames are captured in bursts around each interaction rather than as a
continuous recording. A recording spends most of its length waiting on a
geocode, a route and a model answer, and those seconds are dead on
screen; the bursts keep the movement and drop the waiting, which is why
the result is short enough to sit at the top of a README.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = "https://commutescout.com"
VIEWPORT = {"width": 1280, "height": 800}
# The README shows it 880 wide. Capturing at 1280 and scaling down keeps
# the text legible without carrying a 2x frame into a GIF palette.
WIDTH = 880
FRAME_MS = 140


class Reel:
    """Frames in order, with how long each should hold."""

    def __init__(self, page) -> None:
        self.page = page
        self.frames: list[Image.Image] = []
        self.holds: list[int] = []

    def shot(self, hold: int = FRAME_MS) -> None:
        raw = self.page.screenshot(type="png")
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        if img.width != WIDTH:
            img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        self.frames.append(img)
        self.holds.append(hold)

    def burst(self, count: int = 6, gap: int = 90, hold: int = FRAME_MS) -> None:
        """Several frames through a moving moment, so a pan or a panel
        opening reads as motion rather than a jump cut."""
        for _ in range(count):
            self.shot(hold)
            self.page.wait_for_timeout(gap)

    def beat(self, hold: int = 900) -> None:
        """One frame held long enough to read what is on screen."""
        self.shot(hold)


def settle(page, ms: int = 2500) -> None:
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(ms)


def type_and_pick(page, reel, field: str, text: str) -> None:
    """Type an address, then take the first suggestion and wait for the
    field to say it resolved.

    The waiting matters. An unresolved address plans no route, and the
    first version of this recording lost the route options and ended on
    the assistant asking which pass was meant, which is a demo of
    nothing.
    """
    page.fill(f"#{field}", "")
    for i, ch in enumerate(text):
        page.type(f"#{field}", ch, delay=45)
        if i % 3 == 0:
            reel.shot()
    page.wait_for_timeout(1800)
    reel.beat(700)
    page.wait_for_selector(f"#{field}sugg > *", timeout=15000)
    page.locator(f"#{field}sugg > *").first.click()
    # The box shows a tick and the resolved name once the geocode lands.
    page.wait_for_selector(f"#{field}val", state="visible", timeout=15000)
    page.wait_for_timeout(500)
    reel.beat(700)


def record(page) -> Reel:
    reel = Reel(page)
    page.goto(f"{BASE}/map", wait_until="domcontentloaded")
    settle(page, 4000)
    reel.beat(1100)

    # Two addresses, typed, each resolving to a real place.
    page.click("#from")
    type_and_pick(page, reel, "from", "San Jose")
    type_and_pick(page, reel, "to", "South Lake Tahoe")

    # The routes arrive with what is on each of them. Waiting for the
    # summary line rather than a fixed sleep: routing takes as long as
    # it takes, and a burst fired early records an empty panel.
    page.click("#planbtn")
    page.wait_for_selector("text=/\\d+ mi, ~?\\d+ min/", timeout=60000)
    settle(page, 2500)
    reel.burst(8, gap=110)
    reel.beat(1600)

    # Switching between the options redraws the line on the map.
    options = page.locator("#printwrap >> text=/^via /")
    if options.count() < 2:
        options = page.locator("text=/^via /")
    if options.count() >= 2:
        options.nth(1).click()
        page.wait_for_timeout(900)
        reel.burst(6, gap=120)
        reel.beat(1400)
    else:
        print(f"only {options.count()} route options on screen", file=sys.stderr)

    # Ask about the drive, with the route still on the map behind it.
    with contextlib.suppress(Exception):
        page.locator("text=Ask").first.click(timeout=5000)
        page.wait_for_timeout(700)
        reel.beat(700)
        # Tap a suggested question rather than typing one. These carry
        # the route with them; a typed question does not, and the
        # assistant correctly answers a question about no particular
        # drive by asking which drive is meant, which demonstrates
        # nothing. This is also what the original recording showed.
        asked = False
        with contextlib.suppress(Exception):
            page.wait_for_selector("#routeasks > *", timeout=15000)
            reel.beat(1200)
            page.locator("#routeasks > *").first.click()
            asked = True
        if not asked:
            page.fill("#q", "")
            for ch in "How does this drive look right now?":
                page.type("#q", ch, delay=45)
            reel.beat(700)
            page.click("#go")
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
        reel.burst(5, gap=140)
        reel.beat(2000)
    return reel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/demo.gif")
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome")
        except Exception:
            browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1,
                                  color_scheme="light",
                                  timezone_id="America/Los_Angeles")
        page = ctx.new_page()
        reel = record(page)
        browser.close()

    if len(reel.frames) < 12:
        print(f"only {len(reel.frames)} frames; the flow did not run", file=sys.stderr)
        return 1
    first, rest = reel.frames[0], reel.frames[1:]
    first.save(out, save_all=True, append_images=rest, duration=reel.holds,
               loop=0, optimize=True, disposal=2)
    size = out.stat().st_size
    print(f"{out}: {len(reel.frames)} frames, {size // 1024} KB")
    return 0 if size < 9_000_000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
