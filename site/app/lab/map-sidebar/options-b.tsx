// Desktop mockups 9-15 (1280 x 800 each).
import {
  ArrowLeft,
  ArrowLeftRight,
  ArrowRight,
  Bell,
  Bookmark,
  Briefcase,
  Camera,
  ChevronDown,
  ChevronRight,
  Clock,
  Command,
  CornerDownLeft,
  Crosshair,
  Eye,
  House,
  Layers,
  MapPin,
  MessageSquare,
  Navigation,
  Play,
  Plus,
  Route,
  Search,
  Share2,
  X,
} from "lucide-react";
import { MapBg } from "./map-bg";
import { Screen, Side } from "./options-a";
import {
  Btn,
  Chip,
  Divider,
  EVENTS,
  EventRow,
  Kicker,
  KindIcon,
  LayersBtn,
  RouteSummary,
  SearchBox,
  StatusChip,
  ZoomCtrls,
  cx,
} from "./kit";

/* 9. Search left, inspector right ----------------------------------------- */
export function O9() {
  return (
    <Screen>
      <MapBg focus={[0]} />
      <div className="absolute left-4 top-4 w-[360px]">
        <SearchBox
          float
          trailing={
            <span className="grid h-8 w-8 place-items-center rounded-full bg-cs-accent text-cs-accent-ink">
              <Navigation size={15} />
            </span>
          }
        />
      </div>
      <div className="absolute bottom-0 right-0 top-0 flex w-[380px] flex-col border-l border-cs-line bg-cs-surface">
        <div className="flex items-start gap-3 border-b border-cs-line p-4">
          <KindIcon k="incident" size={36} />
          <div className="flex-1">
            <div className="text-[16px] font-semibold">Crash blocking right lane</div>
            <div className="text-[12.5px] text-cs-ink-2">Interstate eastbound at Exit 14</div>
          </div>
          <X size={18} className="text-cs-ink-3" />
        </div>
        <div className="flex flex-col gap-3 p-4">
          <dl className="grid grid-cols-[110px_1fr] gap-y-1.5 text-[13px]">
            <dt className="text-cs-ink-2">Reported</dt>
            <dd>8:02 AM · 12 min ago</dd>
            <dt className="text-cs-ink-2">Lanes</dt>
            <dd>Right lane blocked</dd>
            <dt className="text-cs-ink-2">Source</dt>
            <dd>State highway patrol log</dd>
          </dl>
          <div className="relative h-[150px] overflow-hidden rounded-[10px] bg-cs-band">
            <svg viewBox="0 0 340 150" className="absolute inset-0 h-full w-full" aria-hidden="true">
              <path d="M120 150 L165 40 H175 L220 150 Z" fill="#2a3a4c" />
              <path d="M170 150 V44" stroke="#c9d3df" strokeDasharray="8 8" strokeWidth="2" />
              <rect x="0" y="0" width="340" height="40" fill="#1b2a3a" />
            </svg>
            <span className="absolute left-2 top-2 flex items-center gap-1 rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-white">
              <Camera size={11} /> Exit 14 · live
            </span>
            <span className="absolute inset-0 m-auto grid h-10 w-10 place-items-center rounded-full bg-white/90 text-cs-band">
              <Play size={16} />
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Btn small primary icon={Navigation}>
              Directions to here
            </Btn>
            <Btn small icon={Eye}>
              Watch this stretch
            </Btn>
            <Btn small icon={Share2}>
              Copy link
            </Btn>
            <Btn small>Report a change</Btn>
          </div>
        </div>
        <Divider />
        <div className="p-4">
          <Kicker>Also near here</Kicker>
          <EventRow {...EVENTS[5]} compact />
        </div>
      </div>
      <LayersBtn className="!right-[396px]" />
      <ZoomCtrls className="!right-[396px]" />
      <StatusChip />
    </Screen>
  );
}

/* 10. One question at a time ---------------------------------------------- */
export function O10() {
  const opts: [typeof House, string, string][] = [
    [House, "Home", "Saved place"],
    [Briefcase, "Work", "Saved place"],
    [Clock, "the gym", "You went here Monday"],
    [Crosshair, "Point to it on the map", "Click where you’re going"],
  ];
  return (
    <Screen>
      <MapBg />
      <Side w={420}>
        <div className="p-5">
          <div className="flex items-center gap-2">
            {[1, 2, 3].map((s) => (
              <span key={s} className={cx("h-1.5 flex-1 rounded-full", s <= 2 ? "bg-cs-accent" : "bg-cs-line")} />
            ))}
          </div>
          <div className="mt-2 font-mono text-[11px] uppercase tracking-[0.1em] text-cs-ink-3">Step 2 of 3</div>
          <div className="mt-1 text-[24px] font-semibold tracking-[-0.015em]">Where are you going?</div>
          <div className="mt-1 text-[14px] text-cs-ink-2">Starting from your location. Change</div>
          <div className="mt-4 flex h-12 items-center gap-2 rounded-[10px] border-2 border-cs-accent px-3 text-[15px] text-cs-ink-3">
            <Search size={17} /> Type a place or address
          </div>
          <div className="mt-4 flex flex-col gap-2">
            {opts.map(([I, a, b]) => (
              <div key={a} className="flex items-center gap-3 rounded-[10px] border border-cs-line p-3">
                <span className="grid h-10 w-10 place-items-center rounded-full bg-cs-surface-2 text-cs-ink-2">
                  <I size={18} />
                </span>
                <div className="flex-1">
                  <div className="text-[15px] font-medium">{a}</div>
                  <div className="text-[12.5px] text-cs-ink-2">{b}</div>
                </div>
                <ChevronRight size={18} className="text-cs-ink-3" />
              </div>
            ))}
          </div>
        </div>
        <div className="mt-auto flex justify-between border-t border-cs-line p-4">
          <Btn icon={ArrowLeft}>Back</Btn>
          <span className="self-center text-[12.5px] text-cs-ink-3">Next: when are you leaving?</span>
        </div>
      </Side>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={436} />
    </Screen>
  );
}

/* 11. The route as a strip, start to finish ------------------------------- */
const STRIP: { mi: string; k?: Parameters<typeof KindIcon>[0]["k"]; title: string; meta: string; seg?: string }[] = [
  { mi: "0", title: "Home", meta: "Leave 8:10 AM" },
  { mi: "3.2", k: "incident", title: "Crash, right lane blocked", meta: "Exit 14 · adds about 4 min", seg: "bg-cs-closure" },
  { mi: "6.0", k: "sign", title: "Sign: EXPECT DELAYS 20 MIN", meta: "read 2 min ago", seg: "bg-cs-fire" },
  { mi: "8.9", k: "closure", title: "Right lane closed, roadwork", meta: "until 3 PM", seg: "bg-cs-ok" },
  { mi: "9.5", k: "camera", title: "Camera at the bridge", meta: "Live video", seg: "bg-cs-ok" },
  { mi: "11.2", title: "Work", meta: "Arrive about 8:34 AM · light rain", seg: "bg-cs-ok" },
];
export function StripList({ big = false }: { big?: boolean }) {
  return (
    <div className="relative">
      {STRIP.map((s, i) => (
        <div key={s.mi} className="relative flex gap-3" style={{ minHeight: big ? 64 : 58 }}>
          <div className="w-12 shrink-0 whitespace-nowrap pt-1.5 text-right font-mono text-[11px] text-cs-ink-3">mi {s.mi}</div>
          <div className="relative flex w-5 shrink-0 justify-center">
            {i < STRIP.length - 1 ? <span className={cx("absolute top-3 bottom-[-6px] w-[5px] rounded-full", STRIP[i + 1].seg)} /> : null}
            {s.k ? (
              <span className="relative z-10 mt-0.5">
                <KindIcon k={s.k} size={20} />
              </span>
            ) : (
              <span className={cx("relative z-10 mt-1.5 h-3.5 w-3.5 rounded-full", i === 0 ? "border-[3px] border-cs-ink bg-cs-surface" : "bg-cs-closure")} />
            )}
          </div>
          <div className="min-w-0 flex-1 pb-3">
            <div className="font-medium">{s.title}</div>
            <div className="text-[12px] text-cs-ink-2">{s.meta}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
export function O11() {
  return (
    <Screen>
      <MapBg route traffic focus={[0, 1]} />
      <Side w={400}>
        <div className="flex items-center gap-2 border-b border-cs-line px-3 py-2.5">
          <ArrowLeft size={18} className="text-cs-ink-2" />
          <div className="flex-1">
            <div className="font-semibold">Home to Work</div>
            <div className="text-[12px] text-cs-ink-2">
              <span className="font-medium text-cs-incident">24 min</span> · 11.2 mi · 6 min slower than usual
            </div>
          </div>
          <Btn small icon={Clock}>
            Leave now
          </Btn>
        </div>
        <div className="flex gap-1.5 px-4 pt-3">
          <Chip active>Fastest · 24 min</Chip>
          <Chip>Via Main St · 27 min</Chip>
        </div>
        <div className="px-4 pt-4">
          <StripList />
        </div>
        <div className="mt-auto flex items-center gap-3 border-t border-cs-line px-4 py-3 text-[12px] text-cs-ink-2">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-4 rounded-full bg-cs-ok" /> moving
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-4 rounded-full bg-cs-fire" /> slow
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-4 rounded-full bg-cs-closure" /> stop and go
          </span>
          <span className="ml-auto text-cs-accent">Share ›</span>
        </div>
      </Side>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={416} />
    </Screen>
  );
}

/* 12. Command palette ----------------------------------------------------- */
export function O12() {
  const groups: [string, [typeof House, string, string?][]][] = [
    ["Directions", [[Route, "Home to Work", "Enter"]]],
    ["Places", [[MapPin, "Work"], [MapPin, "Exit 14"]]],
    ["Map", [[Layers, "Show cameras"], [Eye, "Watch this area"]]],
    ["Ask", [[MessageSquare, "“how's the drive home to work”"]]],
  ];
  return (
    <Screen>
      <MapBg />
      <div className="absolute inset-0" style={{ background: "var(--m-scrim)" }} />
      <div className="msb-float absolute left-4 top-4 flex h-10 items-center gap-2 rounded-full bg-cs-surface px-3 text-cs-ink-3">
        <Search size={15} /> Search or do anything
        <span className="msb-kbd">⌘K</span>
      </div>
      <div className="msb-float absolute left-1/2 top-[90px] w-[580px] -translate-x-1/2 overflow-hidden rounded-[14px] bg-cs-surface">
        <div className="flex h-14 items-center gap-3 border-b border-cs-line px-4 text-[16px]">
          <Search size={18} className="text-cs-ink-3" />
          <span>home to work</span>
          <span className="h-5 w-px bg-cs-ink" />
          <span className="ml-auto msb-kbd">Esc</span>
        </div>
        <div className="p-2">
          {groups.map(([g, rows], gi) => (
            <div key={g} className="pb-1">
              <div className="px-2 pb-1 pt-2 font-mono text-[10.5px] uppercase tracking-[0.1em] text-cs-ink-3">{g}</div>
              {rows.map(([I, l, k], ri) => (
                <div key={l} className={cx("flex h-10 items-center gap-3 rounded-[8px] px-2", gi === 0 && ri === 0 && "bg-cs-accent-soft")}>
                  <I size={16} className="text-cs-ink-2" />
                  <span>{l}</span>
                  {k ? (
                    <span className="ml-auto flex items-center gap-1 text-[12px] text-cs-ink-3">
                      <CornerDownLeft size={13} />
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          ))}
        </div>
        <div className="flex gap-4 border-t border-cs-line px-4 py-2 text-[11.5px] text-cs-ink-3">
          <span>
            <span className="msb-kbd">↑</span> <span className="msb-kbd">↓</span> move
          </span>
          <span>
            <span className="msb-kbd">Enter</span> open
          </span>
          <span className="flex items-center gap-1">
            <Command size={12} /> L layers · D directions
          </span>
        </div>
      </div>
      <ZoomCtrls />
    </Screen>
  );
}

/* 13. My drives ----------------------------------------------------------- */
function Drive({ name, when, status, tone }: { name: string; when: string; status: string; tone: "ok" | "warn" }) {
  return (
    <div className="rounded-[10px] border border-cs-line p-3">
      <div className="flex items-center justify-between">
        <span className="font-semibold">{name}</span>
        <span className="text-[12px] text-cs-ink-3">{when}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <span className={cx("rounded-full px-2 py-0.5 text-[12px] font-medium", tone === "ok" ? "bg-cs-ok-soft text-cs-ok" : "bg-cs-incident-soft text-cs-incident")}>
          {status}
        </span>
        <ArrowRight size={15} className="ml-auto text-cs-ink-3" />
      </div>
    </div>
  );
}
export function O13() {
  return (
    <Screen>
      <MapBg route focus={[0]} />
      <Side w={392}>
        <div className="p-4 pb-3">
          <SearchBox placeholder="Search or plan a new drive" />
        </div>
        <div className="flex flex-col gap-2 px-4">
          <div className="flex items-center justify-between">
            <span className="text-[15px] font-semibold">Your drives</span>
            <span className="text-[12px] text-cs-ink-3">Checked 30 s ago</span>
          </div>
          <Drive name="Home to Work" when="Weekdays 8:10 AM" status="24 min · 1 crash on the way" tone="warn" />
          <Drive name="Work to Home" when="Weekdays 5:30 PM" status="Clear · 21 min now" tone="ok" />
          <Drive name="Home to School" when="Weekdays 7:40 AM" status="Clear · 12 min now" tone="ok" />
          <span className="flex items-center gap-1.5 py-1 text-[13px] font-medium text-cs-accent">
            <Plus size={15} /> Add a drive
          </span>
        </div>
        <Divider className="mt-2" />
        <div className="px-4 pt-3">
          <div className="flex items-center justify-between">
            <span className="text-[15px] font-semibold">Watched areas</span>
            <span className="flex items-center gap-1 text-[12px] text-cs-ink-2">
              <Bell size={13} /> Alerts on
            </span>
          </div>
          <div className="mt-1 divide-y divide-cs-line">
            <EventRow k="camera" title="Around Home · 2 mi" meta="Quiet · nothing new today" compact />
            <EventRow k="closure" title="The pass" meta="1 closure since 6:10 AM" compact />
          </div>
        </div>
      </Side>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={408} />
    </Screen>
  );
}

/* 14. One sheet, three heights, on every screen --------------------------- */
export function O14() {
  return (
    <Screen>
      <MapBg />
      {/* the three stops, drawn as a scale beside the sheet */}
      <div className="absolute bottom-3 left-[396px] top-3 w-px bg-cs-accent/60" />
      {[
        ["Compact", 72],
        ["Medium", 440],
        ["Full", 690],
      ].map(([l, y]) => (
        <span key={l as string} className="absolute left-[390px] flex items-center gap-2" style={{ top: (y as number) - 4 }}>
          <span className="h-[9px] w-[13px] rounded-full border-2 border-cs-accent bg-cs-surface" />
          <span className="rounded bg-cs-accent px-1.5 py-0.5 font-mono text-[10.5px] text-cs-accent-ink">{l as string}</span>
        </span>
      ))}
      <div className="msb-float absolute left-3 top-3 flex h-[440px] w-[372px] flex-col overflow-hidden rounded-[16px] bg-cs-surface">
        <div className="p-3">
          <SearchBox />
          <div className="mt-2.5 flex gap-1.5">
            <Chip icon={House}>Home</Chip>
            <Chip icon={Briefcase}>Work</Chip>
            <Chip icon={Crosshair}>Choose on map</Chip>
          </div>
        </div>
        <Divider />
        <div className="px-4 pt-2">
          {EVENTS.slice(0, 4).map((e) => (
            <EventRow key={e.title} {...e} compact />
          ))}
        </div>
        <div className="mt-auto flex items-center justify-between border-t border-cs-line px-3 py-2 text-[12px] text-cs-ink-2">
          <span>Drag the edge, or</span>
          <span className="flex rounded-[7px] bg-cs-surface-2 p-0.5">
            <span className="rounded-[5px] px-2 py-0.5">Compact</span>
            <span className="rounded-[5px] bg-cs-surface px-2 py-0.5 font-medium text-cs-ink shadow-[var(--cs-shadow-sm)]">Medium</span>
            <span className="rounded-[5px] px-2 py-0.5">Full</span>
          </span>
        </div>
      </div>
      <LayersBtn />
      <ZoomCtrls />
      <StatusChip left={430} />
    </Screen>
  );
}

/* 15. Drive bar across the top -------------------------------------------- */
export function O15() {
  return (
    <Screen>
      <MapBg route alt focus={[0, 1]} />
      <div className="absolute left-0 right-0 top-0 flex items-center gap-2 border-b border-cs-line bg-cs-surface px-4 py-2.5">
        <div className="flex h-10 w-[260px] items-center gap-2 rounded-[8px] border border-cs-line px-3">
          <span className="h-3 w-3 rounded-full border-[3px] border-cs-ink" /> Home
        </div>
        <span className="grid h-8 w-8 place-items-center rounded-full border border-cs-line text-cs-ink-2">
          <ArrowLeftRight size={14} />
        </span>
        <div className="flex h-10 w-[260px] items-center gap-2 rounded-[8px] border border-cs-line px-3">
          <span className="h-3 w-3 rounded-full bg-cs-closure" /> Work
        </div>
        <Chip icon={Clock}>
          Leave now <ChevronDown size={13} />
        </Chip>
        <Chip icon={Plus}>Stop</Chip>
        <Btn primary className="ml-1">
          Check the drive
        </Btn>
        <span className="ml-auto flex items-center gap-2 text-cs-ink-2">
          <Bookmark size={16} /> Saved
        </span>
      </div>
      <div className="absolute bottom-0 left-0 top-[61px] flex w-[360px] flex-col border-r border-cs-line bg-cs-surface">
        <div className="flex items-center justify-between px-4 pt-3">
          <Kicker>2 routes</Kicker>
          <span className="flex items-center gap-1 text-[12px] text-cs-ink-3">
            Hide <ChevronDown size={13} className="rotate-90" />
          </span>
        </div>
        <div className="flex flex-col gap-2 p-4 pt-2">
          <RouteSummary />
          <RouteSummary selected={false} alt mins="27 min" />
        </div>
        <div className="px-4">
          <Kicker>On the fastest route</Kicker>
          <EventRow k="incident" title="Crash blocking right lane" meta="Mile 3.2 · Exit 14" compact />
          <EventRow k="closure" title="Right lane closed, roadwork" meta="Mile 8.9 · until 3 PM" compact />
        </div>
      </div>
      <LayersBtn className="!top-[77px]" />
      <ZoomCtrls />
      <StatusChip left={376} />
    </Screen>
  );
}

