"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ArrowLeft, ArrowLeftRight, ArrowRight, Check, Columns2, LayoutGrid, Link2, Monitor } from "lucide-react";

// Click-through viewer for the map sidebar board. The page (a server
// component) renders every mockup; this only decides which one shows.
// State lives in the URL hash so a view can be shared: #7, #compare-1-2,
// #all, #today, #others, #where, #pick-c.

export type BoardOption = {
  n: number;
  name: string;
  tag?: string;
  diff: string;
  idea: string;
  moved: string[];
  plus: string;
  minus: string;
  desk: React.ReactNode;
  desk2?: React.ReactNode;
  phone?: React.ReactNode;
  phone2?: React.ReactNode;
};

export type BoardStep = { id: string; letter: string; title: string; body: string; phone: boolean; node: React.ReactNode };

type View =
  | { v: "opt"; n: number }
  | { v: "all" }
  | { v: "compare"; a: number; b: number }
  | { v: "today" | "others" | "where" }
  | { v: "pick"; s: string };

const COUNT = 15;
const clampN = (n: number) => (Number.isFinite(n) && n >= 1 && n <= COUNT ? n : 1);

function parse(hash: string): View {
  const h = hash.replace(/^#/, "");
  if (!h) return { v: "opt", n: 1 };
  if (/^\d+$/.test(h)) return { v: "opt", n: clampN(+h) };
  const opt = /^opt-(\d+)$/.exec(h);
  if (opt) return { v: "opt", n: clampN(+opt[1]) };
  if (h === "all" || h === "options") return { v: "all" };
  const cmp = /^compare(?:-(\d+)-(\d+))?$/.exec(h);
  if (cmp) return { v: "compare", a: clampN(+(cmp[1] ?? 1)), b: clampN(+(cmp[2] ?? 2)) };
  if (h === "today" || h === "others" || h === "where") return { v: h };
  const pick = /^pick(?:-([a-i]))?$/.exec(h);
  if (pick) return { v: "pick", s: pick[1] ?? "a" };
  return { v: "opt", n: 1 };
}

function toHash(v: View) {
  switch (v.v) {
    case "opt":
      return `#${v.n}`;
    case "compare":
      return `#compare-${v.a}-${v.b}`;
    case "pick":
      return `#pick-${v.s}`;
    default:
      return `#${v.v}`;
  }
}

const subscribe = (cb: () => void) => {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
};

function go(v: View, scroll = true) {
  const h = toHash(v);
  if (window.location.hash !== h) window.location.hash = h;
  if (scroll && window.scrollY > 0) window.scrollTo({ top: 0 });
}

const pad = (n: number) => String(n).padStart(2, "0");

function isTyping(t: EventTarget | null) {
  const el = t as HTMLElement | null;
  if (!el) return false;
  return !!el.closest("input, textarea, select, [contenteditable=true], [role=tablist]");
}

export function Board({
  options,
  steps,
  today,
  others,
  where,
  pickSpec,
}: {
  options: BoardOption[];
  steps: BoardStep[];
  today: React.ReactNode;
  others: React.ReactNode;
  where: React.ReactNode;
  pickSpec: React.ReactNode;
}) {
  const hash = useSyncExternalStore(
    subscribe,
    () => window.location.hash,
    () => "",
  );
  const view = parse(hash);

  // Left and Right step through options (or pick-on-map steps) anywhere on the page.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.metaKey || e.ctrlKey || e.shiftKey || isTyping(e.target)) return;
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const d = e.key === "ArrowRight" ? 1 : -1;
      const cur = parse(window.location.hash);
      if (cur.v === "opt") {
        e.preventDefault();
        go({ v: "opt", n: ((cur.n - 1 + d + COUNT) % COUNT) + 1 }, false);
      } else if (cur.v === "pick") {
        e.preventDefault();
        const i = steps.findIndex((s) => s.id === cur.s);
        go({ v: "pick", s: steps[(i + d + steps.length) % steps.length].id }, false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps]);

  const section = view.v === "opt" ? "opt" : view.v;
  const tabs: [string, string, View][] = [
    ["opt", "One at a time", { v: "opt", n: view.v === "opt" ? view.n : 1 }],
    ["all", "All 15", { v: "all" }],
    ["compare", "Compare two", { v: "compare", a: view.v === "opt" ? view.n : 1, b: view.v === "opt" && view.n !== 2 ? 2 : 1 }],
  ];
  const research: [string, string, View][] = [
    ["today", "The map today", { v: "today" }],
    ["others", "Other maps", { v: "others" }],
    ["where", "What goes where", { v: "where" }],
    ["pick", "Pick on map", { v: "pick", s: "a" }],
  ];

  return (
    <div className="msb msb-ui min-h-screen">
      <div className="sticky top-[var(--cs-header-h,64px)] z-30 border-b border-cs-line bg-cs-bg">
        <div className="mx-auto flex max-w-[1680px] items-center gap-x-5 gap-y-1 overflow-x-auto px-4 py-2 sm:px-6">
          <span className="shrink-0 text-sm font-semibold">
            Map sidebar <span className="font-normal text-cs-ink-3">· lab</span>
          </span>
          <nav aria-label="Board views" className="flex shrink-0 items-center gap-1 text-sm">
            {tabs.map(([id, label, v]) => (
              <TopLink key={id} active={section === id} onClick={() => go(v)} href={toHash(v)}>
                {id === "opt" ? <Monitor size={14} /> : id === "all" ? <LayoutGrid size={14} /> : <Columns2 size={14} />}
                {label}
              </TopLink>
            ))}
            <span className="mx-2 h-5 w-px bg-cs-line" aria-hidden="true" />
            <span className="mr-1 text-xs text-cs-ink-3">Background:</span>
            {research.map(([id, label, v]) => (
              <TopLink key={id} active={section === id} onClick={() => go(v)} href={toHash(v)}>
                {label}
              </TopLink>
            ))}
          </nav>
        </div>
        {view.v === "opt" ? <OptionTabs options={options} current={view.n} /> : null}
      </div>

      <main className="mx-auto max-w-[1680px] px-4 pb-24 pt-6 sm:px-6">
        {view.v === "opt" ? <OptionStage options={options} n={view.n} /> : null}
        {view.v === "all" ? <AllGrid options={options} /> : null}
        {view.v === "compare" ? <Compare options={options} a={view.a} b={view.b} /> : null}
        {view.v === "today" ? <Prose>{today}</Prose> : null}
        {view.v === "others" ? <Prose>{others}</Prose> : null}
        {view.v === "where" ? <Prose>{where}</Prose> : null}
        {view.v === "pick" ? <PickStage steps={steps} s={view.s} spec={pickSpec} /> : null}
      </main>
    </div>
  );
}

function TopLink({ active, onClick, href, children }: { active: boolean; onClick: () => void; href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      aria-current={active ? "page" : undefined}
      onClick={(e) => {
        e.preventDefault();
        onClick();
      }}
      className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[8px] px-2.5 py-1.5 ${
        active ? "bg-cs-ink text-cs-bg" : "text-cs-ink-2 hover:bg-cs-surface-2 hover:text-cs-ink"
      }`}
    >
      {children}
    </a>
  );
}

/* Option tabs: a strip of all 15, keyboard-operable (arrows, Home, End). */
function OptionTabs({ options, current }: { options: BoardOption[]; current: number }) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-n="${current}"]`);
    el?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [current]);
  const move = (n: number) => {
    go({ v: "opt", n }, false);
    requestAnimationFrame(() => listRef.current?.querySelector<HTMLElement>(`[data-n="${n}"]`)?.focus());
  };
  return (
    <div className="border-t border-cs-line">
      <div
        ref={listRef}
        role="tablist"
        aria-label="Fifteen sidebar options"
        className="mx-auto flex max-w-[1680px] gap-1 overflow-x-auto px-4 py-2 sm:px-6 xl:flex-wrap xl:overflow-visible"
        onKeyDown={(e) => {
          const map: Record<string, number> = {
            ArrowRight: (current % COUNT) + 1,
            ArrowLeft: ((current - 2 + COUNT) % COUNT) + 1,
            Home: 1,
            End: COUNT,
          };
          if (e.key in map) {
            e.preventDefault();
            move(map[e.key]);
          }
        }}
      >
        {options.map((o) => {
          const sel = o.n === current;
          return (
            <button
              key={o.n}
              id={`tab-${o.n}`}
              data-n={o.n}
              type="button"
              role="tab"
              aria-selected={sel}
              aria-controls="option-panel"
              tabIndex={sel ? 0 : -1}
              onClick={() => go({ v: "opt", n: o.n }, false)}
              className={`flex shrink-0 items-center gap-2 whitespace-nowrap rounded-[8px] border px-2.5 py-1.5 text-[13px] ${
                sel ? "border-cs-accent bg-cs-accent text-cs-accent-ink" : "border-cs-line bg-cs-surface text-cs-ink hover:border-cs-line-strong"
              }`}
            >
              <span className={`font-mono text-[12px] ${sel ? "" : "text-cs-ink-3"}`}>{pad(o.n)}</span>
              {o.name}
              {o.tag ? (
                <span
                  className={`rounded-full px-1.5 text-[10.5px] font-semibold ${sel ? "bg-cs-accent-ink/20" : "bg-cs-accent-soft text-cs-accent"}`}
                >
                  {o.tag === "Top pick" ? "Top" : "2nd"}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Tag({ tag }: { tag?: string }) {
  if (!tag) return null;
  return <span className="rounded-full bg-cs-accent px-2.5 py-0.5 text-xs font-semibold text-cs-accent-ink">{tag}</span>;
}

function GoodCost({ o, compact = false }: { o: BoardOption; compact?: boolean }) {
  return (
    <div className={compact ? "space-y-2 text-sm" : "space-y-3 text-[15px]"}>
      <p>
        <span className="font-semibold text-cs-ok">Good: </span>
        {o.plus}
      </p>
      <p>
        <span className="font-semibold text-cs-closure">Cost: </span>
        {o.minus}
      </p>
    </div>
  );
}

function CopyLink({ hash }: { hash: string }) {
  const [done, setDone] = useState(false);
  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(window.location.origin + window.location.pathname + hash);
      setDone(true);
      window.setTimeout(() => setDone(false), 1600);
    } catch {
      /* clipboard blocked: the hash is still in the address bar */
    }
  }, [hash]);
  return (
    <button type="button" onClick={copy} className="flex items-center gap-1.5 rounded-[8px] border border-cs-line px-2.5 py-1.5 text-sm text-cs-ink-2 hover:text-cs-ink">
      {done ? <Check size={14} /> : <Link2 size={14} />}
      <span aria-live="polite">{done ? "Copied" : `Copy link (${hash})`}</span>
    </button>
  );
}

function OptionStage({ options, n }: { options: BoardOption[]; n: number }) {
  const o = options[n - 1];
  const prev = options[(n - 2 + COUNT) % COUNT];
  const next = options[n % COUNT];
  const [routeOn, setRouteOn] = useState(false);
  const hasRoute = !!o.desk2;
  const showRoute = hasRoute && routeOn;
  const desk = showRoute ? o.desk2 : o.desk;
  const phone = showRoute && o.phone2 ? o.phone2 : o.phone;

  return (
    <div id="option-panel" role="tabpanel" aria-labelledby={`tab-${n}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0 max-w-3xl">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-mono text-3xl text-cs-ink-3">{pad(o.n)}</span>
            <h1 className="text-3xl font-semibold tracking-tight">{o.name}</h1>
            <Tag tag={o.tag} />
          </div>
          <p className="mt-2 text-lg text-cs-ink-2">{o.diff}</p>
        </div>
        <div className="flex items-center gap-2">
          <StepBtn dir="prev" onClick={() => go({ v: "opt", n: prev.n }, false)} label={`Previous: ${prev.n}, ${prev.name}`}>
            {pad(prev.n)}
          </StepBtn>
          <StepBtn dir="next" onClick={() => go({ v: "opt", n: next.n }, false)} label={`Next: ${next.n}, ${next.name}`}>
            {pad(next.n)}
          </StepBtn>
        </div>
      </div>

      <div className="mt-5 grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          {hasRoute ? (
            <div className="mb-3 flex items-center gap-3 text-sm">
              <span className="text-cs-ink-3" id="state-label">
                Show
              </span>
              <div role="group" aria-labelledby="state-label" className="flex rounded-[9px] bg-cs-surface-2 p-0.5">
                {[
                  [false, "Before you search"],
                  [true, "With a route planned"],
                ].map(([v, l]) => (
                  <button
                    key={l as string}
                    type="button"
                    aria-pressed={routeOn === v}
                    onClick={() => setRouteOn(v as boolean)}
                    className={`rounded-[7px] px-3 py-1 ${routeOn === v ? "bg-cs-surface font-medium text-cs-ink shadow-[var(--cs-shadow-sm)]" : "text-cs-ink-2"}`}
                  >
                    {l as string}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {desk}
        </div>

        <aside className="flex flex-col gap-5" aria-label={`About option ${o.n}`}>
          <GoodCost o={o} />
          <div>
            <h2 className="cs-eyebrow">The idea</h2>
            <p className="mt-1.5 text-sm text-cs-ink-2">{o.idea}</p>
          </div>
          <div>
            <h2 className="cs-eyebrow">What moved</h2>
            <ul className="mt-1.5 list-disc space-y-1 pl-4 text-sm text-cs-ink-2">
              {o.moved.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
          {phone ? (
            <div className="max-w-[300px]">
              <h2 className="cs-eyebrow mb-2">On a phone</h2>
              {phone}
            </div>
          ) : (
            <p className="text-sm text-cs-ink-3">No phone view drawn for this one. Phone views exist for 1, 2, 6, 11 and 13.</p>
          )}
        </aside>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-cs-line pt-5">
        <button type="button" onClick={() => go({ v: "opt", n: prev.n })} className="flex items-center gap-2 rounded-[10px] border border-cs-line px-4 py-2.5 text-left hover:border-cs-line-strong">
          <ArrowLeft size={16} />
          <span>
            <span className="block text-xs text-cs-ink-3">Previous</span>
            {pad(prev.n)} {prev.name}
          </span>
        </button>
        <div className="flex flex-wrap items-center gap-3 text-sm text-cs-ink-3">
          <span>
            Or use <kbd className="msb-kbd">←</kbd> <kbd className="msb-kbd">→</kbd>
          </span>
          <CopyLink hash={`#${o.n}`} />
          <button
            type="button"
            onClick={() => go({ v: "compare", a: o.n, b: o.n === 1 ? 2 : 1 })}
            className="flex items-center gap-1.5 rounded-[8px] border border-cs-line px-2.5 py-1.5 text-cs-ink-2 hover:text-cs-ink"
          >
            <Columns2 size={14} /> Compare with…
          </button>
        </div>
        <button type="button" onClick={() => go({ v: "opt", n: next.n })} className="flex items-center gap-2 rounded-[10px] border border-cs-line px-4 py-2.5 text-right hover:border-cs-line-strong">
          <span>
            <span className="block text-xs text-cs-ink-3">Next</span>
            {pad(next.n)} {next.name}
          </span>
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}

function StepBtn({ dir, onClick, label, children }: { dir: "prev" | "next"; onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="flex h-10 items-center gap-1.5 rounded-[10px] border border-cs-line bg-cs-surface px-3 font-mono text-sm hover:border-cs-line-strong"
    >
      {dir === "prev" ? <ArrowLeft size={16} /> : null}
      {children}
      {dir === "next" ? <ArrowRight size={16} /> : null}
    </button>
  );
}

function AllGrid({ options }: { options: BoardOption[] }) {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">All fifteen sidebars</h1>
      <p className="mt-2 max-w-3xl text-cs-ink-2">
        Recommended: <b className="text-cs-ink">1, Where to?</b>, using 11’s strip for results and 13’s drives once someone is signed in. Runner-up:{" "}
        <b className="text-cs-ink">2, Search-first card</b>. Click any one to open it large.
      </p>
      <ul className="mt-6 grid gap-x-5 gap-y-8 sm:grid-cols-2 xl:grid-cols-3">
        {options.map((o) => (
          <li key={o.n}>
            <a
              href={`#${o.n}`}
              onClick={(e) => {
                e.preventDefault();
                go({ v: "opt", n: o.n });
              }}
              className="group block rounded-[var(--cs-radius-md)]"
            >
              <div className="transition-opacity group-hover:opacity-90">{o.desk}</div>
              <div className="mt-2.5 flex items-baseline gap-2">
                <span className="font-mono text-sm text-cs-ink-3">{pad(o.n)}</span>
                <span className="font-semibold group-hover:underline">{o.name}</span>
                <Tag tag={o.tag} />
              </div>
              <p className="mt-1 text-sm text-cs-ink-2">{o.diff}</p>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Compare({ options, a, b }: { options: BoardOption[]; a: number; b: number }) {
  const set = (side: "a" | "b", n: number) => go({ v: "compare", a: side === "a" ? n : a, b: side === "b" ? n : b }, false);
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">Compare two</h1>
        <button
          type="button"
          onClick={() => go({ v: "compare", a: b, b: a }, false)}
          className="flex items-center gap-1.5 rounded-[8px] border border-cs-line px-2.5 py-1.5 text-sm text-cs-ink-2 hover:text-cs-ink"
        >
          <ArrowLeftRight size={14} /> Swap sides
        </button>
      </div>
      <div className="mt-5 grid gap-8 lg:grid-cols-2">
        {(
          [
            ["a", a],
            ["b", b],
          ] as const
        ).map(([side, n]) => {
          const o = options[n - 1];
          return (
            <section key={side} aria-label={`${side === "a" ? "Left" : "Right"}: option ${o.n}`}>
              <label className="flex items-center gap-2 text-sm">
                <span className="text-cs-ink-3">{side === "a" ? "Left" : "Right"}</span>
                <select
                  value={n}
                  onChange={(e) => set(side, +e.target.value)}
                  className="min-w-0 flex-1 rounded-[8px] border border-cs-line bg-cs-surface px-2.5 py-2 text-[15px] font-semibold text-cs-ink"
                >
                  {options.map((x) => (
                    <option key={x.n} value={x.n}>
                      {pad(x.n)} {x.name}
                      {x.tag ? ` (${x.tag})` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <p className="mt-3 min-h-[3em] text-cs-ink-2">{o.diff}</p>
              <div className="mt-3">{o.desk}</div>
              <div className="mt-4">
                <GoodCost o={o} compact />
              </div>
              <a
                href={`#${o.n}`}
                onClick={(e) => {
                  e.preventDefault();
                  go({ v: "opt", n: o.n });
                }}
                className="mt-3 inline-block text-sm text-cs-accent underline-offset-4 hover:underline"
              >
                Open {o.n} large, with its phone view
              </a>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function Prose({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-[1280px]">{children}</div>;
}

/* Pick on map: one storyboard frame at a time, large enough to read. */
function PickStage({ steps, s, spec }: { steps: BoardStep[]; s: string; spec: React.ReactNode }) {
  const i = Math.max(0, steps.findIndex((x) => x.id === s));
  const st = steps[i];
  const listRef = useRef<HTMLDivElement>(null);
  const move = (j: number) => {
    const id = steps[(j + steps.length) % steps.length].id;
    go({ v: "pick", s: id }, false);
    requestAnimationFrame(() => listRef.current?.querySelector<HTMLElement>(`[data-s="${id}"]`)?.focus());
  };
  return (
    <div className="mx-auto max-w-[1440px]">
      <h1 className="text-3xl font-semibold tracking-tight">Pick on map, for someone who has never done it</h1>
      <p className="mt-2 max-w-3xl text-cs-ink-2">
        The person may not know exactly where to click. So every step says what to do next, the spot can be adjusted before it counts, and every step has an
        obvious way back. Nine steps; use the list or <kbd className="msb-kbd">←</kbd> <kbd className="msb-kbd">→</kbd>.
      </p>
      <div className="mt-6 grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <div
          ref={listRef}
          role="tablist"
          aria-label="Pick on map steps"
          aria-orientation="vertical"
          className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible"
          onKeyDown={(e) => {
            if (e.key === "ArrowDown" || e.key === "ArrowRight") {
              e.preventDefault();
              move(i + 1);
            } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
              e.preventDefault();
              move(i - 1);
            }
          }}
        >
          {steps.map((x) => {
            const sel = x.id === st.id;
            return (
              <button
                key={x.id}
                id={`step-${x.id}`}
                data-s={x.id}
                type="button"
                role="tab"
                aria-selected={sel}
                aria-controls="step-panel"
                tabIndex={sel ? 0 : -1}
                onClick={() => go({ v: "pick", s: x.id }, false)}
                className={`flex shrink-0 items-baseline gap-2.5 rounded-[8px] px-3 py-2 text-left text-sm ${
                  sel ? "bg-cs-ink text-cs-bg" : "text-cs-ink-2 hover:bg-cs-surface-2 hover:text-cs-ink"
                }`}
              >
                <span className="font-mono text-xs">{x.letter}</span>
                <span className="whitespace-nowrap lg:whitespace-normal">{x.title}</span>
              </button>
            );
          })}
        </div>
        <div id="step-panel" role="tabpanel" aria-labelledby={`step-${st.id}`} className="min-w-0">
          <div className={st.phone ? "grid items-start gap-6 md:grid-cols-[minmax(0,380px)_1fr]" : ""}>
            <div className={st.phone ? "" : "max-w-[1040px]"}>{st.node}</div>
            <div className={st.phone ? "" : "mt-4 max-w-[1040px]"}>
              <div className="font-mono text-xs text-cs-ink-3">Step {st.letter} of I</div>
              <h2 className="mt-1 text-xl font-semibold">{st.title}</h2>
              <p className="mt-1.5 max-w-2xl text-cs-ink-2">{st.body}</p>
              <div className="mt-4 flex gap-2">
                <StepBtn dir="prev" onClick={() => move(i - 1)} label="Previous step">
                  {steps[(i - 1 + steps.length) % steps.length].letter}
                </StepBtn>
                <StepBtn dir="next" onClick={() => move(i + 1)} label="Next step">
                  {steps[(i + 1) % steps.length].letter}
                </StepBtn>
              </div>
            </div>
          </div>
        </div>
      </div>
      <h2 className="mt-14 text-2xl font-semibold">The spec</h2>
      <div className="mt-4">{spec}</div>
    </div>
  );
}
