"use client";

import { useEffect, useState } from "react";

// The plugin marketplace: one tile per listed plugin, read live from
// /api/flare/sources. "Install" on the web turns the plugin's layer on
// for this browser (the map reads the same key); the apps keep their own
// switch per phone. An unlisted plugin is never in the catalog: it is
// shared by link (/marketplace?plugin=<id>) and shows on the map only
// once installed here, so a second key holds those.
type Source = {
  id: string;
  name: string;
  visibility?: "public" | "unlisted" | null;
  description?: string | null;
  attribution?: { name?: string; url?: string } | null;
  tier?: "approved" | "unreviewed" | "private" | null;
  count?: number;
  ok?: boolean | null;
  coverage?: number[] | null;
  kinds?: string[];
  capabilities?: Record<string, boolean>;
  base?: string | null;
};

const KEY = "cs.plugins.off"; // ids switched off in this browser, comma separated
const ON_KEY = "cs.plugins.on"; // unlisted ids installed in this browser

function idSet(key: string): Set<string> {
  try {
    return new Set((localStorage.getItem(key) || "").split(",").filter(Boolean));
  } catch {
    return new Set();
  }
}

function offSet(): Set<string> {
  return idSet(KEY);
}

function saveSet(key: string, ids: Set<string>) {
  try {
    localStorage.setItem(key, Array.from(ids).join(","));
  } catch {
    /* private mode */
  }
}

function coverageLabel(b?: number[] | null): string {
  if (!b || b.length !== 4) return "Coverage not stated";
  const [s, w, n, e] = b;
  const h = n - s, wd = e - w;
  if (h >= 20 && wd >= 50) return "Whole country";
  if (s >= 32 && n <= 36 && w >= -121 && e <= -114) return "Southern California";
  if (s >= 32 && n <= 42.5 && w >= -125 && e <= -114) return "California";
  return `${Math.round(h)}° by ${Math.round(wd)}° area`;
}

function kindsLabel(kinds?: string[]): string {
  if (!kinds || kinds.length === 0) return "";
  const groups = new Set<string>();
  for (const k of kinds) {
    if (k.startsWith("POLICE")) groups.add("police");
    else if (k.startsWith("CRASH")) groups.add("crashes");
    else if (k.startsWith("HAZARD")) groups.add("hazards");
    else if (k.startsWith("JAM")) groups.add("jams");
    else if (k.startsWith("ROAD_CLOSED") || k.startsWith("LANE")) groups.add("closures");
    else if (k.startsWith("WEATHER")) groups.add("weather");
    else if (k.startsWith("CAMERA")) groups.add("cameras");
    else if (k.startsWith("CHAINS")) groups.add("chain controls");
    else groups.add("other");
  }
  return Array.from(groups).join(", ");
}

function Tier({ tier }: { tier?: string | null }) {
  const approved = tier === "approved";
  return (
    <span
      className={
        "rounded-full px-2 py-0.5 text-[11px] font-semibold " +
        (approved ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800")
      }
    >
      {approved ? "Approved" : "Public, not reviewed"}
    </span>
  );
}

export function Marketplace() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [off, setOff] = useState<Set<string>>(new Set());
  const [on, setOn] = useState<Set<string>>(new Set());

  useEffect(() => {
    // The browser's own switches are read once the catalog arrives, so no
    // state is set synchronously inside the effect. A ?plugin=<id> link
    // brings an unlisted plugin along, fetched by id and shown first.
    const wanted = new URLSearchParams(window.location.search).get("plugin") || "";
    const headers = { Accept: "application/json" };
    const catalog = fetch("/api/flare/sources", { headers }).then((r) =>
      r.ok ? r.json() : Promise.reject(r.status),
    );
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
        setOff(offSet());
        setOn(idSet(ON_KEY));
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
    saveSet(KEY, next);
  }

  if (failed) {
    return <p className="text-cs-ink/60 mt-6 text-sm">The marketplace could not be loaded right now.</p>;
  }
  if (sources === null) {
    return <p className="text-cs-ink/60 mt-6 text-sm">Loading plugins…</p>;
  }
  if (sources.length === 0) {
    return <p className="text-cs-ink/70 mt-6">No plugin is listed yet.</p>;
  }
  return (
    <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {sources.map((s) => {
        const installed = isInstalled(s);
        return (
          <article
            key={s.id}
            className="flex flex-col rounded-2xl border border-cs-ink/10 bg-white p-5 shadow-sm"
            data-plugin={s.id}
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-semibold leading-tight text-cs-ink">{s.name}</h2>
              <Tier tier={s.tier} />
            </div>
            {s.visibility === "unlisted" && (
              <p className="text-cs-ink/60 mt-1 text-xs">Unlisted: shared with you by link, not on the catalog.</p>
            )}
            <p className="text-cs-ink/70 mt-2 text-sm">
              {s.description || (kindsLabel(s.kinds) ? `Shows ${kindsLabel(s.kinds)}.` : "Community alerts for the map.")}
            </p>
            <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-cs-ink/60">
              <dt>Coverage</dt>
              <dd className="text-cs-ink">{coverageLabel(s.coverage)}</dd>
              <dt>Alerts now</dt>
              <dd className="text-cs-ink" style={{ fontVariantNumeric: "tabular-nums" }}>
                {s.ok === false ? "not answering" : (s.count ?? 0).toLocaleString()}
              </dd>
              <dt>Kinds</dt>
              <dd className="text-cs-ink">{kindsLabel(s.kinds) || "—"}</dd>
              <dt>Operator</dt>
              <dd className="text-cs-ink">
                {s.attribution?.url ? (
                  <a href={s.attribution.url} className="text-cs-sky hover:underline">
                    {s.attribution?.name || s.name}
                  </a>
                ) : (
                  s.attribution?.name || "Not stated"
                )}
              </dd>
              <dt>Reports</dt>
              <dd className="text-cs-ink">{s.capabilities?.report ? "accepted" : "read only"}</dd>
              <dt>Price</dt>
              <dd className="text-cs-ink">Free</dd>
            </dl>
            <div className="mt-5 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => toggle(s)}
                className={
                  "rounded-full px-4 py-2 text-sm font-medium transition-colors " +
                  (installed
                    ? "border border-cs-ink/20 text-cs-ink hover:bg-cs-bg"
                    : "bg-cs-navy text-white hover:bg-cs-navy/90")
                }
                aria-pressed={installed}
              >
                {installed ? "Installed" : "Install"}
              </button>
              <a href={`/map?plugin=${encodeURIComponent(s.id)}`} className="text-sm text-cs-sky hover:underline">
                See it on the map
              </a>
            </div>
            {s.tier !== "approved" && (
              <p className="text-cs-ink/50 mt-3 text-[11px]">
                Not reviewed by CommuteScout. Use at your own risk; it never speaks unless you turn voice on for it.
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
