"use client";

import type { ReactNode } from "react";
import { CAPS, GROUP_META, GROUP_ORDER, coverageLabel, passes, valuesOf, type FacetId, type Filters, type Source, type Tier } from "./data";
import { GROUP_ICON, TIER_META } from "./parts";

type Opt = { value: string; label: string; icon?: ReactNode };

const TIERS: Tier[] = ["approved", "unreviewed", "private"];

/** Every facet's options, in display order. Built from the catalog so a new kind or region shows up on its own. */
export function facetOptions(sources: Source[]): { id: FacetId; legend: string; opts: Opt[] }[] {
  const coverages = Array.from(new Set(sources.map((s) => coverageLabel(s.coverage)))).sort((a, b) =>
    a === "Whole country" ? -1 : b === "Whole country" ? 1 : a.localeCompare(b),
  );
  return [
    {
      id: "trust",
      legend: "Trust",
      opts: TIERS.map((t) => {
        const { Icon, short } = TIER_META[t];
        return {
          value: t,
          label: short,
          icon: (
            <span data-tier={t} className="mk-t inline-flex">
              <Icon aria-hidden className="size-4" />
            </span>
          ),
        };
      }),
    },
    {
      id: "shows",
      legend: "What it shows",
      opts: GROUP_ORDER.map((g) => {
        const Icon = GROUP_ICON[g];
        return {
          value: g,
          label: GROUP_META[g].label,
          icon: (
            <span data-tone={GROUP_META[g].tone} className="mk-k-fg inline-flex">
              <Icon aria-hidden className="size-4" />
            </span>
          ),
        };
      }),
    },
    { id: "can", legend: "What it can do", opts: CAPS.map((c) => ({ value: c.id, label: c.label })) },
    { id: "coverage", legend: "Coverage", opts: coverages.map((c) => ({ value: c, label: c })) },
  ];
}

export function FacetPanel({
  sources,
  filters,
  setFilters,
  isInstalled,
  idPrefix,
}: {
  sources: Source[];
  filters: Filters;
  setFilters: (f: Filters) => void;
  isInstalled: (s: Source) => boolean;
  idPrefix: string;
}) {
  const total = sources.length;
  const installedN = sources.filter(isInstalled).length;

  function toggle(id: FacetId, value: string) {
    const next = new Set(filters[id]);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    setFilters({ ...filters, [id]: next });
  }

  const groups = facetOptions(sources)
    .map((g) => {
      const opts = g.opts
        .map((o) => {
          const global = sources.filter((s) => valuesOf(s)[g.id].includes(o.value)).length;
          const live = sources.filter(
            (s) => valuesOf(s)[g.id].includes(o.value) && passes(s, filters, isInstalled(s), g.id),
          ).length;
          return { ...o, global, live, checked: filters[g.id].has(o.value) };
        })
        // An option no plugin carries is never shown.
        .filter((o) => o.global > 0);
      // A facet whose every option matches the whole catalog narrows nothing, so it waits until it would.
      const useful = opts.some((o) => o.global < total) || opts.some((o) => o.checked);
      return { ...g, opts, useful };
    })
    .filter((g) => g.opts.length > 0 && g.useful);

  return (
    <div className="flex flex-col gap-6">
      <fieldset>
        <legend className="cs-data mb-2 px-2 text-[11px] uppercase tracking-[0.08em] text-cs-ink-3">Browse</legend>
        <Row
          type="radio"
          name={`${idPrefix}-browse`}
          checked={!filters.installed}
          onChange={() => setFilters({ ...filters, installed: false })}
          label="All plugins"
          count={total}
        />
        <Row
          type="radio"
          name={`${idPrefix}-browse`}
          checked={filters.installed}
          disabled={installedN === 0 && !filters.installed}
          onChange={() => setFilters({ ...filters, installed: true })}
          label="Installed here"
          count={installedN}
        />
      </fieldset>

      {groups.map((g) => (
        <fieldset key={g.id}>
          <legend className="cs-data mb-2 px-2 text-[11px] uppercase tracking-[0.08em] text-cs-ink-3">{g.legend}</legend>
          {g.opts.map((o) => (
            <Row
              key={o.value}
              type="checkbox"
              checked={o.checked}
              disabled={o.live === 0 && !o.checked}
              onChange={() => toggle(g.id, o.value)}
              label={o.label}
              icon={o.icon}
              count={o.live}
            />
          ))}
        </fieldset>
      ))}
    </div>
  );
}

function Row({
  type,
  name,
  checked,
  disabled,
  onChange,
  label,
  icon,
  count,
}: {
  type: "checkbox" | "radio";
  name?: string;
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
  label: string;
  icon?: ReactNode;
  count: number;
}) {
  return (
    <label
      className={
        "group flex min-h-9 cursor-pointer items-center gap-2.5 rounded-[var(--cs-radius-sm)] px-2 text-sm transition-colors duration-150 " +
        "has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-cs-accent " +
        (disabled ? "cursor-not-allowed text-cs-ink-3 opacity-60 " : "text-cs-ink-2 hover:bg-cs-surface-2 hover:text-cs-ink ") +
        (checked ? "bg-cs-surface-2 font-medium text-cs-ink" : "")
      }
    >
      <input
        type={type}
        name={name}
        checked={checked}
        disabled={disabled}
        onChange={onChange}
        className="mk-check size-4 shrink-0 focus-visible:outline-none"
      />
      {icon}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="cs-data text-xs text-cs-ink-3" style={{ fontVariantNumeric: "tabular-nums" }}>
        <span aria-hidden>{count}</span>
        <span className="sr-only">, {count === 1 ? "1 plugin" : `${count} plugins`}</span>
      </span>
    </label>
  );
}
