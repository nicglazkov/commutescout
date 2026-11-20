"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Check, ChevronRight, Clock, LayoutGrid, List, MapPin, Plus, Search, X } from "lucide-react";
import {
  GROUP_STYLE,
  KindChip,
  MiniUS,
  NotReviewedNote,
  ORDER,
  PLUGINS,
  PluginGlyph,
  TrustBadge,
  agoLabel,
  approved,
  coverageLabel,
  groupsOf,
  operatorOf,
  refreshLabel,
  type Group,
  type Plugin,
} from "./kit";

// Every option on the marketplace board, each a working mockup over the real
// catalog snapshot. Install switches here are local state only: they never
// touch the live page's cs.plugins.* keys.

function useInstalled() {
  // On the live page every public plugin starts installed (switched off per browser).
  const [off, setOff] = useState<Set<string>>(new Set());
  return {
    is: (id: string) => !off.has(id),
    toggle: (id: string) =>
      setOff((s) => {
        const n = new Set(s);
        if (n.has(id)) n.delete(id);
        else n.add(id);
        return n;
      }),
  };
}

function InstallButton({ p, inst, size = "md" }: { p: Plugin; inst: ReturnType<typeof useInstalled>; size?: "sm" | "md" }) {
  const on = inst.is(p.id);
  const h = size === "sm" ? "h-8 px-3 text-[0.8125rem]" : "h-9 px-4 text-sm";
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={`${on ? "Installed" : "Install"}: ${p.name}`}
      onClick={() => inst.toggle(p.id)}
      className={`inline-flex shrink-0 items-center gap-1 rounded-[var(--cs-radius-md)] font-medium transition-colors duration-150 ${h} ${
        on
          ? "border border-cs-line-strong bg-cs-surface text-cs-ink hover:bg-cs-surface-2"
          : "bg-cs-accent text-cs-accent-ink hover:bg-cs-accent-hover"
      }`}
    >
      {on && <Check aria-hidden className="size-4" />}
      {on ? "Installed" : "Install"}
    </button>
  );
}

function MapLink({ p }: { p: Plugin }) {
  return (
    <a href={`/map?plugin=${encodeURIComponent(p.id)}`} className="inline-flex items-center gap-1 text-sm font-medium text-cs-accent hover:underline">
      <MapPin aria-hidden className="size-4" />
      See it on the map
    </a>
  );
}

function Frame({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-[calc(var(--cs-radius-lg)+4px)] border border-cs-line bg-cs-bg p-4 sm:p-6 ${className}`}>{children}</div>;
}

function Chips({ p, max }: { p: Plugin; max?: number }) {
  const g = groupsOf(p);
  const shown = max ? g.slice(0, max) : g;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="What it shows">
      {shown.map((x) => (
        <li key={x.group}>
          <KindChip group={x.group} />
        </li>
      ))}
      {max && g.length > max && <li className="px-1 text-xs leading-6 text-cs-ink-3">+{g.length - max} more</li>}
    </ul>
  );
}

function Toggle({ on, onClick, children, count }: { on: boolean; onClick: () => void; children: ReactNode; count?: number }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[0.8125rem] font-medium transition-colors duration-150 ${
        on ? "border-cs-accent bg-cs-accent-soft text-cs-accent" : "border-cs-line-strong bg-cs-surface text-cs-ink-2 hover:bg-cs-surface-2 hover:text-cs-ink"
      }`}
    >
      {children}
      {count !== undefined && <span className="cs-data text-xs opacity-80">{count}</span>}
    </button>
  );
}

/** A trimmed version of today's card, reused where the option is about the browsing, not the card. */
function BasicCard({ p, inst, chips = true }: { p: Plugin; inst: ReturnType<typeof useInstalled>; chips?: boolean }) {
  return (
    <article className="flex min-w-0 flex-col rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-5 shadow-[var(--cs-shadow-sm)]">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <PluginGlyph p={p} />
        <div className="min-w-[11rem] flex-1">
          <h4 className="cs-h3">{p.name}</h4>
          <p className="truncate text-sm text-cs-ink-3">{operatorOf(p)}</p>
        </div>
        <InstallButton p={p} inst={inst} />
      </div>
      <p className="mt-3 text-[0.9375rem] leading-relaxed text-cs-ink-2">{p.description}</p>
      {chips && (
        <div className="mt-3">
          <Chips p={p} />
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-cs-line pt-3">
        <TrustBadge p={p} />
        <span className="cs-data text-sm text-cs-ink-2">{p.count.toLocaleString("en-US")} alerts now</span>
      </div>
    </article>
  );
}

/* ---------------- M1 filter bar ---------------- */

const KIND_FILTERS: Group[] = ORDER.filter((g) => PLUGINS.some((p) => groupsOf(p).some((x) => x.group === g)));

export function M1FilterBar() {
  const inst = useInstalled();
  const [trust, setTrust] = useState<"all" | "approved" | "unreviewed">("all");
  const [kinds, setKinds] = useState<Set<Group>>(new Set());
  const [confirm, setConfirm] = useState(false);
  const list = PLUGINS.filter(
    (p) =>
      (trust === "all" || p.tier === trust) &&
      (kinds.size === 0 || groupsOf(p).some((x) => kinds.has(x.group))) &&
      (!confirm || p.capabilities.confirm),
  );
  const n = (f: (p: Plugin) => boolean) => PLUGINS.filter(f).length;
  const dirty = trust !== "all" || kinds.size > 0 || confirm;
  return (
    <Frame>
      <div className="rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <fieldset className="flex flex-wrap items-center gap-2">
            <legend className="cs-eyebrow mr-1 float-left leading-8">Trust</legend>
            <Toggle on={trust === "all"} onClick={() => setTrust("all")} count={PLUGINS.length}>All</Toggle>
            <Toggle on={trust === "approved"} onClick={() => setTrust("approved")} count={n(approved)}>Approved</Toggle>
            <Toggle on={trust === "unreviewed"} onClick={() => setTrust("unreviewed")} count={n((p) => !approved(p))}>Not reviewed</Toggle>
          </fieldset>
          <span aria-hidden className="hidden h-6 w-px bg-cs-line lg:block" />
          <fieldset className="flex flex-wrap items-center gap-2">
            <legend className="cs-eyebrow mr-1 float-left leading-8">Can</legend>
            <Toggle on={confirm} onClick={() => setConfirm((v) => !v)} count={n((p) => !!p.capabilities.confirm)}>Confirm reports</Toggle>
          </fieldset>
        </div>
        <fieldset className="mt-3 flex flex-wrap items-center gap-2 border-t border-cs-line pt-3">
          <legend className="cs-eyebrow mr-1 float-left leading-8">Shows</legend>
          {KIND_FILTERS.map((g) => {
            const S = GROUP_STYLE[g];
            return (
              <Toggle
                key={g}
                on={kinds.has(g)}
                count={n((p) => groupsOf(p).some((x) => x.group === g))}
                onClick={() =>
                  setKinds((s) => {
                    const nx = new Set(s);
                    if (nx.has(g)) nx.delete(g);
                    else nx.add(g);
                    return nx;
                  })
                }
              >
                <S.Icon aria-hidden className={`size-3.5 ${S.text}`} />
                {S.label}
              </Toggle>
            );
          })}
        </fieldset>
      </div>
      <div className="mt-4 flex items-center justify-between text-sm text-cs-ink-3" aria-live="polite">
        <span>
          {list.length} of {PLUGINS.length} plugins
        </span>
        {dirty && (
          <button
            type="button"
            className="inline-flex items-center gap-1 text-cs-accent hover:underline"
            onClick={() => {
              setTrust("all");
              setKinds(new Set());
              setConfirm(false);
            }}
          >
            <X aria-hidden className="size-3.5" />
            Clear filters
          </button>
        )}
      </div>
      {list.length === 0 ? (
        <p className="mt-3 rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-6 text-sm text-cs-ink-2">
          No plugin matches these filters.
        </p>
      ) : (
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          {list.map((p) => (
            <BasicCard key={p.id} p={p} inst={inst} />
          ))}
        </div>
      )}
    </Frame>
  );
}

/* ---------------- M2 colour by alert kind ---------------- */

export function M2KindColour() {
  const inst = useInstalled();
  return (
    <Frame>
      <div className="grid gap-4 md:grid-cols-2">
        {PLUGINS.map((p) => {
          const g = groupsOf(p);
          return (
            <article key={p.id} className="flex min-w-0 flex-col overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface shadow-[var(--cs-shadow-sm)]">
              {/* one cell per kind group, in the map's own colours */}
              <div className="flex h-1.5" aria-hidden>
                {g.map((x) => (
                  <span key={x.group} className={`flex-1 ${GROUP_STYLE[x.group].dot}`} style={{ flexGrow: x.kinds.length }} />
                ))}
              </div>
              <div className="flex flex-1 flex-col p-5">
                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
                  <div className="min-w-0">
                    <h4 className="cs-h3">{p.name}</h4>
                    <p className="text-sm text-cs-ink-3">{operatorOf(p)}</p>
                  </div>
                  <InstallButton p={p} inst={inst} />
                </div>
                <ul className="mt-4 grid grid-cols-2 gap-1.5 sm:grid-cols-3" aria-label="What it shows">
                  {g.map((x) => {
                    const S = GROUP_STYLE[x.group];
                    return (
                      <li key={x.group} className={`flex items-center gap-2 rounded-[var(--cs-radius-md)] px-2.5 py-2 ${S.soft}`}>
                        <S.Icon aria-hidden className={`size-4 ${S.text}`} />
                        <span className={`text-sm font-medium ${S.text}`}>{S.label}</span>
                        <span className="cs-data ml-auto text-xs text-cs-ink-3" title="Kinds in this group">
                          {x.kinds.length}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-4">
                  <TrustBadge p={p} />
                  <MapLink p={p} />
                </div>
              </div>
            </article>
          );
        })}
      </div>
      <p className="mt-4 text-xs text-cs-ink-3">
        Colours are the live map&rsquo;s: crashes and hazards orange, closures red, weather teal, chain controls indigo. Police, jams and cameras have no road-event colour, so they stay neutral and carry an icon.
      </p>
    </Frame>
  );
}

/* ---------------- M3 icon tiles ---------------- */

function BigIcon({ p }: { p: Plugin }) {
  const g = groupsOf(p);
  const main = g.find((x) => GROUP_STYLE[x.group].text !== "text-cs-ink-2") || g[0];
  const S = GROUP_STYLE[main.group];
  return (
    <span aria-hidden className={`relative flex size-20 items-center justify-center rounded-[22%] border border-cs-line ${S.soft}`}>
      <S.Icon className={`size-9 ${S.text}`} strokeWidth={1.6} />
      {g.length > 1 && (
        <span className="cs-data absolute -right-1.5 -bottom-1.5 rounded-full border border-cs-line bg-cs-surface px-1.5 text-[0.6875rem] text-cs-ink-2">
          +{g.length - 1}
        </span>
      )}
    </span>
  );
}

export function M3IconTiles() {
  const inst = useInstalled();
  return (
    <Frame>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {PLUGINS.map((p) => (
          <li key={p.id} className="flex flex-col items-center rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-5 text-center">
            <BigIcon p={p} />
            <h4 className="mt-4 text-[0.9375rem] font-semibold leading-snug text-cs-ink">{p.name}</h4>
            <p className="mt-1 line-clamp-1 text-xs text-cs-ink-3">{operatorOf(p)}</p>
            <p className="mt-2">
              <TrustBadge p={p} compact />
            </p>
            <div className="mt-4">
              <InstallButton p={p} inst={inst} size="sm" />
            </div>
          </li>
        ))}
        <li className="flex flex-col items-center justify-center rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-5 text-center">
          <span aria-hidden className="flex size-20 items-center justify-center rounded-[22%] border border-dashed border-cs-line-strong text-cs-ink-3">
            <Plus className="size-8" />
          </span>
          <a href="/plugins" className="cs-link mt-4 text-[0.9375rem] font-medium">
            Write a plugin
          </a>
          <p className="mt-1 text-xs text-cs-ink-3">Free to list</p>
        </li>
      </ul>
    </Frame>
  );
}

/* ---------------- M4 featured + list ---------------- */

export function M4Featured() {
  const inst = useInstalled();
  const [feat, ...rest] = [...PLUGINS].sort((a, b) => Number(approved(b)) - Number(approved(a)));
  return (
    <Frame>
      <section aria-label="Featured plugin" className="grid grid-cols-1 overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface lg:grid-cols-12">
        <div className="p-6 sm:p-8 lg:col-span-7">
          <p className="cs-eyebrow">Featured</p>
          <h4 className="mt-3 text-[1.75rem] font-semibold leading-tight tracking-[-0.02em] text-cs-ink">{feat.name}</h4>
          <p className="mt-1 text-sm text-cs-ink-3">{operatorOf(feat)}</p>
          <p className="mt-4 max-w-[38rem] text-[0.9375rem] leading-relaxed text-cs-ink-2">{feat.description}</p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <InstallButton p={feat} inst={inst} />
            <MapLink p={feat} />
          </div>
        </div>
        <div className="flex flex-col justify-between border-t border-cs-line bg-cs-surface-2 p-6 lg:col-span-5 lg:border-t-0 lg:border-l">
          <MiniUS p={feat} className="h-auto w-full max-w-[22rem] self-center" />
          <dl className="mt-4 grid grid-cols-3 gap-2 text-sm">
            <div>
              <dt className="cs-eyebrow">Alerts now</dt>
              <dd className="cs-data mt-1 text-lg text-cs-ink">{feat.count.toLocaleString("en-US")}</dd>
            </div>
            <div>
              <dt className="cs-eyebrow">Refresh</dt>
              <dd className="mt-1 text-cs-ink">{refreshLabel(feat.refresh_s)}</dd>
            </div>
            <div>
              <dt className="cs-eyebrow">Trust</dt>
              <dd className="mt-1">
                <TrustBadge p={feat} compact />
              </dd>
            </div>
          </dl>
        </div>
      </section>
      <h5 className="cs-eyebrow mt-8">All plugins</h5>
      <ul className="mt-3 divide-y divide-cs-line rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface">
        {[feat, ...rest].map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
            <PluginGlyph p={p} size={40} />
            <div className="min-w-[11rem] flex-1">
              <p className="font-medium text-cs-ink">{p.name}</p>
              <p className="truncate text-sm text-cs-ink-3">{p.description}</p>
            </div>
            <TrustBadge p={p} compact />
            <InstallButton p={p} inst={inst} size="sm" />
          </li>
        ))}
      </ul>
    </Frame>
  );
}

/* ---------------- M5 cards / list toggle ---------------- */

export function M5ViewToggle() {
  const inst = useInstalled();
  const [view, setView] = useState<"list" | "cards">("list");
  return (
    <Frame>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-cs-ink-3">{PLUGINS.length} plugins</p>
        <div role="group" aria-label="View" className="inline-flex rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface p-0.5">
          {(
            [
              ["list", List, "List"],
              ["cards", LayoutGrid, "Cards"],
            ] as const
          ).map(([v, Icon, label]) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className={`inline-flex h-8 items-center gap-1.5 rounded-[calc(var(--cs-radius-md)-2px)] px-3 text-[0.8125rem] font-medium ${
                view === v ? "bg-cs-surface-2 text-cs-ink" : "text-cs-ink-3 hover:text-cs-ink"
              }`}
            >
              <Icon aria-hidden className="size-4" />
              {label}
            </button>
          ))}
        </div>
      </div>
      {view === "cards" ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {PLUGINS.map((p) => (
            <BasicCard key={p.id} p={p} inst={inst} />
          ))}
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <thead className="border-b border-cs-line bg-cs-surface-2 text-cs-ink-3">
              <tr>
                {["Plugin", "Trust", "Shows", "Coverage", "Alerts now", "Refresh", ""].map((h) => (
                  <th key={h} scope="col" className="cs-data px-4 py-2.5 text-[0.6875rem] font-medium uppercase tracking-[0.06em]">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-cs-line">
              {PLUGINS.map((p) => (
                <tr key={p.id}>
                  <th scope="row" className="px-4 py-3 font-medium text-cs-ink">
                    <span className="flex items-center gap-3">
                      <PluginGlyph p={p} size={32} />
                      <span>
                        {p.name}
                        <span className="block text-xs font-normal text-cs-ink-3">v{p.version}</span>
                      </span>
                    </span>
                  </th>
                  <td className="px-4 py-3">
                    <TrustBadge p={p} compact />
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex flex-wrap gap-1">
                      {groupsOf(p).map((x) => {
                        const S = GROUP_STYLE[x.group];
                        return (
                          <span key={x.group} title={S.label} className={`inline-flex size-6 items-center justify-center rounded-[var(--cs-radius-sm)] ${S.soft}`}>
                            <S.Icon aria-label={S.label} className={`size-3.5 ${S.text}`} />
                          </span>
                        );
                      })}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-cs-ink-2">{coverageLabel(p.coverage)}</td>
                  <td className="cs-data px-4 py-3 text-cs-ink">{p.count.toLocaleString("en-US")}</td>
                  <td className="px-4 py-3 text-cs-ink-2">{refreshLabel(p.refresh_s)}</td>
                  <td className="px-4 py-3 text-right">
                    <InstallButton p={p} inst={inst} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Frame>
  );
}

/* ---------------- M6 master-detail ---------------- */

const CAPS: [string, string][] = [
  ["alerts", "Sends alerts to the map"],
  ["report", "Takes reports from drivers"],
  ["confirm", "Lets drivers confirm or clear a report"],
  ["notify", "Can push notifications"],
  ["snapshot", "Serves a full snapshot"],
];

function Detail({ p, inst }: { p: Plugin; inst: ReturnType<typeof useInstalled> }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <PluginGlyph p={p} size={56} />
        <div className="min-w-[11rem] flex-1">
          <h4 className="text-xl font-semibold tracking-[-0.015em] text-cs-ink">{p.name}</h4>
          <a href={p.attribution.url} className="text-sm text-cs-ink-3 hover:text-cs-accent hover:underline">
            {operatorOf(p)}
          </a>
        </div>
        <InstallButton p={p} inst={inst} />
      </div>
      <p className="mt-4 text-[0.9375rem] leading-relaxed text-cs-ink-2">{p.description}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <TrustBadge p={p} />
        <MapLink p={p} />
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 [&>*]:min-w-0">
        <div>
          <h5 className="cs-eyebrow">What it shows</h5>
          <ul className="mt-2 space-y-2">
            {groupsOf(p).map((x) => (
              <li key={x.group} className="flex items-start gap-2">
                <KindChip group={x.group} />
                <span className="cs-data min-w-0 break-all pt-0.5 text-[0.6875rem] leading-relaxed text-cs-ink-3">{x.kinds.join(" ")}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h5 className="cs-eyebrow">What it can do</h5>
          <ul className="mt-2 space-y-1.5 text-sm">
            {CAPS.map(([k, label]) => {
              const yes = !!p.capabilities[k];
              return (
                <li key={k} className={`flex items-center gap-2 ${yes ? "text-cs-ink" : "text-cs-ink-3"}`}>
                  {yes ? <Check aria-hidden className="size-4 text-cs-ok" /> : <X aria-hidden className="size-4" />}
                  <span>
                    <span className="sr-only">{yes ? "Yes: " : "No: "}</span>
                    {label}
                  </span>
                </li>
              );
            })}
          </ul>
          <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-cs-line pt-4 text-sm">
            <dt className="text-cs-ink-3">Alerts now</dt>
            <dd className="cs-data text-cs-ink">{p.count.toLocaleString("en-US")}</dd>
            <dt className="text-cs-ink-3">Refresh</dt>
            <dd className="text-cs-ink">{refreshLabel(p.refresh_s)}</dd>
            <dt className="text-cs-ink-3">Last answered</dt>
            <dd className="text-cs-ink">{agoLabel(p.last_ok)}</dd>
            <dt className="text-cs-ink-3">Coverage</dt>
            <dd className="text-cs-ink">{coverageLabel(p.coverage)}</dd>
            <dt className="text-cs-ink-3">Version</dt>
            <dd className="cs-data text-cs-ink">
              {p.version} · {p.protocol}
            </dd>
          </dl>
        </div>
      </div>
      {!approved(p) && (
        <div className="mt-5 rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface-2 p-3">
          <NotReviewedNote />
        </div>
      )}
    </div>
  );
}

export function M6MasterDetail() {
  const inst = useInstalled();
  const [sel, setSel] = useState(PLUGINS[0].id);
  const p = PLUGINS.find((x) => x.id === sel)!;
  return (
    <Frame>
      <div className="grid grid-cols-1 overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface lg:grid-cols-12">
        <ul className="border-b border-cs-line lg:col-span-4 lg:border-r lg:border-b-0" aria-label="Plugins">
          {PLUGINS.map((x) => (
            <li key={x.id}>
              <button
                type="button"
                aria-current={x.id === sel}
                onClick={() => setSel(x.id)}
                className={`flex w-full items-center gap-3 border-l-2 px-4 py-4 text-left transition-colors ${
                  x.id === sel ? "border-cs-accent bg-cs-accent-soft" : "border-transparent hover:bg-cs-surface-2"
                }`}
              >
                <PluginGlyph p={x} size={36} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-cs-ink">{x.name}</span>
                  <span className="block text-xs text-cs-ink-3">
                    {approved(x) ? "Approved" : "Not reviewed"} · {x.count.toLocaleString("en-US")} alerts
                  </span>
                </span>
                <ChevronRight aria-hidden className="size-4 text-cs-ink-3" />
              </button>
            </li>
          ))}
        </ul>
        <div className="min-w-0 p-6 lg:col-span-8" aria-live="polite">
          <Detail p={p} inst={inst} />
        </div>
      </div>
    </Frame>
  );
}

/* ---------------- M7 sidebar categories ---------------- */

type Cat = { key: string; label: string; test: (p: Plugin, inst: ReturnType<typeof useInstalled>) => boolean };

export function M7Sidebar() {
  const inst = useInstalled();
  const [cat, setCat] = useState("all");
  const [q, setQ] = useState("");
  const browse: Cat[] = [
    { key: "all", label: "All plugins", test: () => true },
    { key: "approved", label: "Approved", test: (p) => approved(p) },
    { key: "community", label: "Community", test: (p) => !approved(p) },
    { key: "installed", label: "Installed here", test: (p, i) => i.is(p.id) },
  ];
  const byKind: Cat[] = KIND_FILTERS.map((g) => ({
    key: g,
    label: GROUP_STYLE[g].label,
    test: (p) => groupsOf(p).some((x) => x.group === g),
  }));
  const all = [...browse, ...byKind];
  const cur = all.find((c) => c.key === cat)!;
  const list = PLUGINS.filter((p) => cur.test(p, inst) && (q === "" || (p.name + " " + p.description).toLowerCase().includes(q.toLowerCase())));
  const NavBtn = ({ c, icon }: { c: Cat; icon?: ReactNode }) => (
    <li>
      <button
        type="button"
        aria-current={cat === c.key}
        onClick={() => setCat(c.key)}
        className={`flex h-9 w-full items-center gap-2 rounded-[var(--cs-radius-sm)] px-2.5 text-left text-sm ${
          cat === c.key ? "bg-cs-surface-2 font-medium text-cs-ink" : "text-cs-ink-2 hover:bg-cs-surface-2 hover:text-cs-ink"
        }`}
      >
        {icon}
        <span className="flex-1">{c.label}</span>
        <span className="cs-data text-xs text-cs-ink-3">{PLUGINS.filter((p) => c.test(p, inst)).length}</span>
      </button>
    </li>
  );
  return (
    <Frame>
      <div className="grid grid-cols-1 overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface md:grid-cols-[15rem_1fr]">
        <nav aria-label="Plugin categories" className="border-b border-cs-line p-3 md:border-r md:border-b-0">
          <p className="cs-eyebrow px-2.5 pt-1 pb-2">Browse</p>
          <ul className="space-y-0.5">
            {browse.map((c) => (
              <NavBtn key={c.key} c={c} />
            ))}
          </ul>
          <p className="cs-eyebrow px-2.5 pt-5 pb-2">What it shows</p>
          <ul className="space-y-0.5">
            {byKind.map((c) => {
              const S = GROUP_STYLE[c.key as Group];
              return <NavBtn key={c.key} c={c} icon={<S.Icon aria-hidden className={`size-4 ${S.text}`} />} />;
            })}
          </ul>
        </nav>
        <div className="min-w-0 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h4 className="text-lg font-semibold text-cs-ink">{cur.label}</h4>
            <label className="relative block w-full sm:w-64">
              <span className="sr-only">Search plugins</span>
              <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-cs-ink-3" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search plugins"
                className="h-9 w-full rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface pr-3 pl-9 text-sm text-cs-ink placeholder:text-cs-ink-3"
              />
            </label>
          </div>
          {list.length === 0 ? (
            <p className="mt-4 rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-6 text-sm text-cs-ink-2">Nothing here yet.</p>
          ) : (
            <ul className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
              {list.map((p) => (
                <li key={p.id} className="flex min-w-0 flex-col rounded-[var(--cs-radius-lg)] border border-cs-line p-4">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <PluginGlyph p={p} size={40} />
                    <div className="min-w-[11rem] flex-1">
                      <p className="truncate font-medium text-cs-ink">{p.name}</p>
                      <p className="text-xs text-cs-ink-3">{approved(p) ? "Approved" : "Not reviewed"}</p>
                    </div>
                    <InstallButton p={p} inst={inst} size="sm" />
                  </div>
                  <p className="mt-3 line-clamp-2 text-sm text-cs-ink-2">{p.description}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Frame>
  );
}

/* ---------------- M8 plugin x kind matrix ---------------- */

export function M8Matrix() {
  const cols = ORDER.filter((g) => g !== "other");
  return (
    <Frame>
      <div className="overflow-x-auto rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface">
        <table className="w-full min-w-[52rem] text-sm">
          <caption className="sr-only">Which plugin shows which kind of alert</caption>
          <thead>
            <tr className="border-b border-cs-line">
              <th scope="col" className="px-4 py-3 text-left text-cs-ink-3">
                <span className="cs-eyebrow">Plugin</span>
              </th>
              {cols.map((g) => {
                const S = GROUP_STYLE[g];
                return (
                  <th key={g} scope="col" className="px-2 py-3 text-center font-medium text-cs-ink-2">
                    <span className="flex flex-col items-center gap-1">
                      <S.Icon aria-hidden className={`size-4 ${S.text}`} />
                      <span className="text-xs">{S.label}</span>
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-cs-line">
            {PLUGINS.map((p) => {
              const gs = groupsOf(p);
              return (
                <tr key={p.id}>
                  <th scope="row" className="px-4 py-4 text-left">
                    <span className="block font-medium text-cs-ink">{p.name}</span>
                    <span className="mt-1 inline-block">
                      <TrustBadge p={p} compact />
                    </span>
                  </th>
                  {cols.map((g) => {
                    const hit = gs.find((x) => x.group === g);
                    const S = GROUP_STYLE[g];
                    return (
                      <td key={g} className="px-2 py-4 text-center">
                        {hit ? (
                          <span
                            title={hit.kinds.join(", ")}
                            className={`cs-data inline-flex size-8 items-center justify-center rounded-full ${S.soft} ${S.text} text-xs font-semibold`}
                          >
                            <span className="sr-only">{S.label}: </span>
                            {hit.kinds.length}
                          </span>
                        ) : (
                          <span aria-label="No" className="inline-block size-2 rounded-full bg-cs-line-strong" />
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-cs-ink-3">Each number is how many alert kinds the plugin sends in that group (hover for the kind codes).</p>
    </Frame>
  );
}

/* ---------------- M9 trust shelves ---------------- */

function ShelfCard({ p, inst }: { p: Plugin; inst: ReturnType<typeof useInstalled> }) {
  return (
    <article className="flex min-w-0 flex-col rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-5 shadow-[var(--cs-shadow-sm)]">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <PluginGlyph p={p} />
        <div className="min-w-[11rem] flex-1">
          <h4 className="cs-h3">{p.name}</h4>
          <p className="truncate text-sm text-cs-ink-3">{operatorOf(p)}</p>
        </div>
        <InstallButton p={p} inst={inst} />
      </div>
      <p className="mt-3 text-[0.9375rem] leading-relaxed text-cs-ink-2">{p.description}</p>
      <div className="mt-3">
        <Chips p={p} />
      </div>
      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 border-t border-cs-line pt-3 text-sm">
        <div className="flex gap-1.5">
          <dt className="text-cs-ink-3">Alerts now</dt>
          <dd className="cs-data text-cs-ink">{p.count.toLocaleString("en-US")}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-cs-ink-3">Refresh</dt>
          <dd className="text-cs-ink">{refreshLabel(p.refresh_s)}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-cs-ink-3">Coverage</dt>
          <dd className="text-cs-ink">{coverageLabel(p.coverage)}</dd>
        </div>
      </dl>
      <div className="mt-3">
        <MapLink p={p} />
      </div>
    </article>
  );
}

export function M9Shelves() {
  const inst = useInstalled();
  const rev = PLUGINS.filter(approved);
  const com = PLUGINS.filter((p) => !approved(p));
  return (
    <Frame>
      <section aria-labelledby="shelf-rev">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-cs-line pb-3">
          <h4 id="shelf-rev" className="flex items-center gap-2 text-lg font-semibold text-cs-ink">
            Reviewed by CommuteScout
            <span className="cs-data text-sm font-normal text-cs-ink-3">{rev.length}</span>
          </h4>
          <p className="text-sm text-cs-ink-3">The operator is known and the feed passed review.</p>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {rev.map((p) => (
            <ShelfCard key={p.id} p={p} inst={inst} />
          ))}
          <div className="flex flex-col justify-center rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-5">
            <p className="font-medium text-cs-ink">Run a feed people could use?</p>
            <p className="mt-1 text-sm leading-relaxed text-cs-ink-2">
              Any plugin that passes the conformance check can be listed. Approval adds a review: the operator is known and the feed passed it.
            </p>
            <a href="/plugins" className="cs-link mt-3 text-sm font-medium">
              Write a plugin
            </a>
          </div>
        </div>
      </section>
      <section aria-labelledby="shelf-com" className="mt-10">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-cs-line pb-3">
          <h4 id="shelf-com" className="flex items-center gap-2 text-lg font-semibold text-cs-ink">
            Community, not reviewed
            <span className="cs-data text-sm font-normal text-cs-ink-3">{com.length}</span>
          </h4>
          <p className="text-sm text-cs-ink-3">Passed the conformance check. Run by their operators.</p>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {com.map((p) => (
            <ShelfCard key={p.id} p={p} inst={inst} />
          ))}
          <div className="rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-5">
            <p className="font-medium text-cs-ink">Before you install one</p>
            <div className="mt-2">
              <NotReviewedNote />
            </div>
            <p className="mt-3 text-xs leading-relaxed text-cs-ink-3">Turn its alerts, or speaking them, on or off in Settings &gt; Alerts.</p>
          </div>
        </div>
      </section>
    </Frame>
  );
}

/* ---------------- M10 map-preview cards ---------------- */

export function M10MapCards() {
  const inst = useInstalled();
  return (
    <Frame>
      <div className="grid gap-4 md:grid-cols-2">
        {PLUGINS.map((p) => (
          <article key={p.id} className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface shadow-[var(--cs-shadow-sm)]">
            <div className="relative border-b border-cs-line bg-cs-surface-2 px-8 pt-6 pb-4">
              <MiniUS p={p} className="mx-auto h-auto w-full max-w-[24rem]" />
              <span className="cs-data absolute top-3 left-3 rounded-[var(--cs-radius-sm)] bg-cs-surface px-2 py-1 text-xs text-cs-ink-2 shadow-[var(--cs-shadow-sm)]">
                {coverageLabel(p.coverage)}
              </span>
              <span className="absolute top-3 right-3 rounded-[var(--cs-radius-sm)] bg-cs-surface px-2 py-1 text-right shadow-[var(--cs-shadow-sm)]">
                <span className="cs-data block text-lg leading-none text-cs-ink">{p.count.toLocaleString("en-US")}</span>
                <span className="text-[0.6875rem] text-cs-ink-3">alerts now</span>
              </span>
            </div>
            <div className="p-5">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-3">
                <div className="min-w-[11rem] flex-1">
                  <h4 className="cs-h3">{p.name}</h4>
                  <p className="flex items-center gap-1 text-sm text-cs-ink-3">
                    <Clock aria-hidden className="size-3.5" />
                    {refreshLabel(p.refresh_s)}, last answered {agoLabel(p.last_ok)}
                  </p>
                </div>
                <InstallButton p={p} inst={inst} />
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <Chips p={p} max={4} />
                <TrustBadge p={p} compact />
              </div>
            </div>
          </article>
        ))}
      </div>
    </Frame>
  );
}

/* ---------------- M11 live status rows (reads the endpoint) ---------------- */

export function M11StatusRows() {
  const inst = useInstalled();
  const [live, setLive] = useState<Plugin[] | null>(null);
  useEffect(() => {
    let dead = false;
    fetch("/api/flare/sources", { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => {
        if (!dead && Array.isArray(d.sources)) setLive(d.sources);
      })
      .catch(() => {});
    return () => {
      dead = true;
    };
  }, []);
  const rows = useMemo(() => live ?? PLUGINS, [live]);
  return (
    <Frame>
      <div className="flex items-center justify-between text-sm">
        <p className="text-cs-ink-3">{live ? "Live from /api/flare/sources" : "Snapshot (live data loads in the browser)"}</p>
        <p className="cs-data text-cs-ink-3">{rows.length} listed</p>
      </div>
      <ul className="mt-3 divide-y divide-cs-line rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface">
        {rows.map((p) => {
          const state = p.ok === false ? "Offline" : p.stale ? "Stale" : "Fresh";
          const dot = p.ok === false ? "bg-cs-closure" : p.stale ? "bg-cs-stale" : "bg-cs-ok";
          return (
            <li key={p.id} className="grid items-center gap-x-6 gap-y-2 px-5 py-4 md:grid-cols-[1fr_7rem_8rem_8rem_auto]">
              <div className="flex min-w-0 items-center gap-3">
                <PluginGlyph p={p} size={36} />
                <div className="min-w-0">
                  <p className="truncate font-medium text-cs-ink">{p.name}</p>
                  <p className="text-xs text-cs-ink-3">
                    {approved(p) ? "Approved" : "Not reviewed"} · v{p.version}
                  </p>
                </div>
              </div>
              <p className="flex items-center gap-2 text-sm text-cs-ink">
                <span aria-hidden className={`size-2 rounded-full ${dot}`} />
                {state}
              </p>
              <p className="cs-data text-sm text-cs-ink">
                {(p.count ?? 0).toLocaleString("en-US")} <span className="font-sans text-cs-ink-3">alerts</span>
              </p>
              <p className="text-sm text-cs-ink-2">{refreshLabel(p.refresh_s)}</p>
              <InstallButton p={p} inst={inst} size="sm" />
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs text-cs-ink-3">Stale means the last good answer is more than 15 minutes old, or the last poll failed. A plugin that refreshes hourly reads stale for most of the hour, which this view makes visible.</p>
    </Frame>
  );
}
