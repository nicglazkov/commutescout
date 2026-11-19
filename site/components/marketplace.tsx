"use client";

import { useEffect, useState } from "react";
import { Camera, Check, MapPin, Puzzle, Users } from "lucide-react";

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

// What a plugin is mostly about, read from its kinds: it picks the icon
// and its color, the way a store listing has an app icon.
function category(kinds?: string[]): "cameras" | "crowd" | "other" {
  const k = kinds || [];
  if (k.length > 0 && k.every((x) => x.startsWith("CAMERA"))) return "cameras";
  if (k.some((x) => x.startsWith("POLICE") || x.startsWith("CRASH") || x.startsWith("HAZARD"))) return "crowd";
  return "other";
}

const ICONS = {
  cameras: { Icon: Camera, tile: "bg-cs-surface-2 text-cs-ink-2" },
  crowd: { Icon: Users, tile: "bg-cs-accent-soft text-cs-accent" },
  other: { Icon: Puzzle, tile: "bg-cs-surface-2 text-cs-ink-2" },
} as const;

function PluginIcon({ kinds }: { kinds?: string[] }) {
  const { Icon, tile } = ICONS[category(kinds)];
  return (
    <div
      className={"flex size-12 shrink-0 items-center justify-center rounded-[var(--cs-radius-md)] border border-cs-line " + tile}
      aria-hidden
    >
      <Icon className="size-6" strokeWidth={1.75} />
    </div>
  );
}

function kindChips(kinds?: string[]): string[] {
  const label = kindsLabel(kinds);
  return label ? label.split(", ") : [];
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 flex-1 sm:px-3 sm:text-center sm:first:pl-0 sm:last:pr-0">
      <dt className="cs-data text-[11px] uppercase tracking-[0.06em] text-cs-ink-3">{label}</dt>
      <dd className="mt-1 truncate text-sm font-medium text-cs-ink" style={{ fontVariantNumeric: "tabular-nums" }}>
        {value}
      </dd>
    </div>
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
    return <p role="status" className="mt-10 rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-6 text-sm text-cs-ink-2">The marketplace could not be loaded right now. Try again in a minute.</p>;
  }
  if (sources === null) {
    return <p role="status" className="mt-10 rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong p-6 text-sm text-cs-ink-3">Loading plugins…</p>;
  }
  if (sources.length === 0) {
    return <p className="mt-10 rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-6 text-cs-ink-2">No plugin is listed yet.</p>;
  }
  return (
    <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2">
      {sources.map((s) => {
        const installed = isInstalled(s);
        const approved = s.tier === "approved";
        // An operator named the same as its plugin says nothing twice.
        const named = s.attribution?.name && s.attribution.name !== s.name ? s.attribution.name : "";
        const operator = named || "Run by its community";
        return (
          <article
            key={s.id}
            className="flex min-w-0 flex-col rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-5 shadow-[var(--cs-shadow-sm)] transition-[border-color,box-shadow] duration-150 hover:border-cs-line-strong hover:shadow-[var(--cs-shadow-md)] sm:p-6"
            data-plugin={s.id}
          >
            <div className="flex items-center gap-4">
              <PluginIcon kinds={s.kinds} />
              <div className="min-w-0 flex-1">
                <h2 className="cs-h3 text-balance">{s.name}</h2>
                <p className="mt-0.5 truncate text-sm text-cs-ink-3">
                  {s.attribution?.url ? (
                    <a href={s.attribution.url} className="hover:text-cs-accent hover:underline">
                      {operator}
                    </a>
                  ) : (
                    operator
                  )}
                </p>
              </div>
              <button
                type="button"
                onClick={() => toggle(s)}
                className={
                  "inline-flex h-9 shrink-0 items-center gap-1 rounded-[var(--cs-radius-md)] px-4 text-sm font-medium transition-colors duration-150 " +
                  (installed
                    ? "border border-cs-line-strong bg-cs-surface text-cs-ink hover:bg-cs-surface-2"
                    : "bg-cs-accent text-cs-accent-ink hover:bg-cs-accent-hover")
                }
                aria-pressed={installed}
              >
                {installed && <Check className="size-4" aria-hidden />}
                {installed ? "Installed" : "Install"}
              </button>
            </div>

            <p className="mt-4 text-[0.9375rem] leading-relaxed text-cs-ink-2">
              {s.description || (kindsLabel(s.kinds) ? `Shows ${kindsLabel(s.kinds)}.` : "Community alerts for the map.")}
            </p>

            {kindChips(s.kinds).length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="What it shows">
                {kindChips(s.kinds).map((k) => (
                  <li key={k} className="rounded-[var(--cs-radius-sm)] border border-cs-line bg-cs-bg px-2 py-0.5 text-xs capitalize text-cs-ink-2">
                    {k}
                  </li>
                ))}
              </ul>
            )}

            <dl className="mt-5 grid grid-cols-2 gap-y-4 border-y border-cs-line py-3 sm:flex sm:divide-x sm:divide-cs-line">
              <Stat label="Alerts now" value={s.ok === false ? "Offline" : (s.count ?? 0).toLocaleString()} />
              <Stat label="Coverage" value={coverageLabel(s.coverage)} />
              <Stat label="Reports" value={s.capabilities?.report ? "Accepted" : "Read only"} />
              <Stat label="Price" value="Free" />
            </dl>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <span
                className={
                  "rounded-full px-2.5 py-0.5 text-xs font-medium " +
                  (approved ? "bg-cs-ok-soft text-cs-ok" : "border border-cs-line-strong text-cs-ink-2")
                }
              >
                {approved ? "Approved by CommuteScout" : "Public, not reviewed"}
              </span>
              <a
                href={`/map?plugin=${encodeURIComponent(s.id)}`}
                className="inline-flex items-center gap-1 text-sm font-medium text-cs-accent hover:underline"
              >
                <MapPin className="size-4" aria-hidden />
                See it on the map
              </a>
            </div>
            {s.visibility === "unlisted" && (
              <p className="mt-3 text-xs text-cs-ink-3">Unlisted: shared with you by link, not on the catalog.</p>
            )}
            {!approved && (
              <p className="mt-3 text-xs text-cs-ink-3">
                Use at your own risk. Its alerts are spoken like any other; turn voice off in the
                app&apos;s alert settings.
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
