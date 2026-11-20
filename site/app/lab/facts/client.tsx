"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

// Small tab set for the board's mockups (client switcher, language
// switcher). Arrow keys move between tabs, as the ARIA tabs pattern asks.
export function FxTabs({ label, tabs }: { label: string; tabs: { id: string; label: string; body: ReactNode }[] }) {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const uid = useId();
  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const n = (active + d + tabs.length) % tabs.length;
    setActive(n);
    refs.current[n]?.focus();
  }
  return (
    <div className="fx-tabs">
      <div role="tablist" aria-label={label} className="fx-tablist" onKeyDown={onKey}>
        {tabs.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            role="tab"
            type="button"
            id={`${uid}-t-${t.id}`}
            aria-selected={i === active}
            aria-controls={`${uid}-p-${t.id}`}
            tabIndex={i === active ? 0 : -1}
            onClick={() => setActive(i)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tabs.map((t, i) => (
        <div
          key={t.id}
          role="tabpanel"
          id={`${uid}-p-${t.id}`}
          aria-labelledby={`${uid}-t-${t.id}`}
          hidden={i !== active}
          className="fx-tabpanel"
        >
          {t.body}
        </div>
      ))}
    </div>
  );
}

// The public catalog size, read live from the same endpoint the plugins
// page's catalog uses. Shows a dash until (or unless) it answers.
export function LiveCatalogCount({ what = "plugins" }: { what?: "plugins" | "alerts" }) {
  const [n, setN] = useState<number | null>(null);
  useEffect(() => {
    let alive = true;
    fetch("/api/flare/sources", { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!alive || !d) return;
        const list: { count?: number }[] | null = Array.isArray(d.sources) ? d.sources : null;
        if (!list) return;
        setN(what === "plugins" ? list.length : list.reduce((t, x) => t + (x.count ?? 0), 0));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [what]);
  return <>{n === null ? "–" : n.toLocaleString("en-US")}</>;
}
