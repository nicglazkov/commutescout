"use client";

import { useEffect, useState } from "react";

// The public plugin catalog, read live from /api/flare/sources on the
// same origin. The page is a static export, so this small client
// component is the only part that changes without a build.
type Source = {
  id: string;
  name: string;
  attribution?: { name?: string; url?: string } | null;
  trust?: string | null;
  tier?: "approved" | "unreviewed" | "private" | null;
  count?: number;
  ok?: boolean | null;
  last_ok?: string | null;
};

export function PluginCatalog() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/api/flare/sources", { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => setSources(Array.isArray(d.sources) ? d.sources : []))
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <p className="text-cs-ink/60 mt-4 text-sm">
        The catalog could not be loaded right now. It is also served as JSON at{" "}
        <code className="rounded bg-cs-ink/5 px-1.5 py-0.5 text-[0.85em]">/api/flare/sources</code>.
      </p>
    );
  }
  if (sources === null) {
    return <p className="text-cs-ink/60 mt-4 text-sm">Loading the catalog…</p>;
  }
  if (sources.length === 0) {
    return (
      <p className="text-cs-ink/70 mt-4 text-balance">
        No public plugin is listed yet. CommuteScout&apos;s own community reports are the
        first source; yours can be next.
      </p>
    );
  }
  return (
    <ul className="mt-6 divide-y divide-cs-ink/10 rounded-2xl border border-cs-ink/10 bg-white">
      {sources.map((s) => (
        <li key={s.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-5 py-4">
          <div>
            <p className="font-medium text-cs-ink">
              {s.name}{" "}
              <span
                className={
                  "ml-1 rounded-full px-2 py-0.5 text-[11px] font-semibold " +
                  (s.tier === "approved"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-amber-100 text-amber-800")
                }
              >
                {s.tier === "approved" ? "Approved" : "Public, not reviewed"}
              </span>
            </p>
            <p className="text-cs-ink/60 text-sm">
              {[s.attribution?.name, s.trust, s.count !== undefined ? `${s.count} alerts` : null,
                s.ok === false ? "not answering" : null]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <code className="text-cs-ink/50 text-xs">{s.id}</code>
        </li>
      ))}
    </ul>
  );
}
