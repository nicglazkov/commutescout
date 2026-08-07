# SaaS shell redesign implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the professional site shell (homepage, pricing with Pro waitlist, about, contact, restyled legal pages) around the existing map app, move the map to `/map`, add the two supporting endpoints, and enforce Free watch-area size limits.

**Architecture:** A new `site/` Node workspace produces a static export (Next.js `output: 'export'`, Tailwind, shadcn/ui, Tailark templates). The export is copied into the Python package's static directory at Docker build time, and Starlette serves it like any other static file. The map app keeps its vanilla-JS internals and only adopts shared design tokens and navigation. No Node runs in production.

**Tech stack:** Next.js (static export), Tailwind, shadcn/ui, Tailark Complete (owned license), Starlette, pytest, Playwright.

## Global constraints

Every task implicitly includes these. Copy them into your head before starting.

- Spec: `docs/superpowers/specs/2026-08-05-saas-shell-redesign-design.md`. The spec wins over this plan if they disagree; flag the disagreement.
- Every change ships as a small PR from a branch. Never commit to `main`. Merge only after CI is SUCCESS with no PENDING/IN_PROGRESS/QUEUED checks (`gh pr checks <n> --json state`).
- All prose (page copy, docs, commit messages) follows the Google developer documentation style guide: second person, active voice, present tense, sentence-case headings. No em or en dashes anywhere. Minimal to zero emoji.
- Nic's email address must never appear in the repo or in served pages. The contact destination lives in the `CONTACT_EMAIL` environment variable.
- `docs-private/` is gitignored and must never be committed or quoted in tracked files.
- Windows working tree is CRLF: use the Read and Edit tools for file edits, or normalize line endings in scripts. Write new files with LF.
- Do not trust training data for versions, import paths, or install commands. Verify against current docs in the versions task, and record what you found.
- The map page (`index.html`, becoming `map.html`) is performance-tuned. Do not change its layout, interactions, or JavaScript beyond what a task explicitly lists.
- Legal page content changes require Nic's explicit approval. Reskinning is allowed; rewording is not.
- Python tests run with `.venv/Scripts/python.exe -m pytest -q`; lint with `.venv/Scripts/python.exe -m ruff check src/ tests/`.
- Deploys are manual `gcloud run deploy` with `--project ca-roads-mcp`, `--service-account ca-roads-run@ca-roads-mcp.iam.gserviceaccount.com`, and `--max-instances 1`. Demo also needs `--command ca-roads-demo --min-instances 1 --memory 2Gi --concurrency 20`. Never pass `--set-env-vars` or `--set-secrets` (they wipe the existing set); use `--update-env-vars` for additions.

---

### Task 1: Scaffold the site workspace

**Files:**
- Create: `site/` (via scaffolder), `site/next.config.ts`, `site/.gitignore`
- Modify: `.gitignore` (root)

**Interfaces:**
- Produces: `cd site && npm run build` writes a static export to `site/out/` containing `index.html`. Later tasks add pages to `site/app/`.

- [ ] **Step 1: Verify current versions before scaffolding**

Run these and record the answers in the PR description. Do not skip; the tooling doc forbids trusting remembered versions.

```bash
npm show next version
npm show tailwindcss version
npx shadcn@latest --help | head -5
```

Also open https://nextjs.org/docs/app/building-your-application/deploying/static-exports (or the current equivalent) and confirm `output: 'export'` is still the static-export mechanism in the major you got.

- [ ] **Step 2: Scaffold**

```bash
cd C:/Users/live/Documents/code/ca-roads-mcp
npx create-next-app@latest site --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm
```

If the scaffolder prompts for anything not covered by flags, take the default and note it.

- [ ] **Step 3: Configure static export**

Replace the generated `site/next.config.ts` content with:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: the build writes plain HTML/CSS/JS to out/, which the
  // Python app serves. No Node runs in production.
  output: "export",
  // The exported pages are served from the site root by Starlette.
  trailingSlash: false,
  images: { unoptimized: true },
};

export default nextConfig;
```

- [ ] **Step 4: Ignore build outputs**

Append to the root `.gitignore`:

```
site/node_modules/
site/out/
site/.next/
```

- [ ] **Step 5: Build and verify the export**

```bash
cd site && npm run build
ls out/index.html
```

Expected: the build succeeds and `out/index.html` exists.

- [ ] **Step 6: Commit**

```bash
git checkout -b feat/site-workspace
git add -A && git commit -m "feat: scaffold the site workspace (Next.js static export)"
```

---

### Task 2: Shared design tokens

**Files:**
- Create: `src/ca_roads_demo/static/tokens.css`
- Modify: `site/app/globals.css`

**Interfaces:**
- Produces: CSS custom properties `--cs-navy`, `--cs-navy2`, `--cs-sky`, `--cs-ink`, `--cs-paper`, `--cs-line`, `--cs-font` available to both the map app and the marketing pages. Task 15 makes the map app consume them; Task 6 makes the site consume them.

- [ ] **Step 1: Extract the current palette**

Read the `:root`/top CSS variables in `src/ca_roads_demo/static/index.html` (search for `--navy`, `--sky`, `--line`). Copy the exact color values into the token sheet; do not invent new colors.

- [ ] **Step 2: Write the token sheet**

Create `src/ca_roads_demo/static/tokens.css` with the values found in step 1 (the hex values below are placeholders for the real ones you just read; use the real ones):

```css
/* Design tokens shared by the map app and the marketing site.
   The map app's CSS and the site's Tailwind config both reference
   these. Change a color here and both surfaces move together. */
:root {
  --cs-navy: #0f1c2b;   /* header, dark bands */
  --cs-navy2: #16283c;  /* raised dark surfaces */
  --cs-sky: #2f81f7;    /* primary action */
  --cs-ink: #0f172a;    /* body text on light */
  --cs-paper: #ffffff;  /* light surfaces */
  --cs-line: #e2e8f0;   /* borders */
  --cs-font: Inter, system-ui, sans-serif;
}
```

- [ ] **Step 3: Wire the site to the tokens**

In `site/app/globals.css`, import the token sheet and map Tailwind theme colors to the custom properties using the Tailwind mechanism current in the major you verified (in Tailwind v4 that is `@theme` referencing `var(--cs-*)`; in v3 it is `tailwind.config` `colors`). The site build must fail loudly if the import path breaks, so import the file by relative path:

```css
@import "../../src/ca_roads_demo/static/tokens.css";
```

- [ ] **Step 4: Verify**

```bash
cd site && npm run build
grep -r "cs-navy" out/ | head -2
```

Expected: build succeeds and the token names appear in the emitted CSS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: shared design tokens for app and site"
```

---

### Task 3: Serve the exported site from Starlette

**Files:**
- Modify: `src/ca_roads_demo/app.py`
- Test: `tests/test_site_pages.py`

**Interfaces:**
- Consumes: `site/out/` from Task 1.
- Produces: `SITE_DIR` constant and `site_page(name)` handler in `app.py`; routes `/`, `/pricing`, `/about`, `/contact` serving exported pages. Task 5 re-points `/` and the legal routes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_site_pages.py`:

```python
"""The marketing site: exported pages served by Starlette."""
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app


def test_site_pages_serve_when_built(tmp_path, monkeypatch):
    # Simulate a built export without requiring Node in CI for this test.
    (tmp_path / "pricing").mkdir(parents=True)
    (tmp_path / "index.html").write_text("<h1>home</h1>", encoding="utf-8")
    (tmp_path / "pricing" / "index.html").write_text("<h1>pricing</h1>",
                                                     encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    assert b"home" in c.get("/").content
    assert b"pricing" in c.get("/pricing").content


def test_map_still_serves_when_site_is_not_built(tmp_path, monkeypatch):
    """Local dev without Node: the map and APIs must work; marketing
    pages return a clear 503, not a stack trace."""
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path / "missing")
    c = TestClient(demo_app.app)
    r = c.get("/")
    assert r.status_code == 503
    assert "site is not built" in r.text
```

- [ ] **Step 2: Run it to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_site_pages.py -q
```

Expected: FAIL (no `SITE_DIR`).

- [ ] **Step 3: Implement**

In `app.py`, near `STATIC_DIR`, add:

```python
# The marketing site: a static export built from site/ (see
# docs/superpowers/specs/2026-08-05-saas-shell-redesign-design.md).
# The Docker build copies site/out here; local dev without Node gets a
# clear 503 for marketing pages while the map and APIs keep working.
SITE_DIR = STATIC_DIR / "site"


def _site_response(page: str):
    f = SITE_DIR / page / "index.html" if page else SITE_DIR / "index.html"
    if not f.exists():
        return Response(
            "The marketing site is not built. Run: cd site && npm ci && "
            "npm run build. The map is at /map and APIs are unaffected.",
            status_code=503, media_type="text/plain")
    return FileResponse(f)
```

Add handlers and routes (`/` still points at the map until Task 5; wire `/pricing`, `/about`, `/contact` now):

```python
async def site_pricing(_: Request):
    return _site_response("pricing")


async def site_about(_: Request):
    return _site_response("about")


async def site_contact(_: Request):
    return _site_response("contact")
```

For this task only, also register a temporary test seam: `/` keeps serving the map, and the two tests above monkeypatch `SITE_DIR` and hit `/` through a `site_home` handler that Task 5 will promote. Register `site_home` at `/site-preview` for now so the first test asserts against `/site-preview` instead of `/`; update the test accordingly.

- [ ] **Step 4: Run the tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_site_pages.py -q
.venv/Scripts/python.exe -m ruff check src/ tests/
```

Expected: PASS, lint clean.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: serve the exported marketing site from Starlette"
```

---

### Task 4: Build pipeline (CI and Docker)

**Files:**
- Modify: `Dockerfile`, `.github/workflows/ci.yml`
- Test: extend `tests/test_site_pages.py`

**Interfaces:**
- Consumes: `site/` workspace, `SITE_DIR`.
- Produces: Docker image containing `src/ca_roads_demo/static/site/`; CI job `site` that fails on a broken export.

- [ ] **Step 1: Two-stage Dockerfile**

Replace the single stage with:

```dockerfile
FROM node:22-slim AS site
WORKDIR /site
COPY site/package.json site/package-lock.json ./
RUN npm ci
COPY site/ ./
COPY src/ca_roads_demo/static/tokens.css /src/ca_roads_demo/static/tokens.css
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE constraints.txt ./
COPY src ./src
COPY --from=site /site/out ./src/ca_roads_demo/static/site

# (keep the existing pip install comment block and RUN line unchanged)
RUN pip install --no-cache-dir -c constraints.txt ".[demo]"

RUN useradd --create-home --uid 1001 app
USER app

ENV PORT=8080
EXPOSE 8080

CMD ["ca-roads-mcp", "--transport", "http"]
```

Note the tokens.css copy path: the site's `globals.css` imports it by relative path `../../src/...`, so the build stage must recreate that relative layout. Verify the import resolves inside the container by the build succeeding.

- [ ] **Step 2: CI job**

In `.github/workflows/ci.yml`, add a job alongside `test`:

```yaml
  site:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: site/package-lock.json
      - run: npm ci
        working-directory: site
      - run: npm run build
        working-directory: site
      - name: Exported routes exist
        run: |
          test -f site/out/index.html
          test -f site/out/pricing/index.html
          test -f site/out/about/index.html
          test -f site/out/contact/index.html
```

The route assertions will fail until Task 6 adds the pages; to keep CI green in this PR, assert only `site/out/index.html` now and extend the list in the Task 6 PR.

- [ ] **Step 3: Local Docker smoke test**

```bash
docker build -t cs-test . && docker run --rm cs-test ls src/ca_roads_demo/static/site/index.html
```

Expected: the file lists. If Docker is unavailable locally, note it and rely on the Cloud Run build at deploy time plus CI.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: build the site export in CI and the Docker image"
```

Open a PR for Tasks 1-4 together, merge after CI is green.

---

### Task 5: Move the map to /map

**Files:**
- Rename: `src/ca_roads_demo/static/index.html` to `src/ca_roads_demo/static/map.html`
- Modify: `src/ca_roads_demo/app.py`, `src/ca_roads_demo/static/watch.html`, `src/ca_roads_demo/static/trip.html`
- Test: `tests/test_site_pages.py`, `tests/test_bootgeo.py`

**Interfaces:**
- Consumes: `_site_response` from Task 3.
- Produces: `/` serves the site homepage; `/map` serves the map with boot-geo injection intact. `map_page(request)` handler replaces `index(request)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_site_pages.py`:

```python
def test_map_serves_at_map_with_bootgeo(monkeypatch):
    c = TestClient(demo_app.app)
    r = c.get("/map", headers={"x-visitor-lat": "37.77",
                               "x-visitor-lon": "-122.41"})
    assert r.status_code == 200
    assert 'id="bootgeo"' in r.text          # data island still injected
    assert "leaflet" in r.text.lower()


def test_root_serves_homepage_not_map(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<h1>home</h1>", encoding="utf-8")
    monkeypatch.setattr(demo_app, "SITE_DIR", tmp_path)
    c = TestClient(demo_app.app)
    assert b"home" in c.get("/").content
    assert b"leaflet" not in c.get("/").content.lower()
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/Scripts/python.exe -m pytest tests/test_site_pages.py -q
```

- [ ] **Step 3: Implement the move**

1. `git mv src/ca_roads_demo/static/index.html src/ca_roads_demo/static/map.html`.
2. In `app.py`: rename the `index` handler to `map_page`, point its `FileResponse`/template reads at `map.html` (search for `index.html` and `_index_template`), register `Route("/map", map_page)`, and change `Route("/", index)` to a `site_home` handler that calls `_site_response("")`.
3. Update the rate-limit exemption list and any hardcoded `"/"` page references in `app.py` (search for `"/", ` in the exempt-paths tuple around line 1750) to include `/map`.
4. In `watch.html` and `trip.html`, change nav links `href="/"` (the map links) to `href="/map"`. Keep the logo link pointing at `/`.
5. In `map.html`, keep every internal reference as-is (the service worker does not cache HTML; the snapshot preload and `SNAP_BASE` are host-based, not path-based; verify both by search, not assumption).
6. Metadata split: `map.html` keeps its title but its `og:url` and `ld+json` update to `https://commutescout.com/map`. The homepage takes the product-level metadata in Task 7.

- [ ] **Step 4: Run the full suite**

```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check src/ tests/
```

Expected: all pass. `test_bootgeo.py` and `test_snapshot.py` reference the page by route or read `index.html` directly; update any direct filename references to `map.html` (search `tests/` for `index.html`).

- [ ] **Step 5: Manual boot check**

Run the local server and confirm `/map` paints markers (reuse the pattern from the snapshot work: Playwright, wait for `#maploading.gone`). Confirm `/` returns the 503 not-built message locally, which is correct until the site pages exist.

- [ ] **Step 6: Commit and PR**

```bash
git checkout -b feat/map-at-map
git add -A && git commit -m "feat: move the map to /map, root becomes the homepage"
```

---

### Task 6: Site layout shell and Tailark vendoring

**Files:**
- Create: `site/components/site-header.tsx`, `site/components/site-footer.tsx`, `site/app/layout.tsx` (modify generated), `site/components/blocks/` (vendored Tailark blocks)

**Interfaces:**
- Produces: `<SiteHeader/>` and `<SiteFooter/>` used by every page; Tailark blocks available under `site/components/blocks/`. Pages in Tasks 7-10 import these.

- [ ] **Step 1: Verify the Tailark install path**

Open tailark.com with Nic's Complete license and check the current documented way to pull blocks (registry command vs kit download). Record which you used. Pick blocks from one themed kit that fits a navy/sky data product; do not mix kits (the tooling doc's coherence rule).

- [ ] **Step 2: Vendor the chosen blocks**

Install or copy into `site/components/blocks/`. Required block types: hero, feature grid, logo/stat band, pricing cards, FAQ or content section, footer. Adapt colors to the token variables (`bg-[var(--cs-navy)]` or the theme mapping from Task 2), never the kit's stock palette. Fonts: Inter via the token sheet, not a new font.

- [ ] **Step 3: Header and footer**

`site-header.tsx`: logo (reuse `/logo.svg`, served by the app), links Home, Pricing, About, Contact, and a primary "Open the map" button linking `/map`. `site-footer.tsx`: sitemap links (all pages, `/privacy`, `/terms`, GitHub, MCP docs link), the data-attribution line consistent with the map footer, and no email address anywhere.

- [ ] **Step 4: Build check**

```bash
cd site && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: site layout shell with vendored Tailark blocks"
```

---

### Task 7: Homepage

**Files:**
- Create: `site/app/page.tsx`, `site/public/shots/` (captured imagery)
- Create: capture script in scratchpad (not committed)

**Interfaces:**
- Consumes: layout shell, blocks, tokens.
- Produces: exported `/` page; hero screenshot assets under `site/public/shots/`.

- [ ] **Step 1: Capture fresh product imagery**

Playwright against the live site (or local with keys): a wide multi-state map view with markers, desktop 1440x900, and a route-planned view. Save under `site/public/shots/`. These replace the stale California-only imagery. Use public landmark routes only (San Jose to San Francisco), never personal addresses.

- [ ] **Step 2: Build the page**

Sections and exact copy (adjust layout to the chosen blocks, keep the copy):

- Hero: heading "Live road conditions, straight from the source." Subhead: "CommuteScout reads 53 official agency feeds across 38 states: incidents, closures, chain controls, cameras, and wildfires on one live map." Primary action: "Open the map" to `/map`. Secondary: "Get Pro updates" anchor to the pricing waitlist.
- How it works, four items: "See it. The live map shows what agencies are reporting right now, refreshed about every 30 seconds." / "Plan it. Route options with live conditions along the way, exportable to GPX or KML." / "Ask it. Plain-English answers read from the same feeds, with per-source timestamps." / "Watch it. Draw an area and get push or email alerts when something appears inside it."
- Data credibility band: the three stats (53 agency feeds, 38 states, per-source timestamps) and one sentence: "Every answer names its sources and their timestamps. When a feed goes stale, CommuteScout says so instead of guessing."
- Developer band: "Bring live roads to your assistant." with the MCP connector URL `https://mcp.commutescout.com/mcp` in a copy field and a GitHub link.
- Footer via `<SiteFooter/>`.

The stats must not be hardcoded twice: put them in `site/lib/stats.ts` as constants with a comment pointing at `tests/test_snapshot.py::test_state_counts_are_current`, and extend that test to also scan `site/lib/stats.ts` so drift fails CI.

- [ ] **Step 3: Metadata**

Homepage takes the product metadata: title "CommuteScout: live road conditions, traffic map, and route planner", description matching the map page's current one, `og:image` pointing at the existing `/static/shots/og.png`, `og:url` `https://commutescout.com/`.

- [ ] **Step 4: Build, extend CI route assertions, commit**

```bash
cd site && npm run build && test -f out/index.html
git add -A && git commit -m "feat: homepage"
```

Extend the CI `site` job assertions to include the new routes (from Task 4 step 2).

---

### Task 8: Pricing page with waitlist form

**Files:**
- Create: `site/app/pricing/page.tsx`

**Interfaces:**
- Consumes: layout shell; `POST /api/waitlist` (Task 12; the form targets it before it exists, which is fine because the form is a plain POST and Task 12 lands in the same release).
- Produces: exported `/pricing` page.

- [ ] **Step 1: Build the page**

Two cards from the Tailark pricing block, adapted:

Free card, listed exactly:
- "The full live map, all 38 states"
- "Route planner with GPX, KML, and print export"
- "Ask about your drive (daily cap)"
- "3 watch areas: circles up to 25 mi radius, polygons up to 2,000 sq mi, routes up to 250 mi with a 2 mi buffer"

Pro card, badge "Coming soon", listed:
- "More and larger watch areas"
- "Event history and playback"
- "Route briefings and exports"
- No price number anywhere on the card.

Waitlist form under the Pro card:

```tsx
<form method="post" action="/api/waitlist">
  <input type="email" name="email" required placeholder="you@example.com" />
  <input type="text" name="website" tabIndex={-1} autoComplete="off"
         className="hidden" aria-hidden="true" />
  <button type="submit">Notify me when Pro launches</button>
</form>
<p>Leave your email and we'll tell you when Pro launches. Nothing else, no
newsletter.</p>
```

The hidden `website` field is the honeypot; Task 12 rejects any submission that fills it.

- [ ] **Step 2: Build and commit**

```bash
cd site && npm run build && test -f out/pricing/index.html
git add -A && git commit -m "feat: pricing page with Pro waitlist"
```

---

### Task 9: About and contact pages

**Files:**
- Create: `site/app/about/page.tsx`, `site/app/contact/page.tsx`

**Interfaces:**
- Consumes: layout shell; `POST /api/contact` (Task 11).
- Produces: exported `/about` and `/contact` pages.

- [ ] **Step 1: About page**

Content, in this order: what CommuteScout is (two sentences, reuse the README opening), the data story ("Every layer comes from official agency feeds. CommuteScout never scrapes, and every response carries per-source timestamps."), the sustainability position (reuse the README "License & sustainability" wording adapted to sentence case), and a GitHub link.

- [ ] **Step 2: Contact page**

Form with name (text, required, maxLength 80), email (email, required), message (textarea, required, maxLength 2000), plus the same hidden `website` honeypot field as Task 8. `method="post" action="/api/contact"`. Below the form: "Found a bug? Open a GitHub issue." linking the repo, and "Security issue? Report it privately." linking the GitHub security advisory page (the URL is in SECURITY.md).

- [ ] **Step 3: Build and commit**

```bash
cd site && npm run build && test -f out/about/index.html && test -f out/contact/index.html
git add -A && git commit -m "feat: about and contact pages"
```

---

### Task 10: Legal pages in the new shell

**Files:**
- Create: `site/app/privacy/page.tsx`, `site/app/terms/page.tsx`
- Modify: `src/ca_roads_demo/app.py` (point `/privacy` and `/terms` at the export)
- Test: `tests/test_site_pages.py`

**Interfaces:**
- Consumes: `_site_response`, existing `privacy.html` and `terms.html` content.
- Produces: `/privacy` and `/terms` served from the export; old HTML files removed.

- [ ] **Step 1: Write the content-preservation test first**

The reviewed legal text must survive the reskin word-for-word. Before touching anything, extract the visible text of the current pages and pin it:

```python
def test_legal_content_survived_the_reskin(tmp_path, monkeypatch):
    """The reskin moves privacy and terms into the site shell. The
    words themselves are CalOPPA-reviewed and must not change without
    Nic's approval, so this test compares normalized visible text
    against the pre-reskin extraction committed in tests/fixtures/."""
    import re

    def visible(html):
        t = re.sub(r"<script.*?</script>", "", html, flags=re.S)
        t = re.sub(r"<[^>]+>", " ", t)
        return " ".join(t.split())

    new = visible((demo_app.SITE_DIR / "privacy" / "index.html")
                  .read_text(encoding="utf-8"))
    old = (Path("tests/fixtures/privacy_text.txt")
           .read_text(encoding="utf-8"))
    assert old in new
```

Generate `tests/fixtures/privacy_text.txt` and `terms_text.txt` from the CURRENT pages with the same `visible()` function before the reskin, and commit them in this task.

- [ ] **Step 2: Port the content**

Copy each page's body content into the corresponding `page.tsx` inside the site shell (header, footer, type from tokens). Effective dates and all wording stay identical. Note: the site build must produce output where the normalized old text is a substring of the new page's normalized text (the shell adds nav text around it).

- [ ] **Step 3: Re-point the routes and delete the old files**

In `app.py`, change `privacy_page` and `terms_page` to `_site_response("privacy")` / `_site_response("terms")`. `git rm` the old `privacy.html` and `terms.html`.

- [ ] **Step 4: Run tests, commit**

```bash
cd site && npm run build
.venv/Scripts/python.exe -m pytest tests/test_site_pages.py -q
git add -A && git commit -m "feat: legal pages in the site shell, content unchanged"
```

---

### Task 11: Contact endpoint

**Files:**
- Modify: `src/ca_roads_demo/app.py` (route + handler), `SoftLimit.PREFIXES`
- Test: `tests/test_contact.py`

**Interfaces:**
- Consumes: `watch._email_alert(to_email, subject, html, text) -> bool` (existing, `src/ca_roads_demo/watch.py:1218`); `CONTACT_EMAIL` env var.
- Produces: `POST /api/contact` accepting form-encoded `name`, `email`, `message`, `website` (honeypot).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_contact.py`:

```python
"""POST /api/contact: the contact form's server side."""
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch


def _client(monkeypatch, sent):
    async def fake_email(to_email, subject, html, text):
        sent.append({"to": to_email, "subject": subject, "text": text})
        return True
    monkeypatch.setattr(watch, "_email_alert", fake_email)
    monkeypatch.setenv("CONTACT_EMAIL", "owner@example.com")
    return TestClient(demo_app.app)


def test_valid_submission_sends_email(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    r = c.post("/api/contact", data={"name": "Ada", "email": "a@b.co",
                                     "message": "hello", "website": ""})
    assert r.status_code == 200
    assert sent and sent[0]["to"] == "owner@example.com"
    assert "Ada" in sent[0]["text"] and "a@b.co" in sent[0]["text"]


def test_honeypot_filled_is_dropped_but_returns_ok(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    r = c.post("/api/contact", data={"name": "Bot", "email": "b@b.co",
                                     "message": "spam", "website": "x"})
    assert r.status_code == 200      # bots get no signal
    assert not sent


def test_missing_fields_rejected(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    assert c.post("/api/contact", data={"name": "", "email": "a@b.co",
                                        "message": "m", "website": ""}
                  ).status_code == 400
    assert not sent


def test_unconfigured_contact_email_gives_503(monkeypatch):
    sent = []
    c = _client(monkeypatch, sent)
    monkeypatch.delenv("CONTACT_EMAIL")
    r = c.post("/api/contact", data={"name": "Ada", "email": "a@b.co",
                                     "message": "m", "website": ""})
    assert r.status_code == 503
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/Scripts/python.exe -m pytest tests/test_contact.py -q
```

- [ ] **Step 3: Implement**

In `app.py`:

```python
async def api_contact(request: Request):
    """The contact form. Emails the site owner through the existing
    Resend integration; the destination never appears in the repo or
    on a page. A filled honeypot returns success without sending, so
    bots get no signal to iterate on."""
    form = await request.form()
    name = (form.get("name") or "").strip()[:80]
    email = (form.get("email") or "").strip()[:120]
    message = (form.get("message") or "").strip()[:2000]
    if (form.get("website") or "").strip():
        return PlainTextResponse("Thanks. Your message is on its way.")
    if not (name and message and "@" in email and "." in email.rsplit("@", 1)[-1]):
        return PlainTextResponse("Name, a valid email, and a message are "
                                 "required.", status_code=400)
    dest = os.environ.get("CONTACT_EMAIL", "")
    if not dest:
        return PlainTextResponse("Contact is not configured on this "
                                 "deployment.", status_code=503)
    body = f"From: {name} <{email}>\n\n{message}"
    ok = await watch._email_alert(dest, f"CommuteScout contact: {name}",
                                  f"<pre>{html_escape(body)}</pre>", body)
    if not ok:
        return PlainTextResponse("Sending failed. Try again in a minute.",
                                 status_code=502)
    return PlainTextResponse("Thanks. Your message is on its way.")
```

Import `html.escape` as `html_escape`. Register `Route("/api/contact", api_contact, methods=["POST"])`. Add `"/api/contact"` and `"/api/waitlist"` to `SoftLimit.PREFIXES` (`app.py:1607`).

- [ ] **Step 4: Run tests and lint, commit**

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check src/ tests/
git add -A && git commit -m "feat: contact endpoint via Resend"
```

Deployment note for the PR body: prod needs `--update-env-vars CONTACT_EMAIL=<Nic's choice>` at the release deploy.

---

### Task 12: Waitlist endpoint

**Files:**
- Modify: `src/ca_roads_demo/watch.py` (store method), `src/ca_roads_demo/app.py` (route + handler)
- Test: `tests/test_waitlist.py`

**Interfaces:**
- Consumes: `WatchStore` Firestore client (`self.db`, `watch.py:236`).
- Produces: `POST /api/waitlist` accepting form-encoded `email`, `website`; `WatchStore.add_waitlist_email(email) -> bool` (False when already present).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_waitlist.py` following the repo's existing pattern for Firestore-backed tests (see how `tests/test_watch.py` fakes the store; use the same `MemoryStore`/monkeypatch approach found there):

```python
"""POST /api/waitlist: the Pro waitlist."""
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import watch


def _client(monkeypatch, added):
    async def fake_add(email):
        if email in added:
            return False
        added.append(email)
        return True
    monkeypatch.setattr(watch, "add_waitlist_email", fake_add, raising=False)
    return TestClient(demo_app.app)


def test_signup_stores_email(monkeypatch):
    added = []
    c = _client(monkeypatch, added)
    r = c.post("/api/waitlist", data={"email": "a@b.co", "website": ""})
    assert r.status_code == 200
    assert added == ["a@b.co"]


def test_duplicate_is_idempotent(monkeypatch):
    added = ["a@b.co"]
    c = _client(monkeypatch, added)
    r = c.post("/api/waitlist", data={"email": "a@b.co", "website": ""})
    assert r.status_code == 200          # same message, no error
    assert added == ["a@b.co"]


def test_honeypot_and_bad_email(monkeypatch):
    added = []
    c = _client(monkeypatch, added)
    assert c.post("/api/waitlist", data={"email": "a@b.co",
                                         "website": "x"}).status_code == 200
    assert c.post("/api/waitlist", data={"email": "not-an-email",
                                         "website": ""}).status_code == 400
    assert not added
```

- [ ] **Step 2: Run to verify failure, then implement**

Module-level function in `watch.py` (matching how the store is reached elsewhere in the file; if the store object is the access path, add `async def add_waitlist_email(email)` that uses the active store and degrades cleanly when Firestore is unavailable locally, same as the existing watch endpoints do):

```python
async def add_waitlist_email(email: str) -> bool:
    """Store a Pro-waitlist signup. Returns False when the address is
    already on the list. Document id is the lowercased address, which
    makes duplicates a natural no-op."""
    store = get_store()
    doc = store.db.collection("waitlist").document(email.lower())
    if (await doc.get()).exists:
        return False
    await doc.set({"email": email.lower(),
                   "added": firestore.SERVER_TIMESTAMP})
    return True
```

Adjust `get_store()`/`firestore` names to the file's actual ones (read the top of `watch.py` first; follow its import and store-access conventions exactly).

Handler in `app.py`:

```python
async def api_waitlist(request: Request):
    """Pro waitlist signups from the pricing page."""
    form = await request.form()
    email = (form.get("email") or "").strip().lower()[:120]
    if (form.get("website") or "").strip():
        return PlainTextResponse("You're on the list.")
    if not ("@" in email and "." in email.rsplit("@", 1)[-1]):
        return PlainTextResponse("Enter a valid email address.",
                                 status_code=400)
    try:
        await watch.add_waitlist_email(email)
    except Exception:  # noqa: BLE001 - no Firestore locally
        return PlainTextResponse("Signups are unavailable right now. "
                                 "Try again later.", status_code=503)
    return PlainTextResponse("You're on the list.")
```

Register the route. Privacy note for the legal audit (Task 14): the waitlist stores email addresses; the privacy page must mention it before Pro marketing goes loud. Add that to the gap list.

- [ ] **Step 3: Run tests and lint, commit, PR**

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check src/ tests/
git add -A && git commit -m "feat: Pro waitlist endpoint"
```

---

### Task 13: Free watch-area size limits

**Files:**
- Modify: `src/ca_roads_demo/watch.py`
- Test: `tests/test_watch.py` (extend)

**Interfaces:**
- Consumes: `api_watch_create` (`watch.py:574`), constants block (`watch.py:60-66`).
- Produces: constants `FREE_MAX_WATCHES = 3`, `FREE_MAX_RADIUS_KM = 40.2`, `FREE_MAX_POLYGON_SQ_KM = 5180.0`, `FREE_MAX_ROUTE_KM = 402.0`, `FREE_MAX_BUFFER_KM = 3.2`; function `polygon_area_sq_km(points) -> float`.

Approved values: 3 areas, circle 25 mi radius (40.2 km), polygon 2,000 sq mi (5,180 sq km), route 250 mi (402 km), buffer 2 mi (3.2 km). The current caps (5 watches, 65 km radius, 800 km route) stay as the technical ceilings; the free limits sit inside them. Existing over-limit watches are grandfathered: limits apply at creation and edit, never retroactively.

- [ ] **Step 1: Write the failing tests**

Extend `tests/test_watch.py` following its existing client/store setup pattern:

```python
def test_free_circle_radius_capped():
    r = _create({"type": "circle", "name": "big",
                 "center": {"lat": 37.0, "lon": -120.0},
                 "radius_km": 41.0})
    assert r.status_code == 400
    assert "free limit" in r.json()["error"]


def test_free_polygon_area_capped():
    # A ~1.0 by 1.0 degree box near 37N is ~9,800 sq km: over the limit.
    big = [[37.0, -120.0], [38.0, -120.0], [38.0, -119.0], [37.0, -119.0]]
    r = _create({"type": "polygon", "name": "big", "points": big})
    assert r.status_code == 400
    assert "free limit" in r.json()["error"]


def test_free_route_length_capped():
    # A straight shot far beyond 402 km.
    pts = [[35.0, -119.0], [40.0, -119.0]]     # ~556 km
    r = _create({"type": "route", "name": "long", "points": pts})
    assert r.status_code == 400
    assert "free limit" in r.json()["error"]


def test_within_limits_still_creates():
    r = _create({"type": "circle", "name": "ok",
                 "center": {"lat": 37.0, "lon": -120.0},
                 "radius_km": 25.0})
    assert r.status_code == 200


def test_polygon_area_math():
    from ca_roads_demo.watch import polygon_area_sq_km
    # 0.1 by 0.1 degree box at 37N: 11.1 km x 8.9 km, about 98 sq km.
    box = [[37.0, -120.0], [37.1, -120.0], [37.1, -119.9], [37.0, -119.9]]
    assert 90 < polygon_area_sq_km(box) < 106
```

Adapt `_create` to however `tests/test_watch.py` already posts watch creations (it has an authenticated-client fixture; reuse it verbatim).

- [ ] **Step 2: Run to verify failure, then implement**

Area function (planar shoelace with latitude correction is accurate to well under a percent at these sizes):

```python
def polygon_area_sq_km(points: list) -> float:
    """Approximate polygon area from [lat, lon] pairs. Planar shoelace
    on a locally scaled grid; plenty accurate at watch-area sizes."""
    import math
    if len(points) < 3:
        return 0.0
    lat0 = sum(p[0] for p in points) / len(points)
    kx = 111.32 * math.cos(math.radians(lat0))   # km per degree lon
    ky = 110.57                                   # km per degree lat
    xs = [(p[1] * kx, p[0] * ky) for p in points]
    s = 0.0
    for (x1, y1), (x2, y2) in zip(xs, xs[1:] + xs[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0
```

In `api_watch_create`, after each shape's existing validation and before the store write, enforce the free limit with the exact error text the tests expect, for example: `_err(f"Circles above {FREE_MAX_RADIUS_KM:.0f} km radius are over the free limit")` (make every message contain the words "free limit"). The count check changes from `MAX_WATCHES` to `FREE_MAX_WATCHES` at creation time only. Route buffer: clamp requests above `FREE_MAX_BUFFER_KM` with the same error, not a silent clamp (a stated limit that silently shrinks is worse than a refusal).

Update the `/api/watch/config` limits payload (`watch.py:498`) so the watch UI can show the real numbers.

- [ ] **Step 3: Check the watch UI**

`watch.html` renders the limits from `/api/watch/config` (verify by reading how `limits` is consumed there). If the buffer slider or radius input allows values above the new free caps, tighten their max attributes to match, so users do not hit API errors for values the UI offered.

- [ ] **Step 4: Full suite, lint, commit, PR**

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check src/ tests/
git add -A && git commit -m "feat: free-tier size limits for watch areas"
```

---

### Task 14: Legal coverage gap analysis

**Files:**
- Create: the legal gap analysis, in the private (gitignored) docs
  directory. Never committed, and not named here: tracked files must not
  reference private paths.

**Interfaces:**
- Consumes: current `/privacy` and `/terms` content; Tailark legal templates; public exemplars.
- Produces: a decision list for Nic. No code.

- [ ] **Step 1: Collect the comparison set**

The Tailark Complete legal and legal-document page templates, plus the public terms and privacy pages of three established SaaS data products (pick ones with safety-adjacent data if possible, for the warranty language).

- [ ] **Step 2: Write the gap analysis**

For each provision found in the comparison set but missing or thin in the current pages, one row: provision, why it matters for CommuteScout specifically, and a proposed one-sentence disposition. Must cover at least: acceptable use, limitation of liability, warranty disclaimer for safety-relevant road data, indemnification, DMCA/IP contact, termination, governing law, changes-to-terms notice, the waitlist email collection (from Task 12), and the contact-form data handling. Note which items CalOPPA already covers.

- [ ] **Step 3: Deliver**

Send the file to Nic with SendUserFile and stop. Content changes to the legal pages happen only after his approval, as their own task in a follow-up plan. This task's deliverable is the analysis, not the edits.

---

### Task 15: Map app light restyle

**Files:**
- Modify: `src/ca_roads_demo/static/map.html`

**Interfaces:**
- Consumes: `tokens.css` (Task 2).
- Produces: the map page referencing the shared tokens and linking the new pages.

- [ ] **Step 1: Adopt the tokens**

Add `<link rel="stylesheet" href="/static/tokens.css">` before the inline styles. Replace the page's own `--navy`, `--navy2`, `--sky`, `--line` custom-property definitions with references to the `--cs-*` names (keep the old names as aliases: `--navy: var(--cs-navy);` and so on) so the several thousand existing usages do not need edits.

- [ ] **Step 2: Navigation alignment**

The map header gains links to the new pages in the same style as the existing nav (Home to `/`, Pricing, plus the existing Watch areas and GitHub). The footer link list adds Pricing, About, and Contact. No layout restructuring: additions slot into the existing header and footer markup.

- [ ] **Step 3: Regression checks**

- Popup rendering: run the states-verify pattern (render one popup per kind through `popupFor` in Playwright, assert no throws or `undefined`).
- Boot: `/map` paints markers with zero console errors, measured with the existing boot harness; the median over 3 runs must be within noise of the pre-change measurement (record both in the PR).
- Visual: screenshot the header and footer at 360 px and 1280 px widths and eyeball them against the marketing pages for token consistency.

- [ ] **Step 4: Full suite, commit, PR**

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check src/ tests/
git add -A && git commit -m "feat: map app adopts shared tokens and site navigation"
```

---

### Task 16: Verification sweep, release, deploy

**Files:**
- Create: verification scripts in scratchpad (not committed)
- Modify: `pyproject.toml`, `server.json` (version bump)

**Interfaces:**
- Consumes: everything above.
- Produces: a released, deployed, verified site.

- [ ] **Step 1: Full-site Playwright sweep (local build first, prod after deploy)**

For every page (`/`, `/pricing`, `/about`, `/contact`, `/privacy`, `/terms`, `/map`, `/watch`): load at 375x812 and 1440x900, assert zero console errors and zero failed requests (excluding the known locally-blocked beacon host), and collect every same-origin `<a href>` and assert each resolves non-404.

- [ ] **Step 2: Form round-trips**

Against a local server: submit the contact form with `CONTACT_EMAIL` set and a monkeypatched send, submit the waitlist form, and assert the success texts render. Honeypot-filled submissions succeed silently without side effects.

- [ ] **Step 3: Map boot unchanged**

Run the boot measurement (snapshot path, painted markers) against `/map` and compare with the recorded pre-project numbers. The repeat-visit median must stay under 300 ms.

- [ ] **Step 4: Lighthouse**

Run Lighthouse (via Playwright's bundled Chromium and the `lighthouse` npm package, or `npx lighthouse`) on the local homepage: performance and accessibility 90 or higher. Fix what fails before shipping; the usual suspects on template pages are image sizing and contrast on muted text.

- [ ] **Step 5: Release and deploy**

Version bump `pyproject.toml` and `server.json` together (minor bump: this is a feature release), release PR, GitHub release, then deploy the demo service with the config-preserving flags plus `--update-env-vars CONTACT_EMAIL=<address Nic provides>`. The MCP service does not need a redeploy unless shared `src/ca_roads` files changed (check the diff).

- [ ] **Step 6: Verify production**

Re-run steps 1 and 3 against `https://commutescout.com`. Confirm `/` serves the homepage with `cf-cache-status` behavior unchanged for APIs, `/map` boots, forms submit (send one real contact message and confirm receipt with Nic), and the sitemap and og cards validate. Record before/after numbers in the release notes.

---

## Self-review notes

- Spec coverage: architecture (Tasks 1-4), URL map and map move (Task 5), pages (Tasks 6-10), endpoints (Tasks 11-12), watch limits (Task 13), legal audit (Task 14), map restyle (Task 15), verification/release (Task 16). Imagery recapture lives in Task 7. Stats drift guard extension lives in Task 7.
- The Task 3 test seam (`/site-preview`) is temporary scaffolding promoted in Task 5; both tasks state it.
- Type consistency: `_site_response(page)`, `SITE_DIR`, `add_waitlist_email`, `polygon_area_sq_km`, and the `FREE_*` constants are named identically everywhere they appear.
- Unit conversions used: 25 mi = 40.2 km, 2,000 sq mi = 5,180 sq km, 250 mi = 402 km, 2 mi = 3.2 km.
