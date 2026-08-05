# SaaS shell redesign

Date: 2026-08-05. Status: approved in discussion, pending final review.

## Overview

CommuteScout's product is a mature live-data map, but the site around it
is not a product website: the map sits at the root URL, there is no
homepage, no pricing page, and the legal pages are bare. This project
builds the professional shell (homepage, pricing, about, contact,
restyled legal pages) and gives the map app a light visual alignment,
without touching its internals.

Paid billing is out of scope. The pricing page presents a Free tier and
a Pro tier marked "coming soon" with an email waitlist. Billing and its
prerequisites are a separate later project.

## Decisions made

| Decision | Choice |
|---|---|
| Map app scope | Keep internals, light restyle only (shared tokens, header, footer) |
| Root URL | Homepage at `/`, map moves to `/map` |
| SaaS depth | Shell plus waitlist; no accounts, no payments |
| Identity | Evolve current: navy and sky palette, Inter, current logo |
| Pages | Home, pricing, about, contact, privacy, terms |
| Pro card content | More and larger watch areas, event history and playback, route briefings and exports |
| Contact | Form that emails through Resend, plus GitHub and security-advisory links |
| Build approach | `site/` workspace: Next.js static export, Tailwind, shadcn/ui, Tailark templates. Starlette serves the exported files. No Node in production. |

## Architecture

### The site workspace

`site/` is a self-contained Node workspace: Next.js with
`output: 'export'`, Tailwind, shadcn/ui, and Tailark Complete templates.
The export writes flat HTML, CSS, and JavaScript to `site/out/`. The
Docker build copies that output into the image's static directory.
Starlette serves the files the same way it serves the current static
pages. Verify current versions and import paths against current docs at
build time (Motion imports from `motion/react`, not `framer-motion`;
confirm the current Tailwind and Next.js majors).

No client-side React ships except where a component needs interactivity.
The waitlist and contact forms are plain form POSTs that work without
JavaScript.

### URL map

| URL | Serves |
|---|---|
| `/` | Homepage (new) |
| `/map` | The map app, unchanged internals |
| `/pricing`, `/about`, `/contact` | New pages |
| `/privacy`, `/terms` | Existing content in the new shell |
| `/watch`, `/trip/*`, admin, all APIs | Untouched |

The map page move is a rename plus link updates, nothing more: same
`FileResponse`, same CSP, same boot-geo data island, same snapshot
preload. Old bookmarks to `/` land on the homepage, which carries a
prominent "Open the map" action. No redirects.

The move touches, and the implementation plan must cover: the
`og`/`ld+json` metadata split (homepage takes the product identity,
`/map` gets its own), `sitemap.xml`, nav links on the watch and trip
pages, and the boot-geo injection point.

## Pages and content

All copy follows the Google developer documentation style guide.
Live-condition strings in the map keep following the road-data copy
spec. Repo-wide rules hold: no em or en dashes, minimal emoji.

**Homepage.** Tailark landing template adapted to the product palette.
Sections: hero (value proposition, live multi-state screenshot, "Open
the map" primary action, waitlist secondary), how it works (map,
planner, ask, alerts), data credibility (53 agency feeds, 38 states,
per-source timestamps; numbers pinned by the existing drift test),
developer band (MCP connector URL, GitHub), footer sitemap. All imagery
is recaptured from the live product, which closes the stale-imagery
backlog item.

**Pricing.** Two cards. Free: full live map, planner, capped assistant,
3 watch areas with the size limits below. Pro (coming soon, waitlist
email field): more and larger watch areas, event history and playback,
route briefings and exports. No price number. The waitlist field says
what it does: "Leave your email and we'll tell you when Pro launches."

**About.** What CommuteScout is, the official-feeds data story, the MIT
core sustainability position from the README, GitHub link.

**Contact.** Form (name, email, message) that emails through Resend.
GitHub issues for bugs; the security advisory link for vulnerabilities.
Honeypot field; rate limited.

**Legal.** The existing reviewed content renders inside the new shell.
Separately, a coverage audit compares the current content against the
Tailark legal templates and several established public SaaS legal pages,
and produces a gap list (acceptable use, liability limits, warranty
disclaimer for safety-relevant data, DMCA, termination, governing law,
changes to terms). Every content change requires Nic's explicit
approval before it ships. Nothing legal ships on the agent's judgment.

## Free watch-area limits

The Free tier gets dimensional limits, enforced server-side in
`watch.py`, not just stated on the pricing page. Today the only
dimensional cap is the 800 km route limit that applies to everyone.

Proposed values, subject to approval at spec review:

| Shape | Free limit |
|---|---|
| Count | 3 watch areas |
| Circle | 25 mi radius |
| Polygon | 2,000 sq mi |
| Route corridor | 250 mi length, 2 mi buffer |

Rules: enforcement returns a clear API error ("This area is larger than
the free limit"). Existing over-limit areas are grandfathered, not
broken. Pro limits lift toward the technical caps and are decided in
the billing project.

## Visual system

One shared token sheet (CSS custom properties: navy and sky palette,
Inter stack, spacing scale) referenced by both the Tailwind config and
the map app's existing CSS. Marketing pages are light-mode-first with
the navy header. The map app restyle is scoped to: adopt the token
sheet, the shared header and nav, and footer links to the new pages. No
layout or interaction changes to the map.

## Server-side additions

Two endpoints, both with honeypot checks, the existing SoftLimit
bucket, and no-JavaScript fallback responses:

- `POST /api/contact`: name, email, message. Emails Nic through the
  existing Resend integration; the destination address lives in an
  environment variable, never in the repo or on the page.
- `POST /api/waitlist`: email only. Writes to a Firestore `waitlist`
  collection with deduplication.

No new secrets. Resend and Firestore access already exist.

## Build pipeline

CI gains a site-build job: Node setup, `npm ci`, static export, output
into the Docker image. A Python test asserts the exported pages exist
and carry the expected routes, so a broken export fails CI instead of
deploying a missing homepage. Local development without Node still runs
the map and APIs; only the marketing pages need the one-time build.

## Verification

- Every page renders in Playwright with zero console errors at mobile
  and desktop widths.
- Contact and waitlist forms round-trip against a local server.
- `/map` boots with markers over the snapshot path, measured with the
  existing boot harness.
- All internal links resolve; og and social cards validate.
- Lighthouse on the homepage: 90 or higher on performance and
  accessibility, measured.

## Out of scope

- Billing, accounts, and payments (separate project, with its own
  prerequisites).
- Map UI redesign beyond the token and header alignment.
- Blog, status page, changelog (revisit after launch).
- Logo redesign.

## Open items for review

1. The Free watch-area limit values in the table above.
2. Legal gap-list findings will come back for approval before any
   content change.
