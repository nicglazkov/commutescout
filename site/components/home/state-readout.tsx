"use client";

import { useId, useState, type PointerEvent, type ReactNode } from "react";
import { Check, Minus } from "lucide-react";
import { LAYERS, PARTIAL, ROW_BY_NAME, cellWord, depthFill, has } from "./coverage-data";

// The state map's interactive half. The shaded outlines are server-rendered
// (the `map` prop, one <path data-st="Ohio" id="cov-39"> per state), so
// this file carries no geometry: pointer events are read off the map by
// delegation, the chosen state is outlined by a <use> of its path, and a
// <select> gives keyboard and screen-reader users every state, including
// the small eastern ones that are hard to hit on a phone.

type St = { id: string; name: string };

const DEFAULT = "Ohio";

function DepthScale() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-cs-ink-2">
      <span className="inline-flex items-center gap-1.5">
        <span aria-hidden className="flex overflow-hidden rounded-sm ring-1 ring-cs-line">
          {[1, 2, 3, 4, 5].map((d) => (
            <span key={d} className="h-2.5 w-4" style={{ background: depthFill(d) }} />
          ))}
        </span>
        1 to 5 kinds of report from the state
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span aria-hidden className="h-2.5 w-4 rounded-sm ring-1 ring-cs-line-strong" style={{ background: depthFill(-1) }} />
        Nationwide layers only
      </span>
    </div>
  );
}

export function StateReadout({ map, states }: { map: ReactNode; states: St[] }) {
  const [st, setSt] = useState(DEFAULT);
  const selectId = useId();
  const row = ROW_BY_NAME[st];
  const active = states.find((s) => s.name === st);

  const pick = (e: PointerEvent<HTMLDivElement>) => {
    const el = (e.target as Element).closest?.("[data-st]");
    const name = el?.getAttribute("data-st");
    if (name && name !== st) setSt(name);
  };

  const withFeeds = states.filter((s) => ROW_BY_NAME[s.name]).sort((a, b) => a.name.localeCompare(b.name));
  const national = states.filter((s) => !ROW_BY_NAME[s.name]).sort((a, b) => a.name.localeCompare(b.name));
  const count = row ? LAYERS.filter((l) => has(row[l.key])).length : 0;

  return (
    <div className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface">
      <div className="grid md:grid-cols-[1fr_15.5rem]">
        <div className="flex min-w-0 flex-col justify-center p-4 sm:p-5">
          {/* Pointer only: the select beside it is the keyboard path. */}
          <div className="relative cursor-pointer" onPointerOver={pick} onPointerDown={pick}>
            {map}
            {active && (
              <svg viewBox="0 0 975 610" aria-hidden className="pointer-events-none absolute inset-0 h-full w-full">
                <use href={`#cov-${active.id}`} stroke="var(--cs-ink)" strokeWidth={2} strokeLinejoin="round" />
              </svg>
            )}
          </div>
          <div className="mt-3">
            <DepthScale />
          </div>
        </div>

        <div className="flex flex-col border-t border-cs-line p-5 md:border-l md:border-t-0">
          <label htmlFor={selectId} className="text-xs font-medium text-cs-ink-2">
            State
          </label>
          <select
            id={selectId}
            value={st}
            onChange={(e) => setSt(e.target.value)}
            className="mt-1.5 h-10 w-full rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-bg px-3 text-[0.9375rem] font-medium text-cs-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-cs-accent"
          >
            <optgroup label="With the state's own feeds">
              {withFeeds.map((s) => (
                <option key={s.id} value={s.name}>
                  {s.name}
                </option>
              ))}
            </optgroup>
            <optgroup label="Nationwide layers only">
              {national.map((s) => (
                <option key={s.id} value={s.name}>
                  {s.name}
                </option>
              ))}
            </optgroup>
          </select>

          <div aria-live="polite" className="mt-4 flex flex-1 flex-col">
            <p className="text-[0.8125rem] text-cs-ink-2">
              {row ? (
                <>
                  <span className="font-semibold tabular-nums text-cs-ink">{count}</span> of {LAYERS.length} kinds from{" "}
                  {st}&rsquo;s own agencies{PARTIAL.has(st) ? ", in one metro area" : ""}
                </>
              ) : (
                <>No feeds of its own yet. {st} has the nationwide layers.</>
              )}
            </p>
            <ul className="mt-3 divide-y divide-cs-line border-y border-cs-line text-[0.8125rem]">
              {LAYERS.map((l) => {
                const v = row?.[l.key] ?? "-";
                const yes = has(v);
                return (
                  <li key={l.key} className="flex min-h-8 items-center justify-between gap-2 py-1">
                    <span className={yes ? "text-cs-ink" : "text-cs-ink-3"}>{l.label}</span>
                    {yes ? (
                      <span className="inline-flex items-center gap-1.5">
                        {v !== "Y" && <span className="text-xs text-cs-ink-2">{cellWord(v)}</span>}
                        <Check aria-hidden className="size-3.5 text-cs-ok" />
                        <span className="sr-only">yes</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-xs text-cs-ink-3">
                        {row && v === "n/a" ? cellWord(v) : <span className="sr-only">no</span>}
                        <Minus aria-hidden className="size-3.5" />
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
            <p className="mt-auto pt-4 text-xs leading-relaxed text-cs-ink-3">
              Every state also has weather alerts, wildfires and live traffic.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
