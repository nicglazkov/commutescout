// Pick-on-map storyboard: each frame is a crop of the desktop map
// (800 x 520) or a phone (390 x 844).
import {
  Briefcase,
  Clock,
  Copy,
  Crosshair,
  Eye,
  House,
  Info,
  LocateFixed,
  MousePointer2,
  Navigation,
  TriangleAlert,
  Undo2,
  X,
  ZoomIn,
} from "lucide-react";
import { MapBg, PinA, PinB } from "./map-bg";

const P5_ROUTE = "M560 610 V490 C640 500 700 478 760 474 C790 472 815 470 838 466";
import { Phone, Sheet } from "./mobile";
import { Btn, FromTo, RouteSummary, cx } from "./kit";

const VB = "330 200 800 520"; // world crop shown in desktop frames
const OX = 330;
const OY = 200;
const PANEL = 300;
// Frame px for a world point (panel overlaps the left 300 px of the crop).
const fx = (x: number) => x - OX;
const fy = (y: number) => y - OY;

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="absolute bottom-0 left-0 top-0 flex flex-col gap-3 border-r border-cs-line bg-cs-surface p-3.5" style={{ width: PANEL }}>
      {children}
    </div>
  );
}

function Banner({ children, tone = "accent" }: { children: React.ReactNode; tone?: "accent" | "warn" }) {
  return (
    <div
      className={cx(
        "msb-float absolute top-3 flex h-10 -translate-x-1/2 items-center gap-2.5 whitespace-nowrap rounded-full pl-3.5 pr-1.5 text-[13px] font-medium",
        tone === "accent" ? "bg-cs-ink text-cs-bg" : "bg-cs-closure text-white",
      )}
      style={{ left: PANEL + (800 - PANEL) / 2 }}
    >
      {children}
    </div>
  );
}

function BannerCancel() {
  return (
    <span className="flex h-7 items-center gap-1.5 rounded-full bg-white/15 px-2.5 text-[12px]">
      Cancel <span className="rounded border border-white/40 px-1 font-mono text-[10px]">Esc</span>
    </span>
  );
}

export function P1() {
  return (
    <div className="absolute inset-0">
      <MapBg viewBox={VB} />
      <Panel>
        <FromTo from="Your location" focusTo toPlaceholder="Search a place or address" />
        <div className="msb-float -mt-1 overflow-hidden rounded-[10px] border border-cs-line bg-cs-surface text-[13px]">
          {[
            [LocateFixed, "Your location", ""],
            [House, "Home", "Saved"],
            [Briefcase, "Work", "Saved"],
            [Crosshair, "Choose on map", "Click a spot"],
            [Clock, "the gym", "Recent"],
          ].map(([I, a, b], i) => {
            const Icon = I as typeof House;
            return (
              <div key={a as string} className={cx("flex h-10 items-center gap-2.5 px-3", i === 3 && "bg-cs-accent-soft text-cs-accent")}>
                <Icon size={15} className={i === 3 ? "" : "text-cs-ink-2"} />
                <span className="font-medium">{a as string}</span>
                <span className="ml-auto text-[11.5px] text-cs-ink-3">{b as string}</span>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

export function P2() {
  // cursor off the road, snap point on the interstate
  const cur = { x: 860, y: 520 };
  const snap = { x: 838, y: 466 };
  return (
    <div className="absolute inset-0" style={{ cursor: "crosshair" }}>
      <MapBg viewBox={VB}>
        <path d={`M${cur.x} ${cur.y} L${snap.x} ${snap.y}`} style={{ stroke: "var(--cs-accent)", strokeWidth: 1.5, strokeDasharray: "3 4" }} />
        <circle cx={snap.x} cy={snap.y} r="7" style={{ fill: "var(--cs-accent)", stroke: "#fff", strokeWidth: 2.5 }} />
        <PinB x={snap.x} y={snap.y} ghost />
        <g transform={`translate(${cur.x} ${cur.y})`} style={{ stroke: "var(--cs-ink)", strokeWidth: 1.5 }}>
          <path d="M-12 0 H-4 M4 0 H12 M0 -12 V-4 M0 4 V12" />
        </g>
      </MapBg>
      <span
        className="absolute rounded bg-cs-surface px-1.5 py-0.5 text-[11px] text-cs-ink-2 shadow-[var(--cs-shadow-sm)]"
        style={{ left: fx(cur.x) + 14, top: fy(cur.y) + 8 }}
      >
        Snaps to the nearest road
      </span>
      <Panel>
        <FromTo from="Your location" pickingTo />
        <div className="text-[12px] text-cs-ink-2">Click the map. You can adjust the spot before it is set.</div>
      </Panel>
      <Banner>
        <Crosshair size={15} /> Click the map to set where you’re going <BannerCancel />
      </Banner>
    </div>
  );
}

export function P3() {
  return (
    <div className="absolute inset-0">
      <MapBg viewBox="-260 -180 2000 1300" labels={false}>
        <circle cx="900" cy="420" r="120" style={{ fill: "var(--cs-accent)", opacity: 0.12, stroke: "var(--cs-accent)", strokeWidth: 4 }} />
      </MapBg>
      <span className="absolute grid h-9 w-9 place-items-center rounded-full bg-cs-accent text-cs-accent-ink" style={{ left: 545, top: 264 }}>
        <ZoomIn size={17} />
      </span>
      <Panel>
        <FromTo from="Your location" pickingTo />
        <div className="text-[12px] text-cs-ink-2">You are zoomed out too far to pick one street.</div>
      </Panel>
      <Banner>
        <ZoomIn size={15} /> Click near the spot to zoom in there first <BannerCancel />
      </Banner>
    </div>
  );
}

export function P4() {
  const p = { x: 838, y: 466 };
  return (
    <div className="absolute inset-0">
      <MapBg viewBox={VB}>
        <PinB x={p.x} y={p.y} />
      </MapBg>
      <div
        className="msb-float absolute w-[248px] -translate-x-1/2 rounded-[12px] bg-cs-surface p-3"
        style={{ left: fx(p.x), top: fy(p.y) - 182 }}
      >
        <div className="font-semibold">Near Exit 14</div>
        <div className="text-[12px] text-cs-ink-2">Interstate eastbound · 3.2 mi from you</div>
        <div className="mt-1 flex items-center gap-1 text-[11.5px] text-cs-ink-3">
          <MousePointer2 size={11} /> Drag the pin, or click elsewhere to move it
        </div>
        <div className="mt-2.5 flex gap-2">
          <Btn small primary className="flex-1">
            Set as destination
          </Btn>
          <Btn small>Cancel</Btn>
        </div>
        <span className="absolute -bottom-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 bg-cs-surface" />
      </div>
      <Panel>
        <FromTo from="Your location" pickingTo />
        <div className="rounded-[8px] bg-cs-surface-2 p-2.5 text-[12px] text-cs-ink-2">
          While the address loads the card says “Finding the address…”. Enter also confirms.
        </div>
      </Panel>
    </div>
  );
}

export function P5() {
  return (
    <div className="absolute inset-0">
      <MapBg viewBox={VB} markers={false}>
        <path d={P5_ROUTE} style={{ fill: "none", stroke: "#fff", strokeWidth: 11, strokeLinecap: "round", strokeLinejoin: "round" }} />
        <path d={P5_ROUTE} style={{ fill: "none", stroke: "var(--cs-accent)", strokeWidth: 7, strokeLinecap: "round", strokeLinejoin: "round" }} />
        <PinA />
        <PinB x={838} y={466} />
      </MapBg>
      <Panel>
        <FromTo from="Your location" to="Near Exit 14" />
        <RouteSummary />
      </Panel>
      <div
        className="msb-float absolute bottom-4 flex h-10 -translate-x-1/2 items-center gap-3 whitespace-nowrap rounded-full bg-cs-ink pl-4 pr-1.5 text-[13px] text-cs-bg"
        style={{ left: PANEL + (800 - PANEL) / 2 }}
      >
        Destination set: Near Exit 14
        <span className="flex h-7 items-center gap-1 rounded-full bg-white/15 px-2.5 text-[12px]">
          <Undo2 size={13} /> Undo
        </span>
      </div>
    </div>
  );
}

export function P6() {
  const at = { x: 900, y: 360 };
  const rows: [typeof House, string, string?][] = [
    [Navigation, "Directions from here"],
    [Navigation, "Directions to here"],
    [Info, "What’s here?"],
    [TriangleAlert, "Report a problem here"],
    [Eye, "Watch this area"],
    [Copy, "Copy coordinates"],
  ];
  return (
    <div className="absolute inset-0">
      <MapBg viewBox={VB}>
        <circle cx={at.x} cy={at.y} r="5" style={{ fill: "var(--cs-ink)", stroke: "#fff", strokeWidth: 2 }} />
      </MapBg>
      <Panel>
        <FromTo from="Your location" toPlaceholder="Search a place or address" />
        <div className="text-[12px] text-cs-ink-2">Right-click, or press and hold on a touch screen. Every item is also reachable without it.</div>
      </Panel>
      <div className="msb-float absolute w-[220px] rounded-[10px] border border-cs-line bg-cs-surface py-1.5 text-[13px]" style={{ left: fx(at.x) + 8, top: fy(at.y) + 8 }}>
        <div className="px-3 pb-1.5 pt-0.5 text-[11.5px] text-cs-ink-3">Near Main St and 3rd</div>
        {rows.map(([I, l], i) => (
          <div key={l} className={cx("flex h-8 items-center gap-2.5 px-3", i === 1 && "bg-cs-accent-soft text-cs-accent")}>
            <I size={14} className={cx(i === 0 && "rotate-180", i === 1 ? "" : "text-cs-ink-2")} /> {l}
          </div>
        ))}
      </div>
    </div>
  );
}

export function P7() {
  const p = { x: 1170, y: 560 };
  return (
    <div className="absolute inset-0">
      <MapBg viewBox={VB}>
        <PinB x={p.x} y={p.y} ghost />
        <path d={`M${p.x} ${p.y} L1118 500`} style={{ stroke: "var(--cs-accent)", strokeWidth: 1.5, strokeDasharray: "3 4" }} />
        <circle cx="1118" cy="500" r="6" style={{ fill: "var(--cs-accent)", stroke: "#fff", strokeWidth: 2 }} />
      </MapBg>
      <div className="msb-float absolute w-[236px] rounded-[12px] bg-cs-surface p-3" style={{ left: fx(p.x) - 300, top: fy(p.y) - 60 }}>
        <div className="font-semibold">No road at that spot</div>
        <div className="text-[12px] text-cs-ink-2">The nearest road is 0.3 mi away.</div>
        <div className="mt-2.5 flex gap-2">
          <Btn small primary className="flex-1">
            Use the nearest road
          </Btn>
          <Btn small>Try again</Btn>
        </div>
      </div>
      <Panel>
        <FromTo from="Your location" pickingTo />
      </Panel>
    </div>
  );
}

export function PM1() {
  return (
    <Phone>
      <div className="absolute left-3 right-3 top-12 flex h-11 items-center gap-2 rounded-[12px] bg-cs-ink px-3 text-[13.5px] text-cs-bg msb-float">
        <X size={17} />
        <span className="flex-1">Move the map to place the pin</span>
      </div>
      <div className="absolute left-1/2 top-[300px] -translate-x-1/2">
        <svg width="40" height="60" viewBox="-20 -50 40 60" aria-hidden="true">
          <ellipse cx="0" cy="2" rx="6" ry="2.4" fill="#000" opacity="0.2" />
          <path d="M0 0 V-14" style={{ stroke: "var(--cs-ink)", strokeWidth: 2 }} />
          <circle cy="-27" r="13" style={{ fill: "var(--cs-closure)", stroke: "#fff", strokeWidth: 2 }} />
          <circle cy="-27" r="4.5" fill="#fff" />
        </svg>
      </div>
      <Sheet h={214}>
        <div className="text-[12px] text-cs-ink-3">Your destination</div>
        <div className="text-[17px] font-semibold">Near Exit 14</div>
        <div className="text-[12.5px] text-cs-ink-2">Interstate eastbound</div>
        <Btn primary className="mt-3 h-12 w-full text-[15px]">
          Set destination
        </Btn>
      </Sheet>
    </Phone>
  );
}

export function PM2() {
  return (
    <Phone>
      <div className="absolute left-[205px] top-[380px] h-3 w-3 rounded-full border-2 border-white bg-cs-ink" />
      <Sheet h={330}>
        <div className="text-[17px] font-semibold">Dropped pin</div>
        <div className="text-[12.5px] text-cs-ink-2">Near Main St and 3rd · held for half a second</div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Btn primary icon={Navigation}>
            Directions to
          </Btn>
          <Btn icon={Navigation}>From here</Btn>
          <Btn icon={TriangleAlert}>Report</Btn>
          <Btn icon={Eye}>Watch area</Btn>
        </div>
        <div className="mt-3 text-[12px] text-cs-ink-3">Tap outside or swipe down to dismiss.</div>
      </Sheet>
    </Phone>
  );
}
