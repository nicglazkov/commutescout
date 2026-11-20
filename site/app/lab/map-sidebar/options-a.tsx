// Desktop mockups 1-8 (1280 x 800 each).
import {
  ArrowLeft,
  Bell,
  Bookmark,
  Briefcase,
  ChevronDown,
  ChevronRight,
  Clock,
  Crosshair,
  Download,
  Eye,
  House,
  Layers,
  List,
  MessageSquare,
  Navigation,
  Plus,
  Radio,
  Route,
  Send,
  Share2,
  SlidersHorizontal,
} from "lucide-react";
import { MapBg } from "./map-bg";
import {
  Btn,
  Chip,
  Divider,
  EVENTS,
  EventRow,
  FromTo,
  Kicker,
  LayersBtn,
  RouteSummary,
  SearchBox,
  StatusChip,
  TopBar,
  ZoomCtrls,
  cx,
} from "./kit";

export function Screen({ children, top = true }: { children: React.ReactNode; top?: boolean }) {
  return (
    <div className="absolute inset-0 flex flex-col">
      {top ? <TopBar /> : null}
      <div className="relative flex-1 overflow-hidden">{children}</div>
    </div>
  );
}

export function Side({ w = 380, children, className = "" }: { w?: number; children: React.ReactNode; className?: string }) {
  return (
    <div className={cx("absolute bottom-0 left-0 top-0 flex flex-col border-r border-cs-line bg-cs-surface", className)} style={{ width: w }}>
      {children}
    </div>
  );
}

function LeaveRow({ stop = false }: { stop?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <Chip icon={Clock}>
        Leave now <ChevronDown size={13} className="text-cs-ink-3" />
      </Chip>
      {stop ? (
        <span className="ml-auto flex items-center gap-1 text-[12.5px] font-medium text-cs-accent">
          <Plus size={14} /> Add a stop
        </span>
      ) : (
        <span className="text-[12px] text-cs-ink-3">or set a time to leave or arrive</span>
      )}
    </div>
  );
}

function InView({ n = 4, title = "On the map now" }: { n?: number; title?: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <Kicker>{title}</Kicker>
        <span className="font-mono text-[11px] text-cs-ink-3">31 in view</span>
      </div>
      <div className="mt-1 divide-y divide-cs-line">
        {EVENTS.slice(0, n).map((e) => (
          <EventRow key={e.title} {...e} compact />
        ))}
      </div>
      <div className="mt-1 flex items-center gap-1 text-[12.5px] font-medium text-cs-accent">
        See all 31, worst first <ChevronRight size={14} />
      </div>
    </div>
  );
}

/* 1. Where to? ---------------------------------------------------------- */
export function O1() {
  return (
    <Screen>
      <MapBg />
      <Side>
        <div className="flex flex-col gap-3 p-4">
          <div className="text-[19px] font-semibold tracking-[-0.01em]">Where to?</div>
          <FromTo from="Your location" toPlaceholder="Search a place or address" />
          <div className="flex flex-wrap gap-1.5">
            <Chip icon={House}>Home</Chip>
            <Chip icon={Briefcase}>Work</Chip>
            <Chip icon={Crosshair}>Choose on map</Chip>
          </div>
          <LeaveRow stop />
          <Btn primary className="w-full">
            Check the drive
          </Btn>
          <div className="flex items-center gap-2 rounded-[8px] bg-cs-surface-2 px-3 py-2 text-[12.5px] text-cs-ink-2">
            <MessageSquare size={14} /> Or ask in your own words: “Is my drive clear right now?”
          </div>
        </div>
        <Divider />
        <div className="p-4">
          <InView />
        </div>
      </Side>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={396} />
    </Screen>
  );
}

export function O1Result() {
  return (
    <Screen>
      <MapBg route alt traffic focus={[0, 1]} />
      <Side>
        <div className="flex items-center gap-2 border-b border-cs-line px-3 py-2.5">
          <ArrowLeft size={18} className="text-cs-ink-2" />
          <div className="min-w-0 flex-1">
            <div className="font-semibold">Home to Work</div>
            <div className="text-[12px] text-cs-ink-2">Leave now · Fastest</div>
          </div>
          <Btn small icon={SlidersHorizontal}>
            Options
          </Btn>
        </div>
        <div className="flex flex-col gap-2 p-4">
          <RouteSummary />
          <RouteSummary selected={false} alt mins="27 min" />
        </div>
        <div className="px-4">
          <Kicker>On this route, start to finish</Kicker>
          <div className="mt-1 divide-y divide-cs-line">
            <EventRow k="incident" title="Crash blocking right lane" meta="Mile 3.2 · Exit 14 · adds about 4 min" compact />
            <EventRow k="sign" title="Sign: EXPECT DELAYS 20 MIN" meta="Mile 6.0 · read 2 min ago" compact />
            <EventRow k="closure" title="Right lane closed for roadwork" meta="Mile 8.9 · until 3 PM" compact />
          </div>
        </div>
        <div className="mt-auto border-t border-cs-line p-4">
          <div className="flex gap-2">
            <Btn small primary icon={Share2}>
              Share
            </Btn>
            <Btn small icon={Download}>
              GPX, KML, print
            </Btn>
            <Btn small icon={Eye}>
              Watch this route
            </Btn>
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-[8px] border border-cs-line px-3 py-2 text-cs-ink-3">
            <MessageSquare size={14} /> Ask about this drive…
          </div>
        </div>
      </Side>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={396} />
    </Screen>
  );
}

/* 2. Search-first card ---------------------------------------------------- */
export function O2() {
  return (
    <Screen>
      <MapBg />
      <div className="absolute left-4 top-4 flex w-[400px] flex-col gap-2">
        <SearchBox
          float
          placeholder="Search a place, address or question"
          trailing={
            <span className="flex items-center gap-2 border-l border-cs-line pl-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-cs-accent text-cs-accent-ink">
                <Navigation size={15} />
              </span>
            </span>
          }
        />
        <div className="msb-float rounded-[12px] bg-cs-surface p-3">
          <div className="flex gap-1.5 overflow-hidden">
            <Chip tone="closure">3 closures</Chip>
            <Chip tone="incident">18 incidents</Chip>
            <Chip tone="chain">2 chains</Chip>
            <Chip tone="fire">1 fire</Chip>
          </div>
          <div className="mt-2 divide-y divide-cs-line">
            {EVENTS.slice(0, 3).map((e) => (
              <EventRow key={e.title} {...e} compact />
            ))}
          </div>
          <div className="mt-1 flex items-center justify-between text-[12.5px]">
            <span className="font-medium text-cs-accent">Show the full list</span>
            <span className="flex items-center gap-1 text-cs-ink-3">
              <ChevronDown size={14} /> Hide
            </span>
          </div>
        </div>
      </div>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip />
    </Screen>
  );
}

/* 3. Floating panel with your places -------------------------------------- */
function Fav({ icon: I, label, sub }: { icon: typeof House; label: string; sub: string }) {
  return (
    <div className="flex w-[72px] flex-col items-center gap-1 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-full bg-cs-accent-soft text-cs-accent">
        <I size={20} />
      </span>
      <span className="text-[12.5px] font-medium">{label}</span>
      <span className="text-[11px] text-cs-ink-3">{sub}</span>
    </div>
  );
}
export function O3() {
  return (
    <Screen>
      <MapBg />
      <div className="msb-float absolute bottom-3 left-3 top-3 flex w-[360px] flex-col overflow-hidden rounded-[16px] bg-cs-surface">
        <div className="p-3">
          <SearchBox placeholder="Search maps" />
        </div>
        <div className="px-4">
          <div className="flex items-center justify-between">
            <span className="font-semibold">Your places</span>
            <span className="text-[12px] text-cs-accent">Edit</span>
          </div>
          <div className="mt-3 flex justify-between">
            <Fav icon={House} label="Home" sub="Here" />
            <Fav icon={Briefcase} label="Work" sub="24 min" />
            <Fav icon={Bookmark} label="School" sub="12 min" />
            <Fav icon={Plus} label="Add" sub="" />
          </div>
        </div>
        <Divider className="mx-4 mt-3" />
        <div className="px-4 pt-3">
          <span className="font-semibold">Recent</span>
          <div className="mt-1 divide-y divide-cs-line text-[13px]">
            {[
              ["Home to Work", "Yesterday · 26 min"],
              ["the gym", "Mon"],
              ["the airport", "Last week · 41 min"],
            ].map(([a, b]) => (
              <div key={a} className="flex items-center gap-3 py-2.5">
                <span className="grid h-8 w-8 place-items-center rounded-full bg-cs-surface-2 text-cs-ink-2">
                  <Clock size={15} />
                </span>
                <div>
                  <div className="font-medium">{a}</div>
                  <div className="text-[12px] text-cs-ink-2">{b}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <Divider className="mx-4 mt-1" />
        <div className="px-4 pt-3">
          <InView n={2} title="Live near you" />
        </div>
      </div>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={384} />
    </Screen>
  );
}

/* 4. Slim rail, three jobs ------------------------------------------------ */
function RailItem({ icon: I, label, on = false }: { icon: typeof House; label: string; on?: boolean }) {
  return (
    <div className="flex flex-col items-center gap-1 py-2">
      <span className={cx("grid h-9 w-12 place-items-center rounded-full", on ? "bg-cs-accent-soft text-cs-accent" : "text-cs-ink-2")}>
        <I size={19} />
      </span>
      <span className={cx("text-[11px]", on ? "font-semibold text-cs-ink" : "text-cs-ink-2")}>{label}</span>
    </div>
  );
}
export function O4() {
  return (
    <Screen>
      <MapBg />
      <div className="absolute bottom-0 left-0 top-0 flex w-[76px] flex-col items-center border-r border-cs-line bg-cs-surface pt-3">
        <RailItem icon={Route} label="Drive" on />
        <RailItem icon={Radio} label="Live" />
        <RailItem icon={Bookmark} label="Saved" />
        <div className="mt-auto pb-3">
          <RailItem icon={Bell} label="Alerts" />
        </div>
      </div>
      <div className="absolute bottom-0 left-[76px] top-0 flex w-[340px] flex-col gap-3 border-r border-cs-line bg-cs-surface p-4">
        <div className="flex items-center justify-between">
          <span className="text-[17px] font-semibold">Drive</span>
          <span className="text-[12px] text-cs-ink-3">Collapse ‹</span>
        </div>
        <FromTo from="Your location" toPlaceholder="Where to?" />
        <div className="flex flex-wrap gap-1.5">
          <Chip icon={House}>Home</Chip>
          <Chip icon={Briefcase}>Work</Chip>
          <Chip icon={Crosshair}>Choose on map</Chip>
        </div>
        <LeaveRow />
        <Btn primary>Check the drive</Btn>
        <Divider />
        <Kicker>Recent drives</Kicker>
        <div className="text-[13px]">
          <div className="py-1.5">Home to Work · 26 min</div>
          <div className="py-1.5">Home to the airport · 41 min</div>
        </div>
      </div>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={432} />
    </Screen>
  );
}

/* 5. Tabs on top of one panel --------------------------------------------- */
export function O5() {
  const tiles: [string, string, string][] = [
    ["3", "Closures", "text-cs-closure"],
    ["18", "Incidents", "text-cs-incident"],
    ["2", "Chain controls", "text-cs-chain"],
    ["1", "Wildfire", "text-cs-fire"],
    ["46", "Cameras", "text-cs-ink"],
    ["12", "Message signs", "text-cs-stale"],
  ];
  return (
    <Screen>
      <MapBg focus={[0, 1]} />
      <Side w={384}>
        <div className="p-3 pb-0">
          <SearchBox />
          <div className="mt-3 grid grid-cols-3 rounded-[10px] bg-cs-surface-2 p-1 text-center text-[13px]">
            <span className="rounded-[7px] py-1.5 text-cs-ink-2">Directions</span>
            <span className="rounded-[7px] bg-cs-surface py-1.5 font-semibold shadow-[var(--cs-shadow-sm)]">What’s live</span>
            <span className="rounded-[7px] py-1.5 text-cs-ink-2">Saved</span>
          </div>
        </div>
        <div className="p-3">
          <div className="grid grid-cols-3 gap-2">
            {tiles.map(([n, l, c]) => (
              <div key={l} className="rounded-[8px] border border-cs-line p-2.5">
                <div className={cx("font-mono text-[20px] font-medium", c)}>{n}</div>
                <div className="text-[11.5px] text-cs-ink-2">{l}</div>
              </div>
            ))}
          </div>
          <div className="mt-1.5 text-[11.5px] text-cs-ink-3">In the part of the map you can see</div>
        </div>
        <div className="px-3">
          <Kicker>Worst first</Kicker>
          <div className="divide-y divide-cs-line">
            {EVENTS.slice(0, 4).map((e) => (
              <EventRow key={e.title} {...e} compact />
            ))}
          </div>
        </div>
      </Side>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={400} />
    </Screen>
  );
}

/* 6. Live list; the list is the legend ------------------------------------ */
export function O6() {
  return (
    <Screen>
      <MapBg focus={[0]} />
      <Side w={400}>
        <div className="flex flex-col gap-3 p-4 pb-2">
          <div className="flex gap-2">
            <SearchBox className="flex-1" placeholder="Search a place" />
            <span className="grid h-11 w-11 place-items-center rounded-[10px] bg-cs-accent text-cs-accent-ink">
              <Navigation size={17} />
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Chip active>All 31</Chip>
            <Chip tone="closure" active>
              Closures 3
            </Chip>
            <Chip tone="incident" active>
              Incidents 18
            </Chip>
            <Chip tone="chain" active>
              Chains 2
            </Chip>
            <Chip tone="fire" active>
              Fire 1
            </Chip>
            <Chip tone="camera">Cameras</Chip>
            <Chip tone="sign" active>
              Signs 7
            </Chip>
          </div>
          <div className="flex items-center justify-between text-[12px] text-cs-ink-2">
            <span>Worst first · in view</span>
            <span className="flex items-center gap-1">
              Sort <ChevronDown size={12} />
            </span>
          </div>
        </div>
        <div className="flex-1 divide-y divide-cs-line overflow-hidden px-4">
          {EVENTS.slice(0, 6).map((e, i) => (
            <div key={e.title} className={cx(i === 1 && "-mx-4 bg-cs-accent-soft/60 px-4")}>
              <EventRow {...e} right={<ChevronRight size={15} className="mt-2 text-cs-ink-3" />} />
            </div>
          ))}
        </div>
        <div className="border-t border-cs-line px-4 py-2.5 text-[12px] text-cs-ink-2">Tap a chip to show or hide it on the map. Map style ›</div>
      </Side>
      <ZoomCtrls />
      <StatusChip left={416} />
    </Screen>
  );
}

/* 7. Ask first ------------------------------------------------------------ */
export function O7() {
  return (
    <Screen>
      <MapBg route traffic focus={[0]} />
      <Side w={420}>
        <div className="flex items-center justify-between border-b border-cs-line px-4 py-3">
          <span className="font-semibold">Ask about your drive</span>
          <span className="text-[12px] text-cs-accent">Use the form instead</span>
        </div>
        <div className="flex flex-1 flex-col gap-3 p-4">
          <div className="self-end rounded-[12px] rounded-br-[4px] bg-cs-accent px-3 py-2 text-cs-accent-ink">Is my drive to work clear right now?</div>
          <div className="flex items-center gap-1.5 text-[11.5px] text-cs-ink-3">
            <Radio size={12} /> Read the live feeds for your route · 6 s
          </div>
          <div className="rounded-[12px] border border-cs-line p-3">
            <p>
              Mostly. A crash at <b>Exit 14</b> is blocking the right lane, so plan on about <b>24 min</b>, 6 more than usual. Nothing else is
              on the way.
            </p>
            <div className="mt-3">
              <RouteSummary />
            </div>
            <div className="mt-3 flex gap-2">
              <Btn small primary>
                Show route
              </Btn>
              <Btn small>Tell me more</Btn>
            </div>
          </div>
        </div>
        <div className="border-t border-cs-line p-3">
          <div className="mb-2 flex flex-wrap gap-1.5">
            <Chip>Do I need chains today?</Chip>
            <Chip>Best time to leave?</Chip>
          </div>
          <div className="flex h-11 items-center gap-2 rounded-[10px] border border-cs-line-strong px-3">
            <span className="flex-1 text-cs-ink-3">Ask the way you’d say it…</span>
            <span className="grid h-8 w-8 place-items-center rounded-full bg-cs-accent text-cs-accent-ink">
              <Send size={14} />
            </span>
          </div>
        </div>
      </Side>
      <LayersBtn />
      <ZoomCtrls />
    </Screen>
  );
}

/* 8. Bottom command dock -------------------------------------------------- */
export function O8() {
  return (
    <Screen>
      <MapBg />
      <div className="msb-float absolute bottom-[96px] left-1/2 w-[400px] -translate-x-1/2 rounded-[14px] bg-cs-surface p-4">
        <div className="flex items-center justify-between">
          <span className="font-semibold">Directions</span>
          <span className="text-[12px] text-cs-ink-3">Esc to close</span>
        </div>
        <div className="mt-3">
          <FromTo from="Your location" toPlaceholder="Where to?" focusTo />
        </div>
        <div className="mt-2 divide-y divide-cs-line text-[13px]">
          <div className="flex items-center gap-2 py-2">
            <House size={15} className="text-cs-ink-2" /> Home
          </div>
          <div className="flex items-center gap-2 py-2">
            <Briefcase size={15} className="text-cs-ink-2" /> Work
          </div>
          <div className="flex items-center gap-2 py-2 text-cs-accent">
            <Crosshair size={15} /> Choose on map
          </div>
        </div>
      </div>
      <div className="msb-float absolute bottom-6 left-1/2 flex h-14 w-[640px] -translate-x-1/2 items-center gap-1 rounded-[16px] bg-cs-surface p-1.5">
        <SearchBox className="h-11 flex-1 border-transparent bg-cs-surface-2" placeholder="Search" />
        {[
          [Navigation, "Directions", true],
          [List, "Live 31", false],
          [Layers, "Layers", false],
          [MessageSquare, "Ask", false],
        ].map(([I, l, on]) => {
          const Icon = I as typeof House;
          return (
            <span
              key={l as string}
              className={cx("flex h-11 items-center gap-1.5 rounded-[10px] px-3 text-[13px] font-medium", on ? "bg-cs-accent text-cs-accent-ink" : "text-cs-ink")}
            >
              <Icon size={16} /> {l as string}
            </span>
          );
        })}
      </div>
      <ZoomCtrls />
      <StatusChip className="!bottom-auto top-4" />
    </Screen>
  );
}
