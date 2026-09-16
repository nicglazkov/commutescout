# Map page: icon rail, one panel, on-demand inspector

Status: direction chosen 2026-09-16 (option C of the sidebar board, plus an
on-demand inspector). Design details below are proposed and await review.

## Goal

Replace the fixed 420 px planner sidebar on `/map` with a narrow icon rail and
one tool panel, move the Layers panel off the map's right edge into the rail,
and give any selected marker a "Show in inspector" action that opens a wider
right-hand pane for the cases a popup cannot hold (camera stills, dispatch
logs, sign boards, chain legends). Popups stay as they are. Phones get a
bottom sheet with the same tools as a tab bar.

Two rules from the owner apply to every part of this: one control per job,
nothing duplicated on web or phone; and the rail and panel are user-resizable
within sane bounds.

## Layout, desktop

```
+------+----------------------+---------------------------------+---------+
| rail | panel (one tool)     | map                             |inspector|
| 64px | 360px, drag 300-520  |                                 | 340px   |
|      |                      |                                 | on      |
|      |                      |                                 | demand  |
+------+----------------------+---------------------------------+---------+
```

- Rail (default 64 px, drag between 56 and 88): five tools, top to bottom:
  Route, Ask, Layers, Watch, Alerts. One is active; clicking the active one
  collapses the panel so the rail alone remains. Below a divider: the sources
  status dot (live from 53 sources) and a Data link. The rail carries the
  navy top-bar color so the page reads as one chrome.
- Panel (default 360 px, drag between 300 and 520 px, never above 40% of the
  viewport): shows the active tool. Width and the last active tool persist in
  `localStorage` per viewer (`cs-rail-w`, `cs-panel-w`, `cs-tool`).
- Map: everything else. The zoom control stays top right. The legend becomes
  a single chip row bottom left (today's floating legend box goes away, since
  the Layers tool also lists every kind with its color: one job, one place).
  The floating Layers panel on the right is removed.
- Inspector (340 px, drag between 300 and 480): opens only from a popup's
  "Show in inspector" button or from an Alerts row. Closes with its own X or
  Escape. On viewports under 1280 px it overlays the map's right edge instead
  of docking.
- Top bar: unchanged. The KPI band under it is removed; its numbers move into
  the Alerts tool header (they were a second summary of what Alerts shows).

## Tools

Route: the planner. Stops (origin, destination, swap, add stop), leave-now
menu, Plan. After planning: alternatives as rows with one condition badge each,
"On the way" as a timeline ordered by distance, a Steps disclosure, and one
actions row (Share, GPX, Print, Clear). Export .txt and KML fold into a Share
menu, since four export buttons did one job.

Ask: the assistant, with a short empty state ("Ask about a drive. Reads the
live feeds.") instead of today's paragraph, the question field, the answer
card, feedback. "Questions people ask about this drive" moves from the Route
panel into Ask as suggestions when a route exists, so they exist in one place.

Layers: today's checkbox groups, moved from the map into the panel, plus the
legend colors inline. "Show all / none" stays.

Watch: the watch-areas flow that lives on `/watch` today, embedded: sign in,
list, draw. The `/watch` page keeps working and links here.

Alerts: what is in the current view right now, worst first, with the counts
that were the KPI band. A row opens the inspector.

## Phone

Bottom sheet with three resting heights (peek, half, full) over an edge-to-edge
map. The sheet's foot is a tab bar with the same five tools; there are no
chips in the peek state, because the tab bar already selects the tool. The
sheet remembers its last height per viewer.

## Inspector content

The 25 popup builders in `map.html` keep rendering popups. Each popup gains one
"Show in inspector" button. The inspector renders the same marker with the
existing builder output in a wider layout plus what the popup cannot hold:
full camera still with refresh, full dispatch log newest first, full sign text
in the amber board style, the R-1/R-2/R-3 legend for chain controls, and the
actions row (Avoid on my route, Share, Watch this stretch). The legal footer
text that lives in the sidebar today moves into an About the data panel
reachable from the rail's Data link.

## What must not change

- Every DOM id and state class the JavaScript reads (about sixty ids, a dozen
  classes, 25 innerHTML builders) keeps its name; new containers wrap them.
- Tests pin: nav hrefs, labels and order, one `aria-label="CommuteScout home"`,
  one Live map link, no "Home" text, exactly one `<header>`, one `<h1>`, the
  `bootgeo` script tag and the exact `requestIdleCallback(run, { timeout: 1000 })`
  string, the `<!--BOOT_GEO-->` slot, privacy and terms text verbatim.
- `/static/tokens.css` keeps `--cs-navy`; new colors are tokens, not hexes.
- The service worker precache list gains any new CSS or JS file.

## Approach

1. Split `map.html`'s CSS into `static/map.css` and its JavaScript into
   modules in dependency order (popups, layers, tolls, refresh, assistant,
   search), unchanged in behavior, one PR, so the redesign edits small files.
2. Rail and panel shell with the drag handles and persistence; Route and Ask
   move in; Layers moves in; legend chip; KPI band removed. Tests updated for
   the new wrappers.
3. Alerts tool and the inspector, with the "Show in inspector" button on
   every popup builder.
4. Phone sheet.
5. Watch tool embedding, last, because it is the only step that touches
   sign-in.

Each step ships as its own PR behind no flag: the page is one file today and
the steps are ordered so every intermediate state is complete.

## Open questions for the owner

1. Rail bounds 56 to 88 px and panel bounds 300 to 520 px (40% of viewport
   max): fine, or different numbers?
2. Fold Export .txt and KML into the Share menu, and the KPI band into the
   Alerts header, as the no-duplicates rule suggests?
3. Watch tool inside the map page in this round, or leave `/watch` separate
   for now and do it later?
4. Inspector: dock at 1280 px and wider, overlay below that?
5. Should the inspector open automatically for kinds that never fit a popup
   (dispatch logs with more than five lines, sign boards), or always be on
   demand?
