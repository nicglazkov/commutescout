import type { Metadata } from "next";
import { BoardHeader, Option, Recommend, SectionHead } from "./board";
import { HeroShell } from "./hero-shell";
import {
  Annotated,
  AssistantChat,
  Checklist,
  CoverageLive,
  Devices,
  ExplodedLayers,
  LiveMiniMap,
  MapTicker,
  NowBoard,
  PhonePair,
  RouteByMile,
  SourceLedger,
  Walkthrough,
  WatchAlert,
} from "./hero-visuals";
import {
  CoverageShell,
  Freshness,
  LayerReach,
  MapReadout,
  Matrix,
  NowByKind,
  ProofMap,
  Ranked,
  SourceTypes,
  StateLookup,
  TileGrid,
  TwoMaps,
} from "./coverage";

// Local-only brainstorm board for the home page (owner notes / #2 and / #3).
export const metadata: Metadata = {
  title: "Lab: Home page (local only)",
  robots: { index: false, follow: false },
};

const HERO = [
  {
    n: "A01",
    name: "Live mini map",
    pick: true,
    idea: "The real US map with every live incident, closure, chain control and wildfire drawn as a dot, and the four counts under it read from /api/stats every 30 s.",
    tradeoff:
      "Feasible on the static export: /api/stats is public, keyless and same-origin. The dots need a light endpoint (lat, lon, kind only); /api/mapdata for the whole country is 7.4 MB, so this board uses a snapshot.",
    el: <LiveMiniMap />,
  },
  {
    n: "A02",
    name: "Product walkthrough",
    idea: "Four tabs that advance on their own: live map, a route by the mile, a watch area alerting, an assistant answering. Hover pauses; any tab can be picked.",
    tradeoff: "Shows the whole product in one spot, but motion in a hero competes with the headline and the first frame is all most people see.",
    el: <Walkthrough />,
  },
  {
    n: "A03",
    name: "Desktop and phone",
    idea: "The live map screenshot with a real CommuteScout Drive screenshot overlapping it, so the hero also answers note 1 (make the app more prominent).",
    tradeoff: "Familiar product-hero pattern and uses real captures; less distinctive than drawing the data itself.",
    el: <Devices />,
  },
  {
    n: "A04",
    name: "Map and a live feed",
    idea: "A cropped map beside a list of what was just reported, newest sliding in on top, each tagged with state, agency and age.",
    tradeoff: "Makes “live” obvious in a second. A real feed needs plain-language event types; agency type strings are messy, so rows here are samples.",
    el: <MapTicker />,
  },
  {
    n: "A05",
    name: "A drive, by the mile",
    idea: "One trip from Home to Work drawn as a strip with each live report pinned to its mile, plus drive time with traffic, typical and free-flow.",
    tradeoff: "Explains what the route planner does better than any map; it is a sample trip, so it says less about scale.",
    el: <RouteByMile />,
  },
  {
    n: "A06",
    name: "Ask your assistant",
    idea: "A short conversation: a question about leaving for the airport, the best_time_to_go call, and the answer typing out once in view.",
    tradeoff: "Leads with the AI angle, which is the most unusual feature. Risks reading as a chatbot product rather than a map.",
    el: <AssistantChat />,
  },
  {
    n: "A07",
    name: "Coverage map with counts",
    idea: "The real US map shaded by how many kinds of report each state publishes, next to live counts.",
    tradeoff: "Answers “does it cover me?” at once; it is a coverage chart, not the product, and it repeats section B.",
    el: <CoverageLive />,
  },
  {
    n: "A08",
    name: "Before-you-go check",
    idea: "The checks a trip runs, as a card: closures, incidents, chain controls, weather alerts, cameras and drive time, each with a plain answer.",
    tradeoff: "Very clear about the outcome a driver gets. Quiet as a visual; it needs the strong headline beside it, which it has.",
    el: <Checklist />,
  },
  {
    n: "A09",
    name: "What the map is made of",
    idea: "The map pulled apart into its layers, each drawn with that layer's real dots: closures, incidents, chain controls, wildfires over the base map. Click to stack them.",
    tradeoff: "Shows literally how separate feeds become one map. The tilted sheets shrink the map, so single states are hard to read.",
    el: <ExplodedLayers />,
  },
  {
    n: "A10",
    name: "Straight from the source, as a ledger",
    idea: "The headline taken literally: each agency, its state, how many items it has now and how many seconds ago it was read, from /api/sources (public, keyless).",
    tradeoff: "Builds trust with developers and careful drivers. Dense, and it shows agency acronyms a casual visitor will not know.",
    el: <SourceLedger />,
  },
  {
    n: "A11",
    name: "The app, three screens",
    idea: "Three real CommuteScout Drive screenshots, staggered: the iPhone map, a hazard warning while driving, the Android map. Every capture shows real streets, so it needs neutral-area recaptures first.",
    tradeoff: "Puts the new app first. The web map, which most visitors will use today, drops out of the hero.",
    el: <PhonePair />,
  },
  {
    n: "A12",
    name: "Right now, in numbers",
    idea: "A dark board of today's live counts in large mono figures, refreshed every 30 s from /api/stats.",
    tradeoff: "Bold and honest, cheap to build. Numbers alone do not show what the product looks like.",
    el: <NowBoard />,
  },
  {
    n: "A13",
    name: "Annotated screenshot",
    idea: "Keep today's screenshot but add four numbered callouts explaining the rail, search, the dots and Report. Hover a number to light its note.",
    tradeoff: "Smallest change from today and teaches the interface. Still one screenshot, which is what the note asks to move beyond.",
    el: <Annotated />,
  },
  {
    n: "A14",
    name: "Watch area alert",
    idea: "A drawn area between Home and School; a new crash appears inside it and a push arrives. Gray reports were there at the first check, so they stay quiet, as watch.py works.",
    tradeoff: "Sells the feature people keep using. It is drawn, not a real map, and only one of four features.",
    el: <WatchAlert />,
  },
];

const COVER = [
  {
    n: "B01",
    name: "Map with a state readout",
    pick: true,
    idea: "The real US map shaded by how many of five kinds each state publishes. Hover or tap a state to list exactly what it has; nationwide layers are noted under it.",
    tradeoff: "Most direct answer to “state by state”. Small eastern states are hard to hit on a phone; pair with a list or select on small screens.",
    el: <MapReadout />,
  },
  {
    n: "B02",
    name: "State by layer matrix",
    idea: "All 37 states against six layers in two compact tables; filled dot for statewide, ring for part of the state.",
    tradeoff: "Complete and scannable for people who look things up. Reads like a spec sheet on a home page.",
    el: <Matrix />,
  },
  {
    n: "B03",
    name: "How far each layer reaches",
    idea: "One bar per layer out of 50 states: three nationwide layers full, then how many states publish incidents, closures, cameras, signs, road weather and chains.",
    tradeoff: "Explains the two-tier coverage in one glance. Does not say which states, only how many.",
    el: <LayerReach />,
  },
  {
    n: "B04",
    name: "State tiles",
    idea: "Every state as an equal tile in a US-shaped grid, shaded by depth; small states are as easy to see and tap as large ones.",
    tradeoff: "Fairer than a geographic map and works on phones. Less recognisable than true shapes.",
    el: <TileGrid />,
  },
  {
    n: "B05",
    name: "Live feed health",
    idea: "Fresh, streaming, stale and down counts from /api/sources, then one chip per feed, by state, colored by status.",
    tradeoff: "Proves the data is current right now. A bad day shows up on the home page too, which is honest but a risk.",
    el: <Freshness />,
  },
  {
    n: "B06",
    name: "Pick your state",
    idea: "“What do I get in [state]?” with a select; the answer lists every layer as yes, partial or no, nationwide layers included.",
    tradeoff: "Personal and accessible on every screen size. Shows one state at a time, so the national picture is lost.",
    el: <StateLookup />,
  },
  {
    n: "B07",
    name: "What kind of sources",
    idea: "A stacked bar of the feeds by type: full DOT feeds, work zone feeds, traffic center feeds, toll prices, national services, with example agencies.",
    tradeoff: "Says where data comes from more than where it covers. The status board lists 58 feed rows against the headline 53 sources; this needs reconciling first.",
    el: <SourceTypes />,
  },
  {
    n: "B08",
    name: "On the map right now",
    idea: "A short table: each kind, whether it comes from the states or nationwide, and how many are on the map this minute.",
    tradeoff: "Replaces the static 53/37/30 s tiles with live, meaningful counts. Little visual weight.",
    el: <NowByKind />,
  },
  {
    n: "B09",
    name: "Where reports are, right now",
    idea: "Every live report as a dot on the real map, with states that only get nationwide layers grayed out.",
    tradeoff: "Most striking and literal. Repeats the hero if A01 is picked.",
    el: <ProofMap />,
  },
  {
    n: "B10",
    name: "States ranked by live items",
    idea: "The twelve states with the most live items from their own agencies, as bars.",
    tradeoff: "Concrete and changes through the day. Rewards big states and says nothing about the 25 others.",
    el: <Ranked />,
  },
  {
    n: "B11",
    name: "Two maps, two tiers",
    idea: "The current copy drawn literally: one map filled for the nationwide layers, one with the 37 states that add their own.",
    tradeoff: "The simplest upgrade from today's chips. Less to explore than B01.",
    el: <TwoMaps />,
  },
];

export default function HomeLab() {
  return (
    <main className="pb-24">
      <BoardHeader
        title="Home page"
        intro={
          <>
            Two notes from the review. Section A replaces the single screenshot in the hero (note 2). Section B
            replaces the stat tiles and chips beside “Clear answers, state by state.” (note 3). Each option is drawn at
            real size inside the real copy. Counts come from the public API: live where marked, otherwise a snapshot
            from 20 Nov 2026.
          </>
        }
      >
        <Recommend
          items={[
            {
              section: "A, hero",
              pick: "A01 Live mini map",
              why: "It is the product, with real data, live counts and no metaphor, and it works on the static export with one small endpoint. Runner-up: A03 desktop and phone, which also lifts the app.",
            },
            {
              section: "B, coverage panel",
              pick: "B01 Map with a state readout",
              why: "A true answer for every state in one figure. If A01 ships, B01's shaded states do not repeat the hero's dots. Simpler fallback: B11 two maps.",
            },
          ]}
        />
        <nav className="mt-6 flex gap-4 text-sm" aria-label="Sections">
          <a className="cs-link" href="#hero">
            A. Hero visual, 14 options
          </a>
          <a className="cs-link" href="#coverage">
            B. Coverage panel, 11 options
          </a>
        </nav>
      </BoardHeader>

      <SectionHead
        id="hero"
        letter="A"
        title="Hero visual"
        note="The left column is today's copy, unchanged. Each option fills the right column at its real width (about 640 px at 1440)."
      />
      {HERO.map((o) => (
        <Option key={o.n} n={o.n} name={o.name} idea={o.idea} tradeoff={o.tradeoff} pick={o.pick} bleed>
          <div className="mx-auto max-w-[1360px] px-4 sm:px-6">
            <HeroShell>{o.el}</HeroShell>
          </div>
        </Option>
      ))}

      <SectionHead
        id="coverage"
        letter="B"
        title="Beside “Clear answers, state by state.”"
        note="Today: three stat tiles (53, 37, 30 s) and two chip lists. Each option replaces both, next to the section's real copy."
      />
      {COVER.map((o) => (
        <Option key={o.n} n={o.n} name={o.name} idea={o.idea} tradeoff={o.tradeoff} pick={o.pick} bleed>
          <div className="mx-auto max-w-[1360px] px-4 sm:px-6">
            <CoverageShell>{o.el}</CoverageShell>
          </div>
        </Option>
      ))}
    </main>
  );
}
