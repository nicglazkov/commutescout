import type { Metadata } from "next";
import "./board.css";
import { Scaled } from "./scaled";
import { Board } from "./board";
import { O1, O1Result, O2, O3, O4, O5, O6, O7, O8 } from "./options-a";
import { O9, O10, O11, O12, O13, O14, O15 } from "./options-b";
import { M1, M1Result, M2, M6, M11, M13 } from "./mobile";
import { P1, P2, P3, P4, P5, P6, P7, PM1, PM2 } from "./pick";

// Local-only brainstorm board (page.lab.tsx is dev-server only).
export const metadata: Metadata = {
  title: "Map sidebar (lab)",
  robots: { index: false, follow: false },
};

type Opt = {
  n: number;
  name: string;
  diff: string;
  idea: string;
  moved: string[];
  plus: string;
  minus: string;
  desk: React.ComponentType;
  desk2?: React.ComponentType;
  phone?: React.ComponentType;
  phone2?: React.ComponentType;
  tag?: string;
};

const OPTIONS: Opt[] = [
  {
    n: 1,
    diff: "Route and Alerts become one panel: a trip form with Home, Work and Choose on map in plain view, the live list under it.",
    name: "Where to?",
    tag: "Top pick",
    idea: "The panel opens on the question people arrive with. Home, Work and Choose on map are chips you can see, not rows hidden until you click an empty field. Under the form: what is live in view. A result replaces the form, with a Back arrow.",
    moved: [
      "Route and Alerts become one panel: form on top, live list below",
      "Ask becomes a line under the form and a box on every result",
      "Layers moves to a button on the map; Watch, Settings and Data go to the avatar menu and the status chip",
      "Report moves to the right-click menu and item popups",
    ],
    plus: "One obvious place to start. Nothing behind tabs. Works the same on a phone as a sheet.",
    minus: "Someone who only wants to browse sees a form first; the live list sits lower in the panel.",
    desk: O1,
    desk2: O1Result,
    phone: M1,
    phone2: M1Result,
  },
  {
    n: 2,
    diff: "No panel. One floating search box with Directions inside it, and a small live card that folds away.",
    name: "Search-first card",
    tag: "Runner-up",
    idea: "One floating search box with the Directions button inside it, the way most people already know from Google Maps. Under it, a small card of what is live, which folds away. The map gets the full width.",
    moved: ["The rail is gone", "From and To open from the search box", "Alerts become the folding card", "Layers, zoom and status float on the map"],
    plus: "The most map. Familiar on day one.",
    minus: "Directions is one click deeper. Floating cards cover more map on a small laptop.",
    desk: O2,
    phone: M2,
  },
  {
    n: 3,
    diff: "Starts from your saved places, each with its live drive time, then recent trips.",
    name: "Your places",
    idea: "A rounded floating panel built around your places: Home, Work and School with a live drive time under each, then recent trips, then what is live near you.",
    moved: ["Saved places get a home (today they are only reachable from the find-box popup)", "Route opens when you tap a place", "Alerts shrink to “Live near you”"],
    plus: "Personal and quick: the drive time is on the button.",
    minus: "Empty on a first visit. Places are per-browser today, so they need sign-in to follow you.",
    desk: O3,
  },
  {
    n: 4,
    diff: "Keeps today’s rail, but seven icon tabs become three words.",
    name: "Slim rail, three jobs",
    idea: "Keep the rail, but cut seven tabs to three words: Drive, Live, Saved, with Alerts at the bottom. The smallest change from today.",
    moved: ["Ask folds into Drive", "Layers moves to the map", "Watch goes under Saved", "Settings and Data go to the avatar menu"],
    plus: "Safe, small, familiar to current users.",
    minus: "Still asks novices to read icons, and the rail costs 76 px of map.",
    desk: O4,
  },
  {
    n: 5,
    diff: "No rail. A three-way switch under the search: Directions, What’s live, Saved.",
    name: "Words, not icons",
    idea: "No rail. A segmented control under the search: Directions, What’s live, Saved. What’s live keeps today’s counts as tiles over a worst-first list.",
    moved: ["Rail becomes three labelled tabs", "Today’s six count tiles stay, in the What’s live tab", "Layers moves to the map"],
    plus: "Plain words. Nothing to guess.",
    minus: "Tabs still split one job in three, and each tab hides the other two.",
    desk: O5,
  },
  {
    n: 6,
    diff: "The live list is the panel, and its filter chips replace the Layers tab.",
    name: "The list is the legend",
    idea: "The panel is the live list, worst first. The filter chips are the layer switches, with counts. Hover a row and its marker rings on the map. One Directions button.",
    moved: ["Layers, Alerts and the missing legend merge into the chips", "Map style moves to a link at the foot", "Route opens from the Directions button"],
    plus: "One control set instead of three. The list always matches the map.",
    minus: "Directions becomes secondary. On a busy day the list is long.",
    desk: O6,
    phone: M6,
  },
  {
    n: 7,
    diff: "You ask in your own words first; the form is one link away.",
    name: "Ask first",
    idea: "The panel is a conversation about your drive. The answer comes with the route and a summary card. The form is one link away.",
    moved: ["Ask becomes the front door", "The route form becomes “Use the form instead”", "Suggested questions sit above the input"],
    plus: "Shows what CommuteScout does that others do not. Natural for people who would rather say it.",
    minus: "Answers take 5 to 15 seconds and cost a request each. Harder to scan than a list.",
    desk: O7,
  },
  {
    n: 8,
    diff: "No sidebar. A dock at the bottom centre opens each tool as a card.",
    name: "Bottom dock",
    idea: "No sidebar. A dock at the bottom centre holds Search, Directions, Live, Layers and Ask. Each opens a card just above it.",
    moved: ["Every rail tab becomes a dock button", "Status moves to the top left"],
    plus: "Full-width map and one row of clear words.",
    minus: "Cards open over the middle of the map. Unusual for a desktop map.",
    desk: O8,
  },
  {
    n: 9,
    diff: "Search on the left, the details of whatever you click on the right.",
    name: "Details on the right",
    idea: "Search floats on the left. What you click opens on the right: today’s inspector promoted to the main panel, with the camera, the facts and the actions.",
    moved: ["The inspector becomes the panel", "Directions is a mode of the search box", "Alerts become “Also near here”"],
    plus: "Rich details without covering the place you clicked.",
    minus: "Chrome on both sides. On phones it collapses to the same sheet anyway.",
    desk: O9,
  },
  {
    n: 10,
    diff: "A guided path, one question per screen, with big targets.",
    name: "One question at a time",
    idea: "A short guided path: where from, where to, when. Big targets, plain words, a progress bar. Each step offers Home, Work, a recent place and “Point to it on the map”.",
    moved: ["The route form becomes three steps", "Everything else floats on the map"],
    plus: "The hardest design to get lost in. Good for first visits and for older users.",
    minus: "Slow for daily users; needs a “show the whole form” switch.",
    desk: O10,
  },
  {
    n: 11,
    diff: "A results view: the route drawn as a straight strip, each event at its mile.",
    name: "The route as a strip",
    idea: "A results view: the route straightened into a strip from Home (mile 0) to Work, each event placed at its mile and the line coloured by speed. Arrival weather at the end.",
    moved: ["“Conditions on this route” becomes the strip", "Alternatives become chips", "Exports go behind Share"],
    plus: "Unique to CommuteScout and readable at a glance. The MCP plan_trip tool already returns events by mile.",
    minus: "A results state, not a whole sidebar. The web route list is flat today (items within 0.35 km), so it needs the by-mile data.",
    desk: O11,
    phone: M11,
  },
  {
    n: 12,
    diff: "Almost nothing on screen. One search pill opens a palette that does everything.",
    name: "Command palette",
    idea: "Almost no chrome. A small search pill opens a palette (⌘K) that does everything: directions, places, layers, watch, ask.",
    moved: ["Every tab becomes a command", "Keyboard shortcuts for layers and directions"],
    plus: "Fast for keyboard users and regulars.",
    minus: "Invisible to novices. It needs a visible panel anyway.",
    desk: O12,
  },
  {
    n: 13,
    diff: "The signed-in start page: your usual drives with their live status.",
    name: "Your drives",
    idea: "The signed-in start page: your saved drives with live status, then watched areas with alerts. Plan something new from the search.",
    moved: ["Watch moves out of a tab into “Watched areas”", "Alerts attach to the drive or area they belong to", "Saved drives replace Home/Work quick picks"],
    plus: "Answers “is my commute OK?” with no typing.",
    minus: "Needs sign-in and saved drives; a first visit still needs the form from 1.",
    desk: O13,
    phone: M13,
  },
  {
    n: 14,
    diff: "One floating sheet with three heights, the same on desktop and phone.",
    name: "One sheet, three heights",
    idea: "The panel is a floating sheet with three heights (compact, medium, full) on every screen. Desktop and phone share one component and one set of moves.",
    moved: ["The sidebar becomes a sheet on desktop too", "Compact shows only search and chips"],
    plus: "One thing to learn on every device. Compact frees the map.",
    minus: "Dragging a sheet with a mouse is unusual; it needs size buttons as well.",
    desk: O14,
  },
  {
    n: 15,
    diff: "From, To and Leave in a bar across the top of the map, like a flight search.",
    name: "Drive bar on top",
    idea: "From, To and Leave sit in a bar across the top of the map, like a flight search. A results drawer slides in from the left only after you search.",
    moved: ["The route form becomes a top bar", "Results get a drawer that can hide", "Saved moves to the bar’s right end"],
    plus: "The form never hides; the map is full until there is something to show.",
    minus: "Costs height on short laptop screens. The live list has no home until a search.",
    desk: O15,
  },
];

const PICK: { id: string; title: string; body: string; c: React.ComponentType; phone?: boolean }[] = [
  { id: "a", title: "Start from the field", body: "Focus To and the list shows Your location, Home, Work and Choose on map before you type. The same chip sits under the fields.", c: P1 },
  { id: "b", title: "Armed: say what to do, show how to stop", body: "Dark banner with the instruction, a Cancel button and the Esc key. The field reads “Choosing on map…”. A ghost pin follows the pointer and a dot shows where it will snap to the road.", c: P2 },
  { id: "c", title: "Too far out? Zoom first", body: "At state zoom one click cannot mean one street. The first click zooms in around that spot; the second click picks.", c: P3 },
  { id: "d", title: "Drop, then confirm", body: "The pin lands where it snapped. The card names the place, not coordinates. Drag the pin or click elsewhere to move it. Set as destination, Enter, or Cancel.", c: P4 },
  { id: "e", title: "Done, with Undo", body: "The field shows the place name, the route plans as soon as both ends are set, and a toast offers Undo for a few seconds.", c: P5 },
  { id: "f", title: "Right-click or press and hold", body: "A short menu at the point: directions from or to here, what’s here, report, watch, copy coordinates.", c: P6 },
  { id: "g", title: "When the spot is wrong", body: "Water, a field, or no road nearby: say so in words and offer the nearest road. Never route to a point we cannot reach without saying.", c: P7 },
  { id: "h", title: "Phone: the pin stays still", body: "The map moves under a fixed centre pin, the place name updates when the map stops, and one big button sets it. No precise tap needed.", c: PM1, phone: true },
  { id: "i", title: "Phone: press and hold", body: "Holding for half a second drops a pin and opens a sheet with the same actions as the right-click menu.", c: PM2, phone: true },
];

const ZONES: { n: number; x: number; y: number; t: string }[] = [
  { n: 1, x: 200, y: 108, t: "Panel: the trip form, then what is live in view" },
  { n: 2, x: 300, y: 196, t: "Home, Work, Choose on map as visible chips" },
  { n: 3, x: 1180, y: 112, t: "Layers and legend: a map button with a popover" },
  { n: 4, x: 1200, y: 600, t: "Locate me and zoom" },
  { n: 5, x: 470, y: 716, t: "Freshness and sources" },
  { n: 6, x: 1236, y: 64, t: "Avatar: Saved, Watch, alerts, settings, sign in" },
  { n: 7, x: 900, y: 380, t: "Right-click or press and hold anywhere: directions from or to here, report, watch" },
];

function Zones() {
  return (
    <div className="absolute inset-0">
      <O1 />
      {ZONES.map((z) => (
        <span
          key={z.n}
          className="absolute grid h-8 w-8 place-items-center rounded-full bg-cs-ink text-[14px] font-semibold text-cs-bg ring-4 ring-cs-accent/40"
          style={{ left: z.x, top: z.y }}
        >
          {z.n}
        </span>
      ))}
    </div>
  );
}

const WHERE: [string, string, string][] = [
  ["One search box", "Top of the panel", "One place to start. It turns into From and To, and a typed question goes to Ask."],
  ["From, To, swap, stops, leave time", "Panel", "The main job, so it gets the room."],
  ["Home, Work, Your location, Choose on map", "Chips under the fields and first rows of the list", "Seen before typing. Today they only appear when an empty field is focused."],
  ["Route results and conditions on the route", "Panel, replacing the form, with Back", "The answer appears where the question was asked."],
  ["What is live in view", "Panel, under the form", "Answers “is anything going on?” without a tab."],
  ["Ask", "Inside the search box and on each result", "A way to ask, not a place to go."],
  ["Layers and legend", "Map button, top right: popover on desktop, sheet on phone", "It changes the map, so it lives on the map. A badge shows how many are off."],
  ["Zoom, locate me", "Map, bottom right", "Where everyone looks for them. Locate does not exist today."],
  ["Freshness and sources", "Status chip, bottom left of the map", "Always visible. Opens the sources list and the legal notes (today’s Data tab)."],
  ["Report a problem", "Right-click menu, item popups, a small map button", "A report is about a point on the map."],
  ["Directions from or to here, What’s here, Watch this area", "Right-click and press-and-hold menu", "A shortcut. Each item is also reachable another way."],
  ["Watch areas and alerts inbox", "Saved, from the avatar (or option 13)", "Personal, signed-in things together."],
  ["Sign in, units, theme, API keys, delete account", "Avatar menu, then a settings page", "Rarely changed. Sign-in leaves the Watch tab."],
  ["Details of a clicked item", "Panel on desktop (Back returns), sheet on phone", "One panel, one history. No third column."],
];

function TodaySection() {
  return (
      <section>
        <h2 className="text-2xl font-semibold">The map today</h2>
        <p className="mt-2 max-w-3xl text-cs-ink-2">Read from map.html, map-app.js, map-assistant.js and watch-app.js. Everything a visitor can touch, grouped by where it lives now.</p>
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[
            ["Top bar", "Site links, “live from 53 sources in 37 states” (opens a source status panel), “Data as of 3:42 PM” (amber at 2 min, red at 15), version."],
            ["Rail (7 tabs)", "Route, Ask, Layers, Watch, Alerts; Settings and Data at the bottom. Clicking the open tab folds the panel. Panel and rail are drag-resizable."],
            ["Route", "From, To, a small “Pick on map” link on each, Plan route, Depart now or later. Results: Fastest, No highways, Avoid tolls, Shortest, Avoid chains; up to 3 routes; ETA vs free-flow; stops (map clicks, max 5); Share link; GPX, KML, text, print; turn-by-turn; conditions on the route; 4 question chips."],
            ["Ask", "One input, “How’s my drive looking right now?”, a streamed answer with the steps it took, Tell me more, thumbs. No example questions on a first open."],
            ["Layers", "Everything / Official only / Plugins only; Show all or none; incidents (4), closures (4), winter and weather, wildfire, tolls, traffic overlay, plugins, cameras, message signs; 5 map styles."],
            ["Watch (trial)", "Sign-in lives here (Google or email link). Access code. New watch: circle, polygon or route; name; incidents, closures, chain controls, wildfires; push or email. Your watches, this device."],
            ["Alerts", "“Live right now”: 6 counts and an in-view list, worst first, up to 60."],
            ["Settings and Data", "Miles or kilometres, account, API keys, delete account. Data is the legal and attribution text."],
            ["On the map", "Find box, zoom, Report (top right), the pick hint, a loading pill, item popups, a right-hand inspector (show on map, copy link, watch this stretch). No locate, no legend, no right-click menu."],
            ["Phone (≤ 960 px)", "The rail becomes a 7-tab bottom bar. The panel becomes a sheet: peek 84 px, half, full, moved by its handle only."],
          ].map(([h, b]) => (
            <div key={h} className="rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface p-4">
              <div className="font-semibold">{h}</div>
              <p className="mt-1 text-sm text-cs-ink-2">{b}</p>
            </div>
          ))}
        </div>
        <h3 className="mt-10 text-lg font-semibold">What gets in the way</h3>
        <ol className="mt-3 grid list-decimal gap-2 pl-5 text-cs-ink-2 md:grid-cols-2 md:gap-x-10">
          <li>
            <b className="text-cs-ink">Pick on map</b> is an 11 px text link. There is no Cancel button (only Esc or a second click, and neither is shown). One click
            commits with no chance to adjust. The result is a raw “Pin 12.345 / -67.890”: no place name, and that string ends up in share links and GPX files.
          </li>
          <li>
            <b className="text-cs-ink">Route form</b>: no swap, no clear button, “Use my location” only appears as a hidden row in From, Home and Work only show once
            you focus an empty field, and Plan route can fail without saying why.
          </li>
          <li>
            <b className="text-cs-ink">Depart later</b> looks like a routing input but only changes the conditions list, not the route or the drive time.
          </li>
          <li>
            <b className="text-cs-ink">Two search boxes</b> (find box on the map, From and To in the panel) do related jobs.
          </li>
          <li>
            <b className="text-cs-ink">Seven tabs for four jobs.</b> “Alerts” means what is live, while Watch is what sends alerts. “Data” is a legal page. Sign-in
            hides inside Watch.
          </li>
          <li>
            <b className="text-cs-ink">Layers</b>: the traffic legend is three disabled checkboxes, there is no legend, and nothing on the map says which layers are
            off once the panel is closed.
          </li>
          <li>
            <b className="text-cs-ink">Ask chips</b> under a route send the question to the Ask tab even when that tab is hidden, so the answer can be invisible.
          </li>
          <li>
            <b className="text-cs-ink">Nothing in the URL</b>: a reload loses the planned route. No right-click menu, no keyboard shortcuts, no first-visit help.
          </li>
        </ol>
      </section>

  );
}

function OthersSection() {
  return (
      <section>
        <h2 className="text-2xl font-semibold">How other maps do it</h2>
        <p className="mt-2 max-w-3xl text-cs-ink-2">
          From product help pages, design guidance, Mobbin flows and screens, and beginner tutorials on YouTube. Where a detail could not be confirmed it is left
          out.
        </p>
        <div className="mt-6 overflow-x-auto rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface">
          <table className="min-w-[860px] text-sm">
            <thead>
              <tr>
                <th>Product</th>
                <th>Panel</th>
                <th>Directions</th>
                <th>Pointing at the map</th>
                <th>Layers and phone</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Google Maps (web)", "One search box top left that grows into the panel", "Directions button in the box; type, pick a place, or click the map; Add destination (up to 9 stops, drag to reorder); Leave now, Depart at, Arrive by", "Click points on the map to fill From and To; drag the route to reshape it", "Layers in a corner control; on phones a floating Layers button and nonmodal sheets that fold to the bottom"],
                ["Apple Maps (web beta since July 2024, iOS app)", "Floating sidebar: search, guides, directions", "From and To stacked with drag handles; Now and Prefer as chips; Leave at or Arrive by", "Press and hold drops a pin on phones", "Sheets with medium and large heights; map usable behind the medium height"],
                ["Waze Live Map", "Search box first", "Find a place, click Directions, set both points, then pick a time", "A point with no road nearby routes to the nearest road", "Traffic colours on the line"],
                ["OpenStreetMap.org", "Directions panel", "A to B", "Right-click or press and hold: Directions from here, Directions to here, Show address, Centre map here", "Layers in a side control"],
                ["Komoot (route planner)", "Planner panel", "Waypoints list", "Each click adds the next waypoint after the current end", "Map styles in a picker"],
                ["State DOT traffic maps", "Menus over the map", "Usually none", "Click an icon for a dialog", "Layer checkboxes in an Options menu"],
                ["Freenow, Gojek, Uber-style apps", "Sheet", "Where to? with Home, Work chips", "Choose on map: fixed centre pin, map moves under it, address updates, Confirm", "Map type sheet with two picture tiles"],
              ].map((r) => (
                <tr key={r[0]}>
                  {r.map((c, i) => (
                    <td key={i} className={i === 0 ? "font-medium" : "text-cs-ink-2"}>
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-8 grid gap-8 md:grid-cols-2">
          <div>
            <h3 className="text-lg font-semibold">What the guidance says</h3>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-cs-ink-2">
              <li>Bottom sheets: keep a visible Close as well as the handle; nonmodal when small, modal only when full; quick tasks only (NN/g).</li>
              <li>Sheets have medium and large heights, with the map still usable behind the medium one (Apple HIG).</li>
              <li>The map click can never be the only way: offer a single-pointer and a keyboard path, such as typing the address (WCAG 2.5.1, 2.1.1).</li>
              <li>Tap-to-drop-a-pin with no mode drew complaints when Google Maps shipped it on phones; an armed mode with a visible Cancel avoids stray pins.</li>
              <li>With a fixed centre pin, lock the centre while pinching, and keep the address text in step with the pin: people who cannot see the map rely on the words.</li>
              <li>Beginner tutorials pick the destination by clicking the map, and note that a searched pin is “sometimes a bit hard to spot”.</li>
            </ul>
          </div>
          <div>
            <h3 className="text-lg font-semibold">Mobbin references used</h3>
            <ul className="mt-3 space-y-2 text-sm">
              {[
                ["Choose on map, then confirm destination (Freenow, iOS)", "https://mobbin.com/flows/5a3fe97e-3857-49e5-a7f3-87fb0479d6e2"],
                ["Select via map chip, Home and Work chips, centre pin (Gojek, iOS)", "https://mobbin.com/flows/a92b32ec-ebeb-443c-8909-d953205f6a2b"],
                ["Crosshair picker with Select and a search bar (Polarsteps, iOS)", "https://mobbin.com/flows/d6c67c83-fa3c-48f1-a50e-97cad3ab3adc"],
                ["Set on map from the destination search (Waymo, iOS)", "https://mobbin.com/flows/3bd4f2fc-c239-43ef-a67a-8bb2b25bd0a7"],
                ["Choose drop-off with snapped road options (Waymo, iOS)", "https://mobbin.com/screens/3f7e3869-2582-4814-b87b-1f44cf9f85da"],
                ["Setting a depart or arrive time (Google Maps, iOS)", "https://mobbin.com/flows/cc8bf59c-89b1-44c8-8f90-292d2542c526"],
                ["Directions with stops and drag handles (Google Maps, iOS)", "https://mobbin.com/screens/ff95f1f9-8b5f-40f0-a94b-f240b3f65f29"],
                ["Map type sheet with two picture tiles (Airbnb, iOS)", "https://mobbin.com/screens/7649086b-2efc-45f0-9126-c14a124d060c"],
                ["Planning a route in a bottom sheet (Mercedes-Benz, iOS)", "https://mobbin.com/flows/5e1bb19e-5b7e-41da-a880-2708fbc5ab90"],
              ].map(([t, u]) => (
                <li key={u}>
                  <a href={u} className="text-cs-accent underline-offset-4 hover:underline" target="_blank" rel="noreferrer">
                    {t}
                  </a>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-cs-ink-3">Full notes and source links: reports/commutescout-2026-11/map-sidebar-research.md</p>
          </div>
        </div>
      </section>

  );
}

function WhereSection() {
  return (
      <section>
        <h2 className="text-2xl font-semibold">What goes where</h2>
        <p className="mt-2 max-w-3xl text-cs-ink-2">
          The rule: the sidebar holds the trip and what you are looking at. Things that change the map live on the map. Personal and rare things live behind the
          avatar. Shortcuts never hold the only way to do something.
        </p>
        <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <figure>
            <Scaled w={1280} h={800} label="Option 1 with seven numbered zones showing where each control lives.">
              <Zones />
            </Scaled>
            <figcaption className="mt-3 grid gap-1.5 text-sm text-cs-ink-2 sm:grid-cols-2">
              {ZONES.map((z) => (
                <span key={z.n} className="flex gap-2">
                  <span className="font-mono text-cs-ink">{z.n}</span> {z.t}
                </span>
              ))}
            </figcaption>
          </figure>
          <div className="overflow-x-auto rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface">
            <table className="text-sm">
              <thead>
                <tr>
                  <th>Thing</th>
                  <th>Lives in</th>
                  <th>Why</th>
                </tr>
              </thead>
              <tbody>
                {WHERE.map(([a, b, c]) => (
                  <tr key={a}>
                    <td className="font-medium">{a}</td>
                    <td>{b}</td>
                    <td className="text-cs-ink-2">{c}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

  );
}

function PickSpec() {
  return (
        <div className="overflow-x-auto rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface">
          <table className="min-w-[760px] text-sm">
            <thead>
              <tr>
                <th className="w-[180px]">Part</th>
                <th>Spec</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Ways in", "Choose on map chip under the fields; the same row in the From and To list; right-click or press and hold; dragging the start or end pin; “Directions to here” in any popup. Report uses the same machinery with its own banner."],
                ["Armed mode", "Banner: “Click the map to set where you’re going” (or “your start”, “a stop”, “where the problem is”). Cancel button and Esc shown. Field outlined and reading “Choosing on map…”. Crosshair cursor. Popups do not open while armed. On phones the sheet drops to its smallest height."],
                ["Aim", "A ghost pin follows the pointer. A dot shows the snap point on the nearest drivable road within about 60 m (the report flow already snaps with /api/snap). Hovering over water or a field shows no dot."],
                ["Zoom guard", "Below street-level zoom, the first click zooms in around that spot (banner says so); only a click at street level drops the pin."],
                ["Drop and confirm", "The pin drops with a short settle (no bounce when reduced motion is on). Card on the pin: “Finding the address…”, then a place name such as “Near Exit 14” and the road and distance. Set as destination (Enter) or Cancel. Drag the pin, or click elsewhere, to move it; the name updates."],
                ["Done", "Field shows the place name (never raw coordinates; if no name is found, “Point on the map” with coordinates in the details). Route plans as soon as both ends are set. Toast “Destination set · Undo” for 6 seconds. The pin stays draggable."],
                ["Ways out", "Esc, the banner’s Cancel, the card’s Cancel, clicking the field, the panel’s Back. The previous value comes back. Nothing is changed until Set."],
                ["Touch", "Centre-pin mode: the map moves under a fixed pin; the name updates when the map stops; one large Set button. Centre locked while pinching. A touch that moves more than about 8 px is a pan, never a pick. Press and hold (500 ms) opens the action sheet."],
                ["Keyboard and screen readers", "In armed mode a crosshair shows at the map centre; arrow keys pan, plus and minus zoom, Enter drops the pin there. The mode, the found name and the result are read out in a polite live region. Typing an address always works and is offered first."],
                ["Errors", "No road nearby: “No road at that spot. The nearest road is 0.3 mi away.” with Use the nearest road. Outside coverage: allow it, and say “No live data here yet”. Name lookup fails: keep the point and say the name could not be found. Offline: keep the banner and say the point will be set when back online."],
              ].map(([a, b]) => (
                <tr key={a}>
                  <td className="font-medium">{a}</td>
                  <td className="text-cs-ink-2">{b}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
  );
}

const dk = (o: Opt, C: React.ComponentType, extra = "") => (
  <Scaled w={1280} h={800} label={`Option ${o.n}, ${o.name}, desktop${extra}`}>
    <C />
  </Scaled>
);
const ph = (o: Opt, C: React.ComponentType, extra = "") => (
  <Scaled w={390} h={844} label={`Option ${o.n}, ${o.name}, on a phone${extra}`} className="rounded-[22px]">
    <C />
  </Scaled>
);

export default function MapSidebarBoard() {
  return (
    <Board
      options={OPTIONS.map((o) => ({
        n: o.n,
        name: o.name,
        tag: o.tag,
        diff: o.diff,
        idea: o.idea,
        moved: o.moved,
        plus: o.plus,
        minus: o.minus,
        desk: dk(o, o.desk),
        desk2: o.desk2 ? dk(o, o.desk2, ", with a route planned") : undefined,
        phone: o.phone ? ph(o, o.phone) : undefined,
        phone2: o.phone2 ? ph(o, o.phone2, ", with a route planned") : undefined,
      }))}
      steps={PICK.map((p, i) => ({
        id: p.id,
        letter: String.fromCharCode(65 + i),
        title: p.title,
        body: p.body,
        phone: !!p.phone,
        node: p.phone ? (
          <Scaled w={390} h={844} label={p.title} className="rounded-[22px]">
            <p.c />
          </Scaled>
        ) : (
          <Scaled w={800} h={520} label={p.title}>
            <p.c />
          </Scaled>
        ),
      }))}
      today={<TodaySection />}
      others={<OthersSection />}
      where={<WhereSection />}
      pickSpec={<PickSpec />}
    />
  );
}
