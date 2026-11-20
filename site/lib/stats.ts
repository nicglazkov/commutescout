// Coverage numbers surfaced on the homepage (hero subhead and the data
// credibility band, site/app/page.tsx). A single source so the count is
// never hardcoded twice on the page itself.
//
// Keep in sync with tests/test_snapshot.py::test_state_counts_are_current,
// which scans this file alongside src/ca_roads_demo/static/map.html,
// src/ca_roads_demo/prompt.py, src/ca_roads_mcp/server.py, README.md, and
// docs/registry.md, so a coverage change can't drift silently between the
// Python backend and this Next.js site.
export const AGENCY_FEED_COUNT = 54;
export const STATE_COUNT = 37;
// Toll-price feeds (WSDOT toll rates, 511 SF Bay tolls, NTTA, HCTRA and the
// posted Bay Area bridge tolls) are listed on their own, not in the agency
// feed count above: /api/sources shows 59 = 54 agency feeds + these 5.
export const TOLL_FEED_COUNT = 5;
