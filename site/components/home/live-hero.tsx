"use client";

import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Bell, Check, Layers, MessageSquare, Pause, Play, Route as RouteIcon, ShieldCheck } from "lucide-react";
import { inLower48, project } from "./albers";

// The live half of the home hero. The map's outlines arrive as server-
// rendered SVG (the `base` prop), so the first paint needs no script and
// no image. After the page has loaded, this fetches:
// - /api/hero-dots: every live incident, closure, chain control and
//   wildfire as a bare point (src/ca_roads_demo/hero_dots.py), and
// - /api/stats: the same counts the map's header shows,
// both public, keyless and outside the strict rate limiter, and polls
// them every 30 s, which is how often the server rebuilds them.
//
// Over the map, a slim step rail walks through what the product does with
// that data: plan a route, watch an area, ask an assistant. The cards are
// samples and say so. The tour pauses on hover or focus, has a pause
// button, stops after two passes, and never moves under reduced motion.

type Kind = "i" | "c" | "h" | "f";
const KINDS: { k: Kind; label: string; color: string; size: number; alpha: number }[] = [
  // Closures go first so the rarer kinds draw on top of them.
  { k: "c", label: "Closures", color: "var(--cs-closure)", size: 3.2, alpha: 0.7 },
  { k: "i", label: "Incidents", color: "var(--cs-incident)", size: 4.8, alpha: 1 },
  { k: "h", label: "Chain controls", color: "var(--cs-chain)", size: 4.8, alpha: 1 },
  { k: "f", label: "Wildfires", color: "var(--cs-fire)", size: 4.8, alpha: 1 },
];
const COUNT_ORDER: { k: Kind; stat: keyof Stats }[] = [
  { k: "i", stat: "incidents" },
  { k: "c", stat: "closures" },
  { k: "h", stat: "chain_controls" },
  { k: "f", stat: "wildfires" },
];

type Wire = { at: string } & Record<Kind, number[]>;
type Stats = { incidents: number; closures: number; chain_controls: number; wildfires: number };
type Feed = "connecting" | "live" | "sample" | "down";

const POLL_MS = 30_000;

function toPaths(w: Wire): Record<Kind, string> {
  const out = { i: "", c: "", h: "", f: "" } as Record<Kind, string>;
  for (const { k } of KINDS) {
    const a = w[k] ?? [];
    let d = "";
    for (let j = 0; j + 1 < a.length; j += 2) {
      if (!inLower48(a[j], a[j + 1])) continue;
      const [x, y] = project(a[j], a[j + 1]);
      d += `M${x.toFixed(1)} ${y.toFixed(1)}h0`;
    }
    out[k] = d;
  }
  return out;
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(String(r.status));
  return (await r.json()) as T;
}

function useLiveFeed() {
  const [paths, setPaths] = useState<Record<Kind, string> | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [at, setAt] = useState<number | null>(null);
  const [feed, setFeed] = useState<Feed>("connecting");

  useEffect(() => {
    let off = false;
    let timer = 0;

    const loadDots = async () => {
      try {
        const w = await getJson<Wire>("/api/hero-dots");
        if (off) return;
        setPaths(toPaths(w));
        setAt(Date.parse(w.at) || Date.now());
        setFeed("live");
      } catch {
        // The dev server proxies /api/* to production, which has no
        // /api/hero-dots until this ships. In development only, draw a
        // saved copy so the preview has dots, and label it as a sample.
        // NODE_ENV is inlined at build time, so the production bundle
        // never contains this branch or the file.
        if (process.env.NODE_ENV === "development") {
          const m = await import("./hero-dots.dev.json");
          if (off) return;
          const w = m.default as unknown as Wire;
          setPaths((p) => p ?? toPaths(w));
          setAt((t) => t ?? Date.parse(w.at));
          setFeed((f) => (f === "live" ? f : "sample"));
          return;
        }
        if (!off) setFeed((f) => (f === "live" ? f : "down"));
      }
    };
    const loadStats = async () => {
      try {
        const s = await getJson<Stats>("/api/stats");
        if (!off) setStats(s);
      } catch {
        // Keep the last good counts; the slots never collapse.
      }
    };
    const tick = () => {
      if (document.hidden) return;
      void loadDots();
      void loadStats();
    };
    const start = () => {
      tick();
      timer = window.setInterval(tick, POLL_MS);
    };
    // After load, so none of this competes with the first paint.
    if (document.readyState === "complete") start();
    else window.addEventListener("load", start, { once: true });
    const onVisible = () => {
      if (!document.hidden) tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      off = true;
      window.clearInterval(timer);
      window.removeEventListener("load", start);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  return { paths, stats, at, feed };
}

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => {
      if (!document.hidden) setNow(Date.now());
    }, 1000);
    return () => window.clearInterval(t);
  }, [active]);
  return now;
}

function useReducedMotion() {
  const [r, setR] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setR(m.matches);
    on();
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return r;
}

function ago(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s} s ago`;
  return `${Math.round(s / 60)} min ago`;
}

const fmt = (n: number) => n.toLocaleString("en-US");

/* ---------------- The status line ---------------- */

function FeedStatus({ feed, at }: { feed: Feed; at: number | null }) {
  const now = useNow(at !== null);
  const live = feed === "live";
  let text: ReactNode = "Connecting to the live map";
  if (feed === "live" && at !== null) text = <>Live · updated {ago(now - at)}</>;
  if (feed === "sample") text = "Saved sample · dev preview only";
  if (feed === "down") text = "Live data is unavailable right now";
  return (
    <span className="inline-flex min-w-0 items-center gap-2 font-medium text-cs-ink">
      <span aria-hidden className="relative inline-flex size-2 shrink-0">
        {live && <span className="absolute inset-0 animate-ping rounded-full bg-cs-ok opacity-50 [animation-duration:2.4s] motion-reduce:hidden" />}
        <span className={`relative size-2 rounded-full ${live ? "bg-cs-ok" : "bg-cs-ink-3"}`} />
      </span>
      <span className="truncate tabular-nums">{text}</span>
    </span>
  );
}

/* ---------------- Tour cards ---------------- */

const ROUTE_LEG = 24.6;
const ROUTE_EVENTS: { mile: number; k: Kind }[] = [
  { mile: 3.1, k: "i" },
  { mile: 9.8, k: "c" },
  { mile: 17.0, k: "i" },
];
const COLOR: Record<Kind, string> = Object.fromEntries(KINDS.map((k) => [k.k, k.color])) as Record<Kind, string>;

function Sample({ children }: { children: ReactNode }) {
  return <p className="cs-eyebrow text-[0.6875rem]">{children}</p>;
}

function MapCard() {
  return (
    <>
      <Sample>The live map</Sample>
      <p className="mt-1.5 text-[0.875rem] leading-snug text-cs-ink">
        Each dot is a report from an official feed, placed where the agency put it. Open the map to
        zoom in to lanes, cameras and message signs.
      </p>
    </>
  );
}

function RouteCard() {
  return (
    <>
      <Sample>Route · sample trip</Sample>
      <div className="mt-1.5 flex items-baseline justify-between gap-3">
        <p className="text-[0.9375rem] font-semibold text-cs-ink">Home to Work</p>
        <p className="text-[0.8125rem] tabular-nums text-cs-ink-2">{ROUTE_LEG} mi</p>
      </div>
      <p className="text-[0.8125rem] text-cs-ink-2">
        <span className="font-semibold tabular-nums text-cs-ink">38 min</span> with traffic,{" "}
        <span className="tabular-nums text-cs-ink">31</span> typical
      </p>
      <div aria-hidden className="relative mt-3 h-3">
        <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-cs-surface-2 ring-1 ring-cs-line" />
        <span className="absolute left-0 top-1/2 size-2.5 -translate-y-1/2 rounded-full bg-cs-ink" />
        <span className="absolute right-0 top-1/2 size-2.5 -translate-y-1/2 rounded-full bg-cs-ink" />
        {ROUTE_EVENTS.map((e) => (
          <span
            key={e.mile}
            className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-cs-surface"
            style={{ left: `${(e.mile / ROUTE_LEG) * 100}%`, background: COLOR[e.k] }}
          />
        ))}
      </div>
      <p className="mt-2.5 grid grid-cols-[3.25rem_1fr] gap-2 text-[0.8125rem] text-cs-ink">
        <span className="tabular-nums text-cs-ink-3">mi 9.8</span>
        <span>Left lane closed for roadwork until 3 PM</span>
      </p>
    </>
  );
}

function WatchCard() {
  return (
    <>
      <Sample>Watch area · sample alert</Sample>
      <div className="mt-2 flex gap-2.5">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-[var(--cs-radius-sm)] bg-cs-accent-soft text-cs-accent">
          <Bell aria-hidden className="size-3.5" />
        </span>
        <div className="min-w-0">
          <p className="text-[0.875rem] font-semibold leading-snug text-cs-ink">New crash in &ldquo;Home to School&rdquo;</p>
          <p className="text-[0.8125rem] leading-snug text-cs-ink-2">Right lane blocked. Reported 1 min ago.</p>
        </div>
      </div>
      <p className="mt-2.5 text-[0.75rem] leading-snug text-cs-ink-3">A push when something new appears in an area you watch.</p>
    </>
  );
}

function AskCard() {
  return (
    <>
      <Sample>Your assistant · sample answer</Sample>
      <p className="mt-2 ml-auto w-fit max-w-[92%] rounded-[var(--cs-radius-md)] rounded-br-sm bg-cs-ink px-2.5 py-1.5 text-[0.8125rem] leading-snug text-cs-bg">
        I fly at 9 tomorrow. When should I leave home?
      </p>
      <p className="mt-2 inline-flex items-center gap-1.5 rounded-[var(--cs-radius-sm)] border border-cs-line bg-cs-inset px-2 py-0.5">
        <span className="cs-data text-[0.6875rem] text-cs-ink-2">best_time_to_go</span>
        <Check aria-hidden className="size-3 text-cs-ok" />
      </p>
      <p className="mt-1.5 text-[0.8125rem] leading-snug text-cs-ink">
        Leave by 6:40. It is 41 min with traffic, 9 more than usual, because of a crash at mile 11.2.
      </p>
    </>
  );
}

const STEPS = [
  { key: "map", label: "Live map", short: "Map", Icon: Layers, Card: MapCard },
  { key: "route", label: "Route", short: "Route", Icon: RouteIcon, Card: RouteCard },
  { key: "watch", label: "Watch area", short: "Watch", Icon: ShieldCheck, Card: WatchCard },
  { key: "ask", label: "Ask", short: "Ask", Icon: MessageSquare, Card: AskCard },
] as const;

const STEP_MS = 6500;
const PASSES = 2;

/* ---------------- The hero figure ---------------- */

export function LiveHero({ base }: { base: ReactNode }) {
  const { paths, stats, at, feed } = useLiveFeed();
  const reduced = useReducedMotion();
  const uid = useId();
  const [step, setStep] = useState(0);
  const [hold, setHold] = useState(false);
  const [stopped, setStopped] = useState(false);
  const shown = useRef(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);

  const running = !reduced && !stopped && !hold;
  useEffect(() => {
    if (!running) return;
    const t = window.setTimeout(() => {
      shown.current += 1;
      if (shown.current >= STEPS.length * PASSES - 1) setStopped(true);
      setStep((s) => (s + 1) % STEPS.length);
    }, STEP_MS);
    return () => window.clearTimeout(t);
  }, [running, step]);

  const choose = useCallback((i: number) => {
    setStep(i);
    setStopped(true);
  }, []);

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    let n = -1;
    if (d) n = (step + d + STEPS.length) % STEPS.length;
    if (e.key === "Home") n = 0;
    if (e.key === "End") n = STEPS.length - 1;
    if (n < 0) return;
    e.preventDefault();
    choose(n);
    tabs.current[n]?.focus();
  };

  const Card = STEPS[step].Card;
  const panelId = `${uid}-panel`;

  return (
    <figure
      className="rounded-[calc(var(--cs-radius-lg)+6px)] border border-cs-line bg-cs-surface-2 p-1.5 sm:p-2"
      onPointerEnter={() => setHold(true)}
      onPointerLeave={() => setHold(false)}
      onFocusCapture={() => setHold(true)}
      onBlurCapture={() => setHold(false)}
    >
      <div className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line-strong bg-cs-surface shadow-[var(--cs-shadow-md)]">
        <div className="flex h-10 items-center justify-between gap-3 border-b border-cs-line px-3.5 text-[0.8125rem] sm:px-4">
          <FeedStatus feed={feed} at={at} />
          <span className="hidden shrink-0 text-cs-ink-3 sm:inline">Refreshes about every 30 s</span>
        </div>

        <div className="relative bg-cs-bg">
          <div className="relative mx-auto aspect-[975/610] w-full px-2 pt-2 sm:px-3 sm:pt-3">
            <div className="relative h-full w-full">
              {base}
              <svg
                viewBox="0 0 975 610"
                aria-hidden
                className={`absolute inset-0 h-full w-full transition-opacity duration-700 ease-[var(--cs-ease)] motion-reduce:transition-none ${paths ? "opacity-100" : "opacity-0"}`}
              >
                {paths &&
                  KINDS.map(({ k, color, size, alpha }) => (
                    <path key={k} d={paths[k]} stroke={color} strokeWidth={size} strokeLinecap="round" fill="none" opacity={alpha} />
                  ))}
              </svg>
            </div>
          </div>

          {/* Tour card: over the map's south-east corner from sm up (the
              first step leaves the map clear and keeps its text for screen
              readers only), in the flow below the map on phones. Fixed height on phones so a
              step change never moves the page. */}
          <div
            id={panelId}
            role="tabpanel"
            aria-labelledby={`${uid}-tab-${step}`}
            className={`border-t border-cs-line bg-cs-surface px-3.5 py-3 max-sm:h-[9.75rem] sm:absolute sm:bottom-3 sm:right-3 sm:w-[17.5rem] sm:rounded-[var(--cs-radius-md)] sm:border sm:shadow-[var(--cs-shadow-md)] ${step === 0 ? "sm:sr-only" : ""}`}
          >
            <div key={step} className="cs-hero-card">
              <Card />
            </div>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-px border-t border-cs-line bg-cs-line sm:grid-cols-4">
          {COUNT_ORDER.map(({ k, stat }) => {
            const meta = KINDS.find((x) => x.k === k)!;
            return (
              <div key={k} className="flex flex-col-reverse bg-cs-surface px-3.5 py-2.5 sm:px-4 sm:py-3">
                <dt className="mt-1 inline-flex items-center gap-1.5 text-xs text-cs-ink-3">
                  <span aria-hidden className="size-1.5 rounded-full" style={{ background: meta.color }} />
                  {meta.label}
                </dt>
                <dd className="h-6 text-xl font-semibold leading-6 tracking-[-0.01em] text-cs-ink tabular-nums">
                  {stats ? fmt(stats[stat]) : <span className="text-cs-ink-3">&ndash;</span>}
                </dd>
              </div>
            );
          })}
        </dl>

        <div className="flex items-stretch border-t border-cs-line">
          <div role="tablist" aria-label="What you can do with the live data" onKeyDown={onKey} className="grid flex-1 grid-cols-4">
            {STEPS.map((s, i) => {
              const on = i === step;
              return (
                <button
                  key={s.key}
                  ref={(el) => {
                    tabs.current[i] = el;
                  }}
                  id={`${uid}-tab-${i}`}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  aria-controls={panelId}
                  tabIndex={on ? 0 : -1}
                  onClick={() => choose(i)}
                  className={`relative flex min-h-11 items-center justify-center gap-1.5 px-1 text-[0.8125rem] font-medium transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-cs-accent ${
                    on ? "text-cs-ink" : "text-cs-ink-3 hover:text-cs-ink"
                  } ${i ? "border-l border-cs-line" : ""}`}
                >
                  <s.Icon aria-hidden className="size-3.5 shrink-0" />
                  <span className="sm:hidden">{s.short}</span>
                  <span className="hidden sm:inline">{s.label}</span>
                  <span aria-hidden className="absolute inset-x-0 top-0 h-0.5">
                    {on && (
                      <span
                        key={`${step}-${running}`}
                        className="block h-full bg-cs-accent"
                        style={
                          running
                            ? { animation: `cs-hero-fill ${STEP_MS}ms linear both` }
                            : { width: "100%" }
                        }
                      />
                    )}
                  </span>
                </button>
              );
            })}
          </div>
          {!reduced && (
            <button
              type="button"
              onClick={() => {
                shown.current = 0;
                setStopped((s) => !s);
              }}
              aria-label={stopped ? "Play the tour" : "Pause the tour"}
              className="flex w-11 shrink-0 items-center justify-center border-l border-cs-line text-cs-ink-3 transition-colors hover:text-cs-ink focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-cs-accent"
            >
              {stopped ? <Play aria-hidden className="size-3.5" /> : <Pause aria-hidden className="size-3.5" />}
            </button>
          )}
        </div>
      </div>
      <figcaption className="sr-only">
        A map of the contiguous United States with a dot for every live incident, closure, chain control and wildfire,
        refreshed about every 30 seconds, with the current count of each.
      </figcaption>
      <style>{`@keyframes cs-hero-fill{from{width:0}to{width:100%}}
.cs-hero-card{animation:cs-hero-in .35s var(--cs-ease) both}
@keyframes cs-hero-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion: reduce){.cs-hero-card{animation:none}}`}</style>
    </figure>
  );
}
