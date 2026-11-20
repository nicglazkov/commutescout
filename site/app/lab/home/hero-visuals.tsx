"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import {
  AlertTriangle,
  Bell,
  Camera,
  Check,
  CloudRain,
  Construction,
  Layers,
  MessageSquare,
  Route as RouteIcon,
  ShieldCheck,
  Snowflake,
  Clock,
} from "lucide-react";
import { HeroFrame } from "./hero-shell";
import { SNAP_AT, SOURCE_ROWS } from "./live-snapshot";
import { KIND, StatePaths, UsMap, depth, depthFill, dotPath, fmt, markers, useCycle, useLiveStats, useReduced, type KindKey } from "./viz";

/* Shared bits */

function LiveDot({ live }: { live: boolean }) {
  return (
    <span className="relative inline-flex size-2">
      {live && <span className="absolute inset-0 animate-ping rounded-full bg-cs-ok opacity-60 motion-reduce:hidden" />}
      <span className={`relative size-2 rounded-full ${live ? "bg-cs-ok" : "bg-cs-ink-3"}`} />
    </span>
  );
}

function MapShot({ className = "", priority }: { className?: string; priority?: boolean }) {
  return (
    <>
      <Image
        src="/shots/live-map-light.webp"
        alt="The CommuteScout live map, zoomed out over the country with thousands of live markers."
        width={1600}
        height={939}
        sizes="700px"
        priority={priority}
        className={`block dark:hidden ${className}`}
      />
      <Image
        src="/shots/live-map-dark.webp"
        alt="The CommuteScout live map on its dark base map, zoomed out over the country."
        width={1600}
        height={939}
        sizes="700px"
        className={`hidden dark:block ${className}`}
      />
    </>
  );
}

function Phone({ src, alt, width }: { src: string; alt: string; width: number }) {
  return (
    <div
      className="shrink-0 overflow-hidden rounded-[13%/6%] border border-cs-line-strong bg-cs-surface-2 shadow-[var(--cs-shadow-md)]"
      style={{ width }}
    >
      <Image src={src} alt={alt} width={640} height={1389} sizes={`${width}px`} className="block aspect-[640/1389] h-auto w-full object-cover" />
    </div>
  );
}

/* ---------------- 01 Live mini map ---------------- */

export function LiveMiniMap() {
  const { stats, live } = useLiveStats();
  const counts: Partial<Record<KindKey, number>> = {
    i: stats.incidents,
    c: stats.closures,
    h: stats.chain_controls,
    f: stats.wildfires,
  };
  return (
    <HeroFrame>
      <div className="flex items-center justify-between border-b border-cs-line px-4 py-2.5 text-[0.8125rem]">
        <span className="inline-flex items-center gap-2 font-medium text-cs-ink">
          <LiveDot live={live} />
          {live ? "Live now" : "Snapshot"}
        </span>
        <span className="cs-data hidden text-cs-ink-3 sm:inline">
          {stats.sources} sources · {stats.states} states · every 30 s
        </span>
      </div>
      <div className="bg-cs-bg px-3 pt-3">
        <UsMap showDots title="Every live incident, closure, chain control and wildfire on the map right now, on a map of the US." className="block h-auto w-full" />
      </div>
      <div className="grid grid-cols-2 gap-px border-t border-cs-line bg-cs-line sm:grid-cols-4">
        {(["i", "c", "h", "f"] as KindKey[]).map((k) => (
          <div key={k} className="bg-cs-surface px-4 py-3">
            <p className="cs-data text-xl font-medium leading-none tracking-[-0.02em] text-cs-ink">{fmt(counts[k] ?? 0)}</p>
            <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-cs-ink-3">
              <span aria-hidden className="size-1.5 rounded-full" style={{ background: KIND[k].stroke }} />
              {KIND[k].label}
            </p>
          </div>
        ))}
      </div>
    </HeroFrame>
  );
}

/* ---------------- 02 Walkthrough ---------------- */

const TOUR = [
  { key: "map", label: "Live map", Icon: Layers },
  { key: "route", label: "Route", Icon: RouteIcon },
  { key: "watch", label: "Watch area", Icon: ShieldCheck },
  { key: "ask", label: "Ask", Icon: MessageSquare },
] as const;

export function Walkthrough() {
  const [hold, setHold] = useState(false);
  const [i, setI] = useCycle(TOUR.length, 5200, hold);
  const reduced = useReduced();
  return (
    <HeroFrame>
      <div onPointerEnter={() => setHold(true)} onPointerLeave={() => setHold(false)} onFocus={() => setHold(true)} onBlur={() => setHold(false)}>
        <div role="tablist" aria-label="What CommuteScout does" className="grid grid-cols-4 border-b border-cs-line">
          {TOUR.map((t, idx) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={i === idx}
              onClick={() => setI(idx)}
              className={`relative flex items-center justify-center gap-2 px-2 py-3 text-[0.8125rem] font-medium transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-cs-accent ${
                i === idx ? "text-cs-ink" : "text-cs-ink-3 hover:text-cs-ink"
              } ${idx ? "border-l border-cs-line" : ""}`}
            >
              <t.Icon aria-hidden className="size-4" />
              {t.label}
              <span className="absolute inset-x-0 bottom-0 h-0.5 bg-cs-line">
                {i === idx && (
                  <span
                    key={`${i}-${hold}`}
                    className="block h-full bg-cs-accent"
                    style={reduced || hold ? { width: "100%" } : { animation: "lab-fill 5200ms linear both" }}
                  />
                )}
              </span>
            </button>
          ))}
        </div>
        <div className="relative aspect-[16/10] bg-cs-bg" role="tabpanel">
          {i === 0 && <MapShot className="h-full w-full object-cover object-left-top" />}
          {i === 1 && (
            <div className="flex h-full flex-col justify-center p-6">
              <RouteStripBody compact />
            </div>
          )}
          {i === 2 && <WatchScene />}
          {i === 3 && (
            <div className="h-full p-5">
              <ChatBody compact />
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes lab-fill{from{width:0}to{width:100%}}`}</style>
    </HeroFrame>
  );
}

/* ---------------- 03 Devices ---------------- */

export function Devices() {
  return (
    <div className="relative pb-10 pr-10 sm:pr-16">
      <HeroFrame>
        <MapShot className="h-auto w-full" />
      </HeroFrame>
      <div className="absolute -bottom-2 right-0 w-[24%] min-w-[120px]">
        <Phone src="/shots/app/ios-alert.webp" alt="CommuteScout Drive on iPhone, warning of a hazard on the road 1,000 ft ahead during navigation." width={172} />
      </div>
    </div>
  );
}

/* ---------------- 04 Map with ticker ---------------- */

const TICKS: { k: KindKey | "w"; text: string; st: string; agency: string }[] = [
  { k: "i", text: "Crash, right lane blocked", st: "OH", agency: "OHGO" },
  { k: "c", text: "Two lanes closed for roadwork", st: "FL", agency: "FDOT" },
  { k: "w", text: "Road weather: ice on bridge deck", st: "UT", agency: "UDOT" },
  { k: "h", text: "Chain controls: R2, all vehicles but 4WD", st: "CA", agency: "Caltrans" },
  { k: "i", text: "Disabled vehicle on the shoulder", st: "NC", agency: "NCDOT" },
  { k: "c", text: "Ramp closed overnight", st: "WA", agency: "WSDOT" },
  { k: "f", text: "Wildfire perimeter updated", st: "AZ", agency: "WFIGS" },
  { k: "i", text: "Debris in the left lane", st: "IL", agency: "IDOT" },
];

function kindColor(k: KindKey | "w") {
  return k === "w" ? "var(--cs-weather)" : KIND[k].stroke;
}

export function MapTicker() {
  const reduced = useReduced();
  const [head, setHead] = useState(0);
  useEffect(() => {
    if (reduced) return;
    const t = window.setInterval(() => setHead((h) => (h + 1) % TICKS.length), 2600);
    return () => window.clearInterval(t);
  }, [reduced]);
  const rows = Array.from({ length: 6 }, (_, j) => TICKS[(head + TICKS.length - j) % TICKS.length]);
  return (
    <HeroFrame>
      <div className="grid grid-cols-[1.35fr_1fr]">
        <div className="relative min-h-[380px] overflow-hidden border-r border-cs-line">
          <MapShot className="absolute -top-[9%] left-0 h-[118%] w-full max-w-none object-cover object-[30%_50%]" />
        </div>
        <div className="flex flex-col">
          <div className="flex items-center justify-between border-b border-cs-line px-4 py-2.5">
            <span className="text-[0.8125rem] font-medium text-cs-ink">Just reported</span>
            <span className="cs-data text-[0.6875rem] uppercase tracking-[0.06em] text-cs-ink-3">sample</span>
          </div>
          <ol aria-live="off" className="flex-1 divide-y divide-cs-line">
            {rows.map((r, j) => (
              <li
                key={`${head}-${j}`}
                className="px-4 py-2.5"
                style={j === 0 && !reduced ? { animation: "lab-in 420ms var(--cs-ease) both" } : undefined}
              >
                <p className="flex items-start gap-2 text-[0.8125rem] leading-snug text-cs-ink">
                  <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: kindColor(r.k) }} />
                  {r.text}
                </p>
                <p className="cs-data mt-0.5 pl-4 text-[0.6875rem] text-cs-ink-3">
                  {r.st} · {r.agency} · {j === 0 ? "just now" : `${j * 2 + 1} min ago`}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </div>
      <style>{`@keyframes lab-in{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}`}</style>
    </HeroFrame>
  );
}

/* ---------------- 05 Route by mile ---------------- */

const LEG = 24.6;
const ON_ROUTE: { mile: number; k: KindKey | "w" | "s" | "cam"; text: string }[] = [
  { mile: 3.1, k: "i", text: "Crash, right lane blocked" },
  { mile: 9.8, k: "c", text: "Left lane closed for roadwork until 3 PM" },
  { mile: 12.4, k: "s", text: "Sign reads: EXIT 14 RAMP CLOSED, USE EXIT 15" },
  { mile: 17.0, k: "cam", text: "Camera at Exit 17, image 40 s old" },
  { mile: 21.5, k: "w", text: "Road weather station: wet pavement, 41°F" },
];

function stripColor(k: (typeof ON_ROUTE)[number]["k"]) {
  if (k === "w") return "var(--cs-weather)";
  if (k === "s" || k === "cam") return "var(--cs-ink-3)";
  return KIND[k].stroke;
}

function RouteStripBody({ compact }: { compact?: boolean }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <p className="text-[0.9375rem] font-semibold text-cs-ink">Home to Work</p>
        <p className="cs-data text-[0.8125rem] text-cs-ink-2">{LEG} mi · leave 7:30 AM</p>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[0.8125rem] text-cs-ink-2">
        <span>
          <span className="cs-data font-medium text-cs-ink">38 min</span> with traffic
        </span>
        <span>
          <span className="cs-data text-cs-ink">31 min</span> typical at 7:30
        </span>
        <span>
          <span className="cs-data text-cs-ink">27 min</span> with no traffic
        </span>
      </div>
      <div className="relative mt-7 h-8">
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-cs-surface-2 ring-1 ring-cs-line" />
        <span className="absolute left-0 top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-cs-surface bg-cs-ink" />
        <span className="absolute right-0 top-1/2 size-3.5 -translate-y-1/2 translate-x-1/2 rounded-full border-2 border-cs-surface bg-cs-ink" />
        {ON_ROUTE.map((e) => (
          <span
            key={e.mile}
            className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-cs-surface"
            style={{ left: `${(e.mile / LEG) * 100}%`, background: stripColor(e.k) }}
          />
        ))}
      </div>
      <div className="cs-data mt-1 flex justify-between text-[0.6875rem] text-cs-ink-3">
        <span>mi 0 · Home</span>
        <span>mi {LEG} · Work</span>
      </div>
      <ol className={`mt-4 divide-y divide-cs-line border-y border-cs-line ${compact ? "text-[0.8125rem]" : "text-[0.875rem]"}`}>
        {ON_ROUTE.slice(0, compact ? 4 : 5).map((e) => (
          <li key={e.mile} className="grid grid-cols-[4.25rem_1fr] items-baseline gap-3 py-2">
            <span className="cs-data text-cs-ink-3">mi {e.mile.toFixed(1)}</span>
            <span className="flex items-baseline gap-2 text-cs-ink">
              <span aria-hidden className="size-2 shrink-0 translate-y-[-1px] rounded-full" style={{ background: stripColor(e.k) }} />
              {e.text}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function RouteByMile() {
  return (
    <HeroFrame>
      <div className="p-6">
        <RouteStripBody />
        <p className="mt-4 text-xs text-cs-ink-3">Every live report is pinned to the route by the mile. Sample trip.</p>
      </div>
    </HeroFrame>
  );
}

/* ---------------- 06 Assistant conversation ---------------- */

const ANSWER =
  "Leave by 6:40 to be safe. The drive is 41 min with traffic, 9 more than usual for 7 AM, because of a crash at mile 11.2 that is blocking the right lane. No closures or chain controls on the route. The forecast at the airport for 7:45 is light rain, 46°F.";

function ChatBody({ compact }: { compact?: boolean }) {
  const reduced = useReduced();
  const ref = useRef<HTMLDivElement>(null);
  const words = ANSWER.split(" ");
  const [n, setN] = useState(words.length);
  useEffect(() => {
    if (reduced) return;
    const el = ref.current;
    if (!el) return;
    let t = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      let k = 0;
      setN(0);
      t = window.setInterval(() => {
        k += 1;
        setN(k);
        if (k >= words.length) window.clearInterval(t);
      }, 55);
    });
    io.observe(el);
    return () => {
      io.disconnect();
      window.clearInterval(t);
    };
  }, [reduced, words.length]);
  return (
    <div ref={ref} className="flex h-full flex-col gap-3">
      <div className="ml-auto max-w-[80%] rounded-[var(--cs-radius-md)] rounded-br-sm bg-cs-ink px-3.5 py-2.5 text-[0.875rem] leading-snug text-cs-bg">
        I fly at 9 tomorrow. When should I leave home for the airport?
      </div>
      <div className="inline-flex w-fit items-center gap-2 rounded-[var(--cs-radius-sm)] border border-cs-line bg-cs-inset px-2.5 py-1">
        <span className="cs-data text-[0.75rem] text-cs-ink-2">best_time_to_go</span>
        <span className="text-[0.75rem] text-cs-ink-3">Home → Airport · 6:00 to 8:00 AM</span>
        <Check aria-hidden className="size-3.5 text-cs-ok" />
      </div>
      <div className={`max-w-[92%] rounded-[var(--cs-radius-md)] rounded-bl-sm border border-cs-line bg-cs-surface px-3.5 py-2.5 leading-relaxed text-cs-ink ${compact ? "text-[0.8125rem]" : "text-[0.9375rem]"}`}>
        <span aria-hidden>{words.slice(0, n).join(" ")}</span>
        <span className="sr-only">{ANSWER}</span>
        {n < words.length && <span aria-hidden className="ml-0.5 inline-block h-3.5 w-1.5 translate-y-0.5 bg-cs-ink-3" />}
      </div>
      {!compact && (
        <p className="mt-auto text-xs text-cs-ink-3">Claude, ChatGPT or any MCP assistant. Answers come from the same official sources as the map. Sample answer.</p>
      )}
    </div>
  );
}

export function AssistantChat() {
  return (
    <HeroFrame>
      <div className="flex items-center gap-2 border-b border-cs-line px-4 py-2.5 text-[0.8125rem] text-cs-ink-2">
        <MessageSquare aria-hidden className="size-4" />
        Your assistant, connected to CommuteScout
      </div>
      <div className="min-h-[300px] bg-cs-bg p-5">
        <ChatBody />
      </div>
    </HeroFrame>
  );
}

/* ---------------- 07 Coverage map with live counts ---------------- */

export function CoverageLive() {
  const { stats, live } = useLiveStats();
  return (
    <HeroFrame>
      <div className="grid grid-cols-[1fr_11rem]">
        <div className="bg-cs-bg p-4">
          <UsMap fill={(n) => depthFill(depth(n))} stroke="var(--cs-surface)" title="States CommuteScout reads road reports from, shaded by how many kinds each state publishes." className="block h-auto w-full" />
          <div className="mt-2 flex items-center gap-3 text-xs text-cs-ink-3">
            <span>Kinds of report from the state</span>
            <span className="flex">
              {[1, 2, 3, 4, 5].map((d) => (
                <span key={d} className="h-2.5 w-6 first:rounded-l-sm last:rounded-r-sm" style={{ background: depthFill(d) }} />
              ))}
            </span>
            <span className="cs-data">1 to 5</span>
          </div>
        </div>
        <dl className="flex flex-col divide-y divide-cs-line border-l border-cs-line">
          {[
            ["States", stats.states],
            ["Official sources", stats.sources],
            ["Closures now", stats.closures],
            ["Incidents now", stats.incidents],
            ["Cameras", stats.cameras],
          ].map(([l, v]) => (
            <div key={l as string} className="flex-1 px-4 py-3">
              <dt className="text-xs text-cs-ink-3">{l}</dt>
              <dd className="cs-data mt-1 text-lg font-medium leading-none text-cs-ink">{fmt(v as number)}</dd>
            </div>
          ))}
          <div className="flex items-center gap-2 px-4 py-2.5 text-xs text-cs-ink-3">
            <LiveDot live={live} />
            {live ? "live" : "snapshot"}
          </div>
        </dl>
      </div>
    </HeroFrame>
  );
}

/* ---------------- 08 Before-you-go checklist ---------------- */

const CHECKS: { ok: boolean; Icon: typeof Check; label: string; value: string; tone?: string }[] = [
  { ok: true, Icon: Construction, label: "Closures on the route", value: "None" },
  { ok: false, Icon: AlertTriangle, label: "Incidents on the route", value: "1, at mile 9.8", tone: "var(--cs-incident)" },
  { ok: true, Icon: Snowflake, label: "Chain controls", value: "None" },
  { ok: false, Icon: CloudRain, label: "Weather alerts along the way", value: "Wind advisory", tone: "var(--cs-weather)" },
  { ok: true, Icon: Camera, label: "Cameras on the route", value: "4, newest 40 s old" },
  { ok: true, Icon: Clock, label: "Drive time, leaving now", value: "34 min, usual 31" },
];

export function Checklist() {
  return (
    <HeroFrame>
      <div className="flex items-baseline justify-between border-b border-cs-line px-5 py-3.5">
        <div>
          <p className="cs-eyebrow">Before you go</p>
          <p className="mt-1 text-[1.0625rem] font-semibold text-cs-ink">Home to School</p>
        </div>
        <p className="cs-data text-[0.8125rem] text-cs-ink-3">checked 12 s ago</p>
      </div>
      <ul className="divide-y divide-cs-line">
        {CHECKS.map((c) => (
          <li key={c.label} className="flex items-center gap-3 px-5 py-3">
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-full"
              style={{
                background: c.ok ? "var(--cs-ok-soft)" : `color-mix(in oklab, ${c.tone} 14%, var(--cs-surface))`,
                color: c.ok ? "var(--cs-ok)" : c.tone,
              }}
            >
              {c.ok ? <Check aria-hidden className="size-4" /> : <c.Icon aria-hidden className="size-4" />}
            </span>
            <span className="flex-1 text-[0.9375rem] text-cs-ink">{c.label}</span>
            <span className="cs-data text-[0.875rem]" style={{ color: c.ok ? "var(--cs-ink-2)" : c.tone }}>
              {c.value}
            </span>
          </li>
        ))}
      </ul>
      <p className="border-t border-cs-line bg-cs-bg px-5 py-2.5 text-xs text-cs-ink-3">Sample trip. The route planner and the assistants run these checks on any drive.</p>
    </HeroFrame>
  );
}

/* ---------------- 09 Exploded layers ---------------- */

const STACK: { k: KindKey | null; label: string }[] = [
  { k: null, label: "Base map" },
  { k: "c", label: "Closures" },
  { k: "i", label: "Incidents" },
  { k: "h", label: "Chain controls" },
  { k: "f", label: "Wildfires" },
];
// Oblique plan: each sheet is the 975 x 610 map, tilted onto a table.
const MA = 0.74, MB = 0.1, MC = 0.36, MD = 0.32;
const SHEET_H = MB * 975 + MD * 610; // 292.7

export function ExplodedLayers() {
  const { stats } = useLiveStats();
  const [open, setOpen] = useState(true);
  const ms = markers();
  const count: Record<KindKey, number> = { i: stats.incidents, c: stats.closures, h: stats.chain_controls, f: stats.wildfires };
  const gap = open ? 62 : 6;
  const W = 1200, H = 600;
  const base = H - SHEET_H - 14;
  return (
    <HeroFrame>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="block w-full bg-cs-bg text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-cs-accent"
      >
        <span className="sr-only">{open ? "Stack the layers" : "Pull the layers apart"}</span>
        <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label="The live map as a stack of sheets: the base map, then closures, incidents, chain controls and wildfires, each drawn with its real live points.">
          {STACK.map((l, idx) => {
            const ty = base - idx * gap;
            const right = MA * 975 + MC * 305; // label anchor on the sheet's right edge
            const ry = MB * 975 + MD * 305;
            return (
              <g key={l.label} style={{ transform: `translateY(${ty}px)`, transition: "transform 700ms var(--cs-ease)" }}>
                <g transform={`matrix(${MA} ${MB} ${MC} ${MD} 16 0)`}>
                  <rect
                    x="-14"
                    y="-14"
                    width="1003"
                    height="638"
                    rx="14"
                    fill={l.k ? "color-mix(in oklab, var(--cs-surface) 62%, transparent)" : "var(--cs-surface)"}
                    stroke={l.k ? KIND[l.k].stroke : "var(--cs-line-strong)"}
                    strokeOpacity={l.k ? 0.55 : 1}
                    strokeWidth="2.4"
                  />
                  {l.k === null ? (
                    <StatePaths />
                  ) : (
                    <path d={dotPath(ms.filter((m) => m.k === l.k))} stroke={KIND[l.k].stroke} strokeWidth={l.k === "c" ? 5 : 8} strokeLinecap="round" fill="none" opacity={l.k === "c" ? 0.75 : 1} />
                  )}
                </g>
                <line x1={16 + right} y1={ry} x2={980} y2={ry} stroke="var(--cs-line-strong)" strokeDasharray="3 4" />
                <circle cx={980} cy={ry} r="5" fill={l.k ? KIND[l.k].stroke : "var(--cs-ink-3)"} />
                <text x={994} y={ry - 4} fontSize="27" fontWeight="600" fill="var(--cs-ink)" fontFamily="var(--cs-font-sans)">
                  {l.label}
                </text>
                <text x={994} y={ry + 26} fontSize="21" fill="var(--cs-ink-3)" fontFamily="var(--cs-font-mono)">
                  {l.k ? `${fmt(count[l.k])} now` : "every state"}
                </text>
              </g>
            );
          })}
        </svg>
        <span className="block border-t border-cs-line px-4 py-2 text-xs text-cs-ink-3">{open ? "Click to stack the layers into one map" : "Click to pull the layers apart"}</span>
      </button>
    </HeroFrame>
  );
}

/* ---------------- 10 Source ledger ---------------- */

type Row = { name: string; agency: string; state: string | null; count: number | null; age: number | null; status: string };

export function SourceLedger() {
  const [rows, setRows] = useState<Row[]>(() => SOURCE_ROWS.filter((r) => r.count && r.age !== null));
  const [at, setAt] = useState(() => Date.parse(SNAP_AT));
  const [now, setNow] = useState(() => Date.parse(SNAP_AT));
  const [live, setLive] = useState(false);
  useEffect(() => {
    const load = () =>
      fetch("/api/sources", { headers: { Accept: "application/json" } })
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((d: { checked_at: string; sources: (Row & { state_code: string | null; age_s: number | null })[] }) => {
          setRows(
            d.sources
              .filter((s) => s.count && s.age_s !== null)
              .map((s) => ({ name: s.name, agency: s.agency, state: s.state_code, count: s.count, age: s.age_s, status: s.status })),
          );
          setAt(Date.parse(d.checked_at));
          setLive(true);
        })
        .catch(() => {});
    load();
    const t1 = window.setInterval(load, 30000);
    const t2 = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      window.clearInterval(t1);
      window.clearInterval(t2);
    };
  }, []);
  const drift = live ? Math.max(0, Math.round((now - at) / 1000)) : 0;
  const shown = rows
    .slice()
    .sort((a, b) => (a.age ?? 0) - (b.age ?? 0))
    .slice(0, 9);
  const age = (s: number) => (s < 90 ? `${s} s` : `${Math.round(s / 60)} min`);
  return (
    <HeroFrame>
      <div className="flex items-center justify-between border-b border-cs-line px-4 py-2.5 text-[0.8125rem]">
        <span className="inline-flex items-center gap-2 font-medium text-cs-ink">
          <LiveDot live={live} />
          Read from each agency, newest first
        </span>
        <span className="cs-data text-cs-ink-3">/api/sources</span>
      </div>
      <table className="w-full text-[0.8125rem]">
        <thead>
          <tr className="border-b border-cs-line text-left text-[0.6875rem] uppercase tracking-[0.06em] text-cs-ink-3">
            <th className="px-4 py-2 font-medium">Agency</th>
            <th className="py-2 font-medium">State</th>
            <th className="py-2 font-medium">Feed</th>
            <th className="py-2 text-right font-medium">Items</th>
            <th className="px-4 py-2 text-right font-medium">Read</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-cs-line">
          {shown.map((r) => (
            <tr key={r.agency + r.name}>
              <td className="px-4 py-2 font-medium text-cs-ink">{r.agency}</td>
              <td className="cs-data py-2 text-cs-ink-2">{r.state ?? "US"}</td>
              <td className="py-2 text-cs-ink-2">{r.name.replace(/\s*\(.*\)$/, "")}</td>
              <td className="cs-data py-2 text-right text-cs-ink">{fmt(r.count ?? 0)}</td>
              <td className="cs-data whitespace-nowrap px-4 py-2 text-right text-cs-ok">
                <span className="inline-flex items-center gap-1.5">
                  <span aria-hidden className="size-1.5 rounded-full bg-cs-ok" />
                  {age((r.age ?? 0) + drift)} ago
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </HeroFrame>
  );
}

/* ---------------- 11 Two phones ---------------- */

export function PhonePair() {
  return (
    <div className="relative flex h-[460px] items-center justify-center gap-6">
      <div className="translate-y-6">
        <Phone src="/shots/app/ios-map.webp" alt="CommuteScout Drive on iPhone: the live map with incidents and closures." width={200} />
      </div>
      <div className="-translate-y-6">
        <Phone src="/shots/app/ios-alert.webp" alt="CommuteScout Drive on iPhone: navigation with a hazard warning 1,000 ft ahead." width={200} />
      </div>
      <div className="translate-y-10">
        <Phone src="/shots/app/android-map.webp" alt="CommuteScout Drive on Android: the map with a live closure marker." width={176} />
      </div>
    </div>
  );
}

/* ---------------- 12 Right-now board ---------------- */

export function NowBoard() {
  const { stats, live } = useLiveStats();
  const cells: [string, number, string][] = [
    ["Closures", stats.closures, "var(--cs-closure)"],
    ["Cameras", stats.cameras, "var(--cs-band-ink-2)"],
    ["Incidents", stats.incidents, "var(--cs-incident)"],
    ["Chain controls", stats.chain_controls, "var(--cs-chain)"],
    ["Wildfires", stats.wildfires, "var(--cs-fire)"],
    ["Sources", stats.sources, "var(--cs-band-ink-2)"],
  ];
  return (
    <figure className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-band-line bg-cs-band text-cs-band-ink shadow-[var(--cs-shadow-md)]">
      <div className="flex items-center justify-between border-b border-cs-band-line px-5 py-3 text-[0.8125rem]">
        <span className="inline-flex items-center gap-2 font-medium">
          <LiveDot live={live} />
          On the road right now
        </span>
        <span className="cs-data text-cs-band-ink-2">{stats.states} states · refreshed every 30 s</span>
      </div>
      <dl className="grid grid-cols-2 gap-px bg-cs-band-line sm:grid-cols-3">
        {cells.map(([l, v, c]) => (
          <div key={l} className="bg-cs-band px-5 py-6">
            <dt className="inline-flex items-center gap-2 text-[0.8125rem] text-cs-band-ink-2">
              <span aria-hidden className="size-2 rounded-full" style={{ background: c }} />
              {l}
            </dt>
            <dd className="mt-3 text-[2.5rem] font-medium leading-none tracking-[-0.035em] tabular-nums">{fmt(v)}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}

/* ---------------- 13 Annotated screenshot ---------------- */

const NOTES: { n: number; x: number; y: number; title: string; body: string }[] = [
  { n: 1, x: 6.5, y: 17, title: "Route, Ask, Layers, Watch, Alerts", body: "Plan a drive, ask about it, pick layers, draw a watch area." },
  { n: 2, x: 40, y: 1.5, title: "Search any place", body: "An address, a place or coordinates." },
  { n: 3, x: 60, y: 45, title: "One dot, one live report", body: "Colored by kind, read from the agency that published it." },
  { n: 4, x: 91, y: 9, title: "Report", body: "Tell us what you see on the road." },
];

export function Annotated() {
  const [on, setOn] = useState<number | null>(3);
  return (
    <div>
      <HeroFrame>
        <div className="relative">
          <MapShot className="h-auto w-full" />
          {NOTES.map((n) => (
            <button
              key={n.n}
              type="button"
              onPointerEnter={() => setOn(n.n)}
              onFocus={() => setOn(n.n)}
              onClick={() => setOn(n.n)}
              aria-label={n.title}
              className={`absolute flex size-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-cs-surface text-[0.75rem] font-semibold shadow-[var(--cs-shadow-md)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cs-accent ${
                on === n.n ? "bg-cs-accent text-cs-accent-ink" : "bg-cs-ink text-cs-bg"
              }`}
              style={{ left: `${n.x}%`, top: `${n.y + 3}%` }}
            >
              {n.n}
            </button>
          ))}
        </div>
      </HeroFrame>
      <ol className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3">
        {NOTES.map((n) => (
          <li key={n.n} className={`flex gap-2.5 text-[0.8125rem] leading-snug transition-opacity ${on === n.n ? "opacity-100" : "opacity-60"}`}>
            <span className="cs-data mt-px text-cs-ink-3">{n.n}</span>
            <span>
              <span className="font-medium text-cs-ink">{n.title}.</span> <span className="text-cs-ink-2">{n.body}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ---------------- 14 Watch area alert ---------------- */

function WatchScene() {
  const reduced = useReduced();
  const [step, setStep] = useState(reduced ? 2 : 0);
  useEffect(() => {
    if (reduced) return;
    const seq = [0, 1, 2, 2, 2];
    let i = 0;
    const t = window.setInterval(() => {
      i = (i + 1) % seq.length;
      setStep(seq[i]);
    }, 1400);
    return () => window.clearInterval(t);
  }, [reduced]);
  const s = reduced ? 2 : step;
  return (
    <div className="relative h-full min-h-[340px] overflow-hidden bg-cs-bg">
      <svg viewBox="0 0 640 400" className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid slice" aria-hidden>
        <g stroke="var(--cs-line-strong)" strokeWidth="1" fill="none">
          {Array.from({ length: 9 }, (_, i) => (
            <path key={`h${i}`} d={`M0 ${30 + i * 45}H640`} />
          ))}
          {Array.from({ length: 12 }, (_, i) => (
            <path key={`v${i}`} d={`M${20 + i * 55} 0V400`} />
          ))}
        </g>
        <path d="M-10 300 C 140 280, 220 200, 330 190 S 520 120, 660 90" stroke="var(--cs-surface)" strokeWidth="14" fill="none" />
        <path d="M-10 300 C 140 280, 220 200, 330 190 S 520 120, 660 90" stroke="var(--cs-ink-3)" strokeWidth="2" strokeDasharray="10 8" fill="none" />
        <path
          d="M170 150 C 200 110, 330 100, 420 120 C 500 140, 520 230, 460 270 C 400 310, 230 320, 180 280 C 140 250, 140 190, 170 150Z"
          fill="color-mix(in oklab, var(--cs-accent) 10%, transparent)"
          stroke="var(--cs-accent)"
          strokeWidth="2"
          strokeDasharray="7 5"
        />
        <circle cx="96" cy="282" r="7" fill="var(--cs-ink)" />
        <text x="96" y="312" textAnchor="middle" fontSize="13" fill="var(--cs-ink-2)" fontFamily="var(--cs-font-sans)">Home</text>
        <circle cx="590" cy="102" r="7" fill="var(--cs-ink)" />
        <text x="590" y="132" textAnchor="middle" fontSize="13" fill="var(--cs-ink-2)" fontFamily="var(--cs-font-sans)">School</text>
        <circle cx="250" cy="150" r="6" fill="var(--cs-ink-3)" />
        <circle cx="430" cy="250" r="6" fill="var(--cs-ink-3)" />
        {s >= 1 && <circle cx="345" cy="186" r="8" fill="var(--cs-incident)" stroke="var(--cs-surface)" strokeWidth="2.5" />}
      </svg>
      <div
        className={`absolute left-4 top-4 w-[17rem] rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface p-3 shadow-[var(--cs-shadow-md)] transition-all duration-500 ease-[var(--cs-ease)] ${
          s >= 2 ? "translate-y-0 opacity-100" : "-translate-y-3 opacity-0"
        }`}
      >
        <p className="flex items-center gap-2 text-[0.75rem] text-cs-ink-3">
          <Bell aria-hidden className="size-3.5" /> CommuteScout · now
        </p>
        <p className="mt-1 text-[0.875rem] font-semibold text-cs-ink">New crash in “Home to School”</p>
        <p className="text-[0.8125rem] text-cs-ink-2">Right lane blocked. Reported 1 min ago.</p>
      </div>
      <p className="absolute bottom-3 left-4 max-w-[22rem] text-xs text-cs-ink-3">
        Gray dots were already there at the first check, so they never alert. Only the new crash does.
      </p>
    </div>
  );
}

export function WatchAlert() {
  return (
    <HeroFrame>
      <div className="flex items-center gap-2 border-b border-cs-line px-4 py-2.5 text-[0.8125rem] text-cs-ink-2">
        <ShieldCheck aria-hidden className="size-4" />
        Watch area: Home to School · push on
      </div>
      <div className="h-[380px]">
        <WatchScene />
      </div>
    </HeroFrame>
  );
}

