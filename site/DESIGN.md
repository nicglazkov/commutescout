# CommuteScout site design system ("Clear Coat")

Design read: a product site for drivers and developers that reads official
road data. Light, clear, calm and precise. Navy ink, one blue accent, a
fixed set of semantic colors for road events, a grotesk for words and a
mono for data. Light and dark are both first-class.

All tokens live in `app/globals.css`. Style only with them.

## Theme

- Light by default. With no stored choice the OS setting wins
  (`prefers-color-scheme`), so the page is right with JavaScript off.
- An inline script in `app/layout.tsx` sets `<html data-theme="light|dark">`
  before first paint (stored key: `localStorage["cs-theme"]`). The header
  switch changes it. `data-theme` beats the media query both ways.
- Tailwind `dark:` follows `data-theme="dark"`. Prefer tokens over `dark:`;
  tokens already flip.

## Color tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--cs-bg` | #f5f7fa | #0a111b | Page background |
| `--cs-surface` | #ffffff | #111a26 | Cards, panels, figure frames |
| `--cs-surface-2` | #eef2f7 | #172231 | Raised or alternate rows, hover fills |
| `--cs-inset` | #e7ecf3 | #0d1520 | Wells, code, sunken areas |
| `--cs-ink` | #0b1a2c | #e6edf5 | Headings, body |
| `--cs-ink-2` | #475569 | #a3b2c4 | Secondary text (7.6:1 / 8.1:1) |
| `--cs-ink-3` | #5f6e82 | #8091a6 | Labels, captions (4.8:1 / 5.4:1, AA) |
| `--cs-line` | #e1e7ef | #223042 | Hairlines, borders |
| `--cs-line-strong` | #c9d3df | #33445b | Inputs, emphasized rules |
| `--cs-accent` | #1a63d6 | #5b9cff | The one action color, links |
| `--cs-accent-hover` | #1555bb | #7aafff | Hover on accent fills |
| `--cs-accent-ink` | #ffffff | #06101e | Text on the accent (5.5:1 / 7:1) |
| `--cs-accent-soft` | #e8f0fd | #14284a | Selected chips, soft highlights |

Semantic (each with a `-soft` fill; every base value is AA as text on
`--cs-surface` in its theme). Hues match the live map's families.

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `--cs-incident` | #ab4d0d | #f0914f | Crashes, hazards, patrol log entries |
| `--cs-closure` | #a1262e | #ff8a8f | Full, lane and ramp closures |
| `--cs-chain` | #4053a8 | #98a6f0 | Chain controls |
| `--cs-fire` | #946200 | #e3b341 | Wildfire perimeters and points |
| `--cs-weather` | #0e7480 | #4cc2c9 | Road weather, NWS alerts |
| `--cs-ok` | #1a774f | #4fc98e | Fresh feed, success |
| `--cs-stale` | #6b5b95 | #b4a5e0 | A feed past its stale limit |

Dark band (developer section, footer; stays dark in both themes):
`--cs-band`, `--cs-band-2`, `--cs-band-ink`, `--cs-band-ink-2`, `--cs-band-line`.

Rules: the accent points at one action or one highlight per viewport.
Semantic colors only ever mean their road event; never decorate with them.

Legacy aliases kept for older markup: `--cs-navy` (= band), `--cs-navy2`,
`--cs-sky` (= accent), `--cs-paper` (= surface), `--cs-font`. shadcn slots
(`--background`, `--primary`, `--muted`, `--border`, `--ring`, ...) are
mapped onto the tokens, so `components/ui` and `bg-primary` style classes
keep working.

Tailwind utilities exist for every token: `bg-cs-surface`, `text-cs-ink-2`,
`border-cs-line`, `bg-cs-closure-soft`, `text-cs-accent`, etc.

## Type

- **Geist** (UI and display) and **Geist Mono** (data), self-hosted with
  `next/font/google` (`--font-geist`, `--font-geist-mono`), `display: swap`.
  `--cs-font-sans` and `--cs-font-mono` wrap them with system fallbacks.
- Why: a neutral, engineered grotesk that holds up at 68 px and at 13 px,
  with a sibling mono drawn on the same skeleton, so timestamps, counts and
  URLs read as data without a second personality. Two families, three
  weights (400, 500, 600).
- Utilities in `globals.css`:
  - `cs-display` hero heading: clamp(40px..68px), 1.02, -0.035em, 600
  - `cs-h2` section heading: clamp(28px..40px), 1.08, -0.028em, 600
  - `cs-h3` item heading: 17px, 1.4, 600
  - `cs-lede` intro paragraph: 17-19px, 1.6, ink-2
  - `cs-eyebrow` mono label: 12px, uppercase, 0.08em, ink-3
  - `cs-data` mono, tabular numbers
  - `cs-link` inline link with a quiet underline
- Body 16px / 1.6 on marketing pages; measure 60-70 characters.

## Shape, depth, motion

- Radius: `--cs-radius-sm` 6px (chips, inputs), `--cs-radius-md` 10px
  (buttons, small cards), `--cs-radius-lg` 16px (panels, figure frames).
- Depth comes from hairlines and tone first. `--cs-shadow-sm` for resting
  panels, `--cs-shadow-md` only for things that float (menus, the hero
  figure).
- Motion: `--cs-ease` cubic-bezier(.22,1,.36,1); `--cs-dur-fast` 150ms
  (hover, press), `--cs-dur` 260ms (menus), `--cs-dur-slow` 520ms
  (entrances). `cs-rise` is the one entrance. Everything is disabled under
  `prefers-reduced-motion`.

## Layout

- `cs-container`: 1200px content, 20px gutter on phones, 32px from 768px.
- Section rhythm: 96-128px between sections on desktop, 64-72px on phones.
- Asymmetric splits (7/5, 5/7) over centered stacks. Hairline rules and
  mono labels make the grid visible.

## Accessibility

- WCAG 2.2 AA: every text token is checked at 4.5:1 or better on its
  surface. Focus is a 2px accent outline, offset 2px, on every control.
- Targets are at least 44px on touch layouts.
- Every figure has a meaningful static state without JavaScript.
