import type { Metadata } from "next";
import { BoardHeader, Option, Recommend } from "../home/board";
import {
  M10MapCards,
  M11StatusRows,
  M1FilterBar,
  M2KindColour,
  M3IconTiles,
  M4Featured,
  M5ViewToggle,
  M6MasterDetail,
  M7Sidebar,
  M8Matrix,
  M9Shelves,
} from "./options";

// Local-only brainstorm board for /marketplace (review note /marketplace #1:
// "more colours, or more filters, let's brainstorm"). Every option renders the
// real catalog from plugins-snapshot.ts; M11 also reads the live endpoint.
export const metadata: Metadata = {
  title: "Lab: Marketplace (local only)",
  robots: { index: false, follow: false },
};

export default function MarketplaceLab() {
  return (
    <main className="pb-24">
      <BoardHeader
        title="Marketplace"
        intro={
          <>
            Eleven ways to browse plugins, with more colour, more filters, or both. Every mockup uses the real catalog:
            two listed plugins today, one approved (speed and red light cameras) and one community relay, not reviewed.
          </>
        }
      >
        <Recommend
          items={[
            {
              section: "now, with 2 plugins",
              pick: "09 Trust shelves, with 02's kind colours on the chips",
              why: (
                <>
                  With two plugins a filter bar filters nothing. The one choice that matters today is trust, so split the page by it
                  and let the alert-kind chips carry the colour, in the map&rsquo;s own hues.
                </>
              ),
            },
            {
              section: "later, at about 6+ plugins",
              pick: "01 Filter bar above the shelves",
              why: (
                <>
                  Add the trust and &ldquo;Shows&rdquo; chips once there is something to narrow. 07 (sidebar) is the step after that, at
                  15 or more. 06&rsquo;s detail panel is worth keeping in mind for the capabilities list either way.
                </>
              ),
            },
          ]}
        />
      </BoardHeader>

      <Option
        n="01"
        name="Filter bar with counts"
        idea="Chip rows for trust, what it shows and what it can do, each with a live count. The list narrows as you tap, with a clear-filters link and an empty state."
        tradeoff="The most familiar pattern and it scales well, but with two plugins most chips return the same one or two cards."
      >
        <M1FilterBar />
      </Option>

      <Option
        n="02"
        name="Colour by alert kind"
        idea="Each card opens with a thin strip split by the kinds it sends, and a grid of kind tiles in the live map's colours. Police, jams and cameras have no road-event colour, so they stay neutral with an icon."
        tradeoff="Adds colour that means something and matches the map legend. A plugin with many kinds (the relay sends 24) gets busy; the strip keeps it scannable."
      >
        <M2KindColour />
      </Option>

      <Option
        n="03"
        name="App-store icon tiles"
        idea="Square tiles with a big kind icon on its own tint, the name, operator and trust, plus a dashed tile that invites people to write one."
        tradeoff="Feels like a store and fits many plugins per row. Hides the description, so it needs a detail view (06) behind each tile."
      >
        <M3IconTiles />
      </Option>

      <Option
        n="04"
        name="Featured banner and a list"
        idea="One approved plugin gets a wide banner with its coverage map and numbers. Everything else follows as a compact list."
        tradeoff="Gives the page a strong first screen. With two plugins the list repeats the banner, so it only pays off once the catalog grows."
      >
        <M4Featured />
      </Option>

      <Option
        n="05"
        name="List and cards toggle"
        idea="A dense table (trust, kinds as icons, coverage, alerts now, refresh) with a switch to cards. Developers and people comparing can scan columns."
        tradeoff="Most information per pixel. The table needs a horizontal scroll on phones, so phones would default to cards."
      >
        <M5ViewToggle />
      </Option>

      <Option
        n="06"
        name="List with a detail panel"
        idea="Plugins on the left, the selected one in full on the right: every alert kind code, what it can do (alerts, reports, confirm, notify, snapshot), version, protocol, refresh, last answer."
        tradeoff="Answers every question without leaving the page. Heavier than the rest, and on phones the panel becomes a separate screen."
      >
        <M6MasterDetail />
      </Option>

      <Option
        n="07"
        name="Sidebar categories and search"
        idea="A left rail with All, Approved, Community and Installed here, then one entry per alert kind with counts. Search sits over the results."
        tradeoff="Built for a big catalog and familiar from integration directories. Today it is mostly empty rail and two results."
      >
        <M7Sidebar />
      </Option>

      <Option
        n="08"
        name="Plugin by alert-kind matrix"
        idea="Rows are plugins, columns are alert kinds, each hit a coloured dot with how many kinds it sends in that group. Answers “who shows police?” at a glance."
        tradeoff="Honest and literal. Reads as a comparison table, not a store, so it works best as a second view rather than the page."
      >
        <M8Matrix />
      </Option>

      <Option
        n="09"
        name="Trust shelves"
        pick
        idea="Two shelves: Reviewed by CommuteScout, then Community, not reviewed, with the install notice set beside the community plugins instead of under every card. Kind chips carry the colour."
        tradeoff="Puts the one decision that matters first and keeps the warning in one place. Adds no filtering, which is fine until the catalog grows."
      >
        <M9Shelves />
      </Option>

      <Option
        n="10"
        name="Coverage map cards"
        idea="Each card leads with the real US outline filled by the plugin's coverage box, the alerts-now count and how often it refreshes."
        tradeoff="Visual and literal about where it works. Both current plugins cover the whole country, so today the two maps look the same."
      >
        <M10MapCards />
      </Option>

      <Option
        n="11"
        name="Live status rows"
        idea="A status-page list: fresh, stale or offline, alerts now and refresh, read live from /api/flare/sources in the browser."
        tradeoff="Shows plugins are running, not just listed. An hourly plugin reads stale for most of each hour (the 15-minute rule), which may worry people."
      >
        <M11StatusRows />
      </Option>
    </main>
  );
}
