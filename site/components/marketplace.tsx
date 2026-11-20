"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { LayoutGrid, List, Rows3, Search, SlidersHorizontal, X } from "lucide-react";
import {
  CAPS,
  GROUP_META,
  OFF_KEY,
  ON_KEY,
  activeCount,
  emptyFilters,
  idSet,
  passes,
  saveSet,
  tierOf,
  type FacetId,
  type Filters,
  type Group,
  type Source,
  type Tier,
} from "./marketplace/data";
import { FacetPanel } from "./marketplace/facets";
import { TIER_META } from "./marketplace/parts";
import { Card, Featured, ListHead, ListRow, UNREVIEWED_NOTE } from "./marketplace/views";
import "./marketplace/marketplace.css";

// The plugin marketplace, read live from /api/flare/sources. "Install" on
// the web turns the plugin's layer on for this browser (the map reads the
// same key); the apps keep their own switch per phone. An unlisted plugin is
// never in the catalog: it is shared by link (/marketplace?plugin=<id>) and
// shows on the map only once installed here, so a second key holds those.
//
// Layout: a featured banner, then a facet rail (a sheet on phones) beside
// the results, grouped into trust shelves by default, as a list or as cards.

const VIEW_KEY = "cs.marketplace.view";
const TIER_ORDER: Tier[] = ["private", "approved", "unreviewed"];

type View = "list" | "cards";

export function Marketplace() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [off, setOff] = useState<Set<string>>(new Set());
  const [on, setOn] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [view, setView] = useState<View>("list");
  const [grouped, setGrouped] = useState(true);
  const sheet = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    // The browser's own switches are read once the catalog arrives, so no
    // state is set synchronously inside the effect. A ?plugin=<id> link
    // brings an unlisted plugin along, fetched by id and shown first.
    const wanted = new URLSearchParams(window.location.search).get("plugin") || "";
    const headers = { Accept: "application/json" };
    const catalog = fetch("/api/flare/sources", { headers }).then((r) => (r.ok ? r.json() : Promise.reject(r.status)));
    const extra = wanted
      ? fetch("/api/flare/sources?id=" + encodeURIComponent(wanted), { headers })
          .then((r) => (r.ok ? r.json() : { sources: [] }))
          .catch(() => ({ sources: [] }))
      : Promise.resolve({ sources: [] });
    Promise.all([catalog, extra])
      .then(([d, e]) => {
        const listed: Source[] = Array.isArray(d.sources) ? d.sources : [];
        const linked: Source[] = (Array.isArray(e.sources) ? e.sources : []).filter(
          (s: Source) => !listed.some((l) => l.id === s.id),
        );
        setOff(idSet(OFF_KEY));
        setOn(idSet(ON_KEY));
        try {
          const v = localStorage.getItem(VIEW_KEY);
          if (v === "cards" || v === "list") setView(v);
        } catch {
          /* private mode */
        }
        setSources([...linked, ...listed]);
      })
      .catch(() => setFailed(true));
  }, []);

  function isInstalled(s: Source) {
    return s.visibility === "unlisted" ? on.has(s.id) : !off.has(s.id);
  }

  function toggle(s: Source) {
    if (s.visibility === "unlisted") {
      const next = new Set(on);
      if (next.has(s.id)) next.delete(s.id);
      else next.add(s.id);
      setOn(next);
      saveSet(ON_KEY, next);
      return;
    }
    const next = new Set(off);
    if (next.has(s.id)) next.delete(s.id);
    else next.add(s.id);
    setOff(next);
    saveSet(OFF_KEY, next);
  }

  function pickView(v: View) {
    setView(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* private mode */
    }
  }

  if (failed) {
    return (
      <p role="status" className="mt-10 rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-6 text-sm text-cs-ink-2">
        The marketplace could not be loaded right now. Try again in a minute.
      </p>
    );
  }
  if (sources === null) {
    return (
      <p role="status" className="mt-10 rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-6 text-sm text-cs-ink-3">
        Loading plugins…
      </p>
    );
  }
  if (sources.length === 0) {
    return <p className="mt-10 rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-6 text-cs-ink-2">No plugin is listed yet.</p>;
  }

  const total = sources.length;
  const results = sources.filter((s) => passes(s, filters, isInstalled(s)));
  const nActive = activeCount(filters);
  const browsing = nActive === 0 && !filters.q;

  // The banner goes to the busiest approved, listed plugin, and only while
  // nobody is narrowing the list.
  const featured = sources
    .filter((s) => tierOf(s) === "approved" && s.visibility !== "unlisted")
    .sort((a, b) => (b.count ?? 0) - (a.count ?? 0))[0];
  const showBanner = browsing && !!featured;

  const ctl = { isInstalled, onToggle: toggle };
  const clearAll = () => setFilters(emptyFilters());

  const panel = (prefix: string) => (
    <FacetPanel sources={sources} filters={filters} setFilters={setFilters} isInstalled={isInstalled} idPrefix={prefix} />
  );

  function block(items: Source[], showTrust: boolean) {
    if (view === "list") {
      return (
        <div className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface">
          <ListHead showTrust={showTrust} />
          <ul className="divide-y divide-cs-line">
            {items.map((s) => (
              <ListRow key={s.id} s={s} showTrust={showTrust} {...ctl} />
            ))}
          </ul>
        </div>
      );
    }
    return (
      <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {items.map((s) => (
          <Card key={s.id} s={s} showTrust={showTrust} featured={showBanner && s.id === featured?.id} {...ctl} />
        ))}
      </ul>
    );
  }

  return (
    <div className="mk mt-10 md:mt-14">
      {showBanner && featured && <Featured s={featured} {...ctl} />}

      <div className={"lg:grid lg:grid-cols-[224px_minmax(0,1fr)] lg:gap-10 " + (showBanner ? "mt-12" : "")}>
        {/* Facet rail, wide screens */}
        <aside aria-labelledby="mk-filters-h" className="hidden lg:sticky lg:top-24 lg:block lg:self-start">
          <div className="mb-4 flex items-baseline justify-between px-2">
            <h2 id="mk-filters-h" className="text-sm font-semibold text-cs-ink">
              Filters
            </h2>
            {nActive > 0 && (
              <button type="button" onClick={clearAll} className="text-xs font-medium text-cs-accent hover:underline">
                Clear all
              </button>
            )}
          </div>
          {panel("rail")}
        </aside>

        <div className="min-w-0">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <label className="relative min-w-0 flex-1 basis-full sm:basis-auto">
              <span className="sr-only">Search plugins</span>
              <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-cs-ink-3" />
              <input
                type="search"
                value={filters.q}
                onChange={(e) => setFilters({ ...filters, q: e.target.value })}
                placeholder="Search plugins"
                className="h-10 w-full rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface pl-9 pr-3 text-sm text-cs-ink placeholder:text-cs-ink-3 focus-visible:border-cs-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cs-accent/30"
              />
            </label>
            <button
              type="button"
              onClick={() => sheet.current?.showModal()}
              className="inline-flex h-10 items-center gap-2 rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface px-3.5 text-sm font-medium text-cs-ink hover:bg-cs-surface-2 lg:hidden"
              aria-haspopup="dialog"
            >
              <SlidersHorizontal aria-hidden className="size-4" />
              Filters
              {nActive > 0 && (
                <span className="cs-data rounded-full bg-cs-accent px-1.5 text-[11px] text-cs-accent-ink">{nActive}</span>
              )}
            </button>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                aria-pressed={grouped}
                onClick={() => setGrouped(!grouped)}
                className={
                  "inline-flex h-10 items-center gap-2 rounded-[var(--cs-radius-md)] border px-3 text-sm font-medium transition-colors " +
                  (grouped ? "border-cs-line-strong bg-cs-surface-2 text-cs-ink" : "border-cs-line bg-cs-surface text-cs-ink-2 hover:bg-cs-surface-2")
                }
              >
                <Rows3 aria-hidden className="size-4" />
                <span className="hidden sm:inline">Group by trust</span>
                <span className="sm:hidden">By trust</span>
              </button>
              <div role="group" aria-label="View" className="inline-flex rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface p-0.5">
                {(
                  [
                    ["list", "List", List],
                    ["cards", "Cards", LayoutGrid],
                  ] as const
                ).map(([v, label, Icon]) => (
                  <button
                    key={v}
                    type="button"
                    aria-pressed={view === v}
                    onClick={() => pickView(v)}
                    className={
                      "inline-flex h-8 items-center gap-1.5 rounded-[calc(var(--cs-radius-md)-2px)] px-2.5 text-sm font-medium transition-colors " +
                      (view === v ? "bg-cs-surface-2 text-cs-ink" : "text-cs-ink-3 hover:text-cs-ink")
                    }
                  >
                    <Icon aria-hidden className="size-4" />
                    <span className="hidden sm:inline">{label}</span>
                    <span className="sr-only sm:hidden">{label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Phones: the trust facet as a quick chip row (the full set is in the sheet) */}
          <QuickTrust sources={sources} filters={filters} setFilters={setFilters} isInstalled={isInstalled} />

          {/* Count and the active filters, removable one by one */}
          <div className="mt-4 flex min-h-8 flex-wrap items-center gap-2">
            <p role="status" aria-live="polite" className="mr-1 text-sm text-cs-ink-3">
              {results.length === total
                ? `${total} ${total === 1 ? "plugin" : "plugins"}`
                : `${results.length} of ${total} plugins`}
            </p>
            <ActiveChips filters={filters} setFilters={setFilters} />
            {(nActive > 0 || filters.q) && (
              <button type="button" onClick={clearAll} className="text-sm font-medium text-cs-accent hover:underline">
                Clear all
              </button>
            )}
          </div>

          {/* Results */}
          <div className="mt-4 flex flex-col gap-10">
            {results.length === 0 ? (
              <div className="rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-8 text-center">
                <p className="font-medium text-cs-ink">No plugin matches these filters.</p>
                <button type="button" onClick={clearAll} className="mt-3 text-sm font-medium text-cs-accent hover:underline">
                  Clear filters
                </button>
              </div>
            ) : grouped ? (
              TIER_ORDER.filter((t) => results.some((s) => tierOf(s) === t)).map((t) => {
                const items = results.filter((s) => tierOf(s) === t);
                const { Icon, shelf, why } = TIER_META[t];
                return (
                  <section key={t} aria-labelledby={`mk-shelf-${t}`} data-tier={t}>
                    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-1 pb-3">
                      <h2 id={`mk-shelf-${t}`} className="flex items-center gap-2.5 text-lg font-semibold text-cs-ink">
                        <span aria-hidden className="mk-t-bg inline-flex size-7 items-center justify-center rounded-[var(--cs-radius-sm)]">
                          <Icon className="size-4" />
                        </span>
                        {shelf}
                        <span className="cs-data text-sm font-normal text-cs-ink-3">{items.length}</span>
                      </h2>
                      <p className="text-sm text-cs-ink-3">{why}</p>
                    </div>
                    <div aria-hidden className="mk-t-rule mb-4" />
                    {t === "unreviewed" && (
                      <p className="mb-4 flex gap-3 rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface p-4 text-sm leading-relaxed text-cs-ink-2">
                        <span aria-hidden className="mk-t-dot w-1 shrink-0 rounded-full" />
                        <span>
                          <strong className="font-semibold text-cs-ink">Before you install one. </strong>
                          {UNREVIEWED_NOTE}
                        </span>
                      </p>
                    )}
                    {block(items, false)}
                  </section>
                );
              })
            ) : (
              <>
                {view === "list" && results.some((s) => tierOf(s) === "unreviewed") && (
                  <p className="text-xs leading-relaxed text-cs-ink-3">Plugins marked not reviewed: {UNREVIEWED_NOTE}</p>
                )}
                {block(
                  [...results].sort((a, b) => TIER_ORDER.indexOf(tierOf(a)) - TIER_ORDER.indexOf(tierOf(b))),
                  true,
                )}
              </>
            )}
          </div>

          {/* Invite */}
          <div className="mt-12 flex flex-col gap-3 rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-cs-ink">Run a feed people could use?</p>
              <p className="mt-1 max-w-[62ch] text-sm leading-relaxed text-cs-ink-2">
                Any plugin that passes the conformance check can be listed. Approval adds a review: the operator is known and the feed
                passed it.
              </p>
            </div>
            <Link href="/plugins" prefetch={false} className="cs-link inline-flex min-h-6 shrink-0 items-center text-sm">
              Write a plugin
            </Link>
          </div>
        </div>
      </div>

      {/* Filters sheet, below lg */}
      <dialog
        ref={sheet}
        aria-labelledby="mk-sheet-h"
        className="mk-sheet"
        onClick={(e) => e.target === sheet.current && sheet.current?.close()}
      >
        <div className="flex max-h-[88dvh] flex-col">
          <div className="flex items-center justify-between border-b border-cs-line px-5 py-3">
            <h2 id="mk-sheet-h" className="text-base font-semibold">
              Filters
            </h2>
            <button
              type="button"
              onClick={() => sheet.current?.close()}
              className="inline-flex size-10 items-center justify-center rounded-[var(--cs-radius-md)] text-cs-ink-2 hover:bg-cs-surface-2"
            >
              <X aria-hidden className="size-5" />
              <span className="sr-only">Close filters</span>
            </button>
          </div>
          <div className="overflow-y-auto px-3 py-4">{panel("sheet")}</div>
          <div className="flex items-center justify-between gap-3 border-t border-cs-line px-5 py-3">
            <button
              type="button"
              onClick={clearAll}
              disabled={nActive === 0}
              className="text-sm font-medium text-cs-accent hover:underline disabled:text-cs-ink-3 disabled:no-underline"
            >
              Clear all
            </button>
            <button
              type="button"
              onClick={() => sheet.current?.close()}
              className="inline-flex h-10 items-center rounded-[var(--cs-radius-md)] bg-cs-accent px-4 text-sm font-medium text-cs-accent-ink hover:bg-cs-accent-hover"
            >
              Show {results.length} {results.length === 1 ? "plugin" : "plugins"}
            </button>
          </div>
        </div>
      </dialog>
    </div>
  );
}

function QuickTrust({
  sources,
  filters,
  setFilters,
  isInstalled,
}: {
  sources: Source[];
  filters: Filters;
  setFilters: (f: Filters) => void;
  isInstalled: (s: Source) => boolean;
}) {
  const tiers = (["approved", "unreviewed", "private"] as Tier[])
    .map((t) => ({
      t,
      global: sources.filter((s) => tierOf(s) === t).length,
      live: sources.filter((s) => tierOf(s) === t && passes(s, filters, isInstalled(s), "trust")).length,
    }))
    .filter((x) => x.global > 0);
  if (tiers.length < 2) return null;
  return (
    <div role="group" aria-label="Trust" className="mk-scroll -mx-4 mt-3 flex gap-2 overflow-x-auto px-4 lg:hidden">
      {tiers.map(({ t, live }) => {
        const pressed = filters.trust.has(t);
        const { Icon, short } = TIER_META[t];
        return (
          <button
            key={t}
            type="button"
            data-tier={t}
            aria-pressed={pressed}
            disabled={live === 0 && !pressed}
            onClick={() => {
              const next = new Set(filters.trust);
              if (pressed) next.delete(t);
              else next.add(t);
              setFilters({ ...filters, trust: next });
            }}
            className={
              "inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3 text-sm font-medium transition-colors disabled:opacity-50 " +
              (pressed ? "mk-t-bg border-transparent" : "border-cs-line bg-cs-surface text-cs-ink-2")
            }
          >
            <Icon aria-hidden className="mk-t size-4" />
            {short}
            <span className="cs-data text-xs opacity-75">{live}</span>
          </button>
        );
      })}
    </div>
  );
}

function ActiveChips({ filters, setFilters }: { filters: Filters; setFilters: (f: Filters) => void }) {
  const labelOf = (id: FacetId, v: string): string => {
    if (id === "trust") return TIER_META[v as Tier].short;
    if (id === "shows") return GROUP_META[v as Group].label;
    if (id === "can") return CAPS.find((c) => c.id === v)?.label ?? v;
    return v;
  };
  const chips: { key: string; label: string; remove: () => void }[] = [];
  if (filters.installed) chips.push({ key: "installed", label: "Installed here", remove: () => setFilters({ ...filters, installed: false }) });
  for (const id of ["trust", "shows", "can", "coverage"] as FacetId[]) {
    for (const v of filters[id]) {
      chips.push({
        key: id + v,
        label: labelOf(id, v),
        remove: () => {
          const next = new Set(filters[id]);
          next.delete(v);
          setFilters({ ...filters, [id]: next });
        },
      });
    }
  }
  if (chips.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Active filters">
      {chips.map((c) => (
        <li key={c.key}>
          <button
            type="button"
            onClick={c.remove}
            className="inline-flex h-7 items-center gap-1 rounded-full border border-cs-line-strong bg-cs-surface pl-2.5 pr-1.5 text-xs font-medium text-cs-ink hover:bg-cs-surface-2"
          >
            {c.label}
            <X aria-hidden className="size-3.5 text-cs-ink-3" />
            <span className="sr-only">: remove filter</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
