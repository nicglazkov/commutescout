"use client";

import { useEffect, useState } from "react";

// The public plugin catalog, read live from /api/flare/sources on the
// same origin. The page is a static export, so this small client
// component is the only part that changes without a build. Styled with
// the docs classes (components/docs/docs.css), which /plugins loads.
type Source = {
  id: string;
  name: string;
  attribution?: { name?: string; url?: string } | null;
  trust?: string | null;
  tier?: "approved" | "unreviewed" | "private" | null;
  shared?: boolean | null;
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

  let body: React.ReactNode;
  if (failed) {
    body = (
      <p className="dx-catalog-note">
        The catalog could not be loaded right now. It is also served as JSON at{" "}
        <code className="dx-ic">/api/flare/sources</code>.
      </p>
    );
  } else if (sources === null) {
    body = <p className="dx-catalog-note">Loading the catalog...</p>;
  } else if (sources.length === 0) {
    body = (
      <p className="dx-catalog-note">
        No public plugin is listed yet. CommuteScout&apos;s own community reports are the first source; yours
        can be next.
      </p>
    );
  } else {
    body = (
      <ul className="dx-catalog">
        {sources.map((s) => (
          <li key={s.id}>
            <div>
              <p className="dx-catalog-name">
                {s.name}
                <span className={`dx-tag ${s.tier === "approved" ? "dx-tag-2xx" : "dx-tag-4xx"}`}>
                  {s.tier === "approved" ? "Approved" : "Public, not reviewed"}
                </span>
                {s.shared ? <span className="dx-tag dx-tag-muted">Shared</span> : null}
              </p>
              <p className="dx-catalog-meta">
                {[
                  s.attribution?.name,
                  s.trust,
                  s.count !== undefined ? `${s.count.toLocaleString("en-US")} alerts` : null,
                  s.ok === false ? "not answering" : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <code className="dx-catalog-id">{s.id}</code>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <div aria-live="polite" aria-busy={sources === null && !failed}>
      {body}
    </div>
  );
}
