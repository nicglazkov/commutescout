"use client";

import { useState } from "react";
import { FigureFrame } from "./frame";

// Flare plugins, two paths (protocol: src/ca_roads/flare.py; poller: src/ca_roads_demo/flare_sources.py).
// Listed (public or unlisted, flare.py:44-59 TIERS / VISIBILITY):
// - added by CommuteScout after validate_manifest (flare.py:250) and a live handshake (validate_handshake, :212)
// - the backend poller asks the plugin, never more often than every 60 s (POLL_FLOOR_S, flare_sources.py:80),
//   and only for one-degree grid-cell centers (CELL_DEG = 1.0, :36), never a user's position
// - every response goes through accept_alerts (flare.py:162): known kinds only (KINDS, :28), ttl at most a day
//   (MAX_TTL_S, :64), at most 500 alerts and 1 MB (MAX_ALERTS / MAX_BYTES, :61-63)
// - accepted alerts become map markers with the plugin's name and trust tier; the app never calls the plugin
// - a report sent to the plugin carries a per-plugin pseudonym, not the account (reporter_pseudonym, :275)
// Private (visibility "private"):
// - a user adds the plugin's https URL (and an optional token) in their own settings
// - the user's app calls the plugin directly, with only a snapped tile center
// - CommuteScout does not review, validate or relay it, and nobody else sees it.

type View = "both" | "listed" | "private";
type Node = { t: string; d: string; owner: "plugin" | "cs" | "app" };
const LISTED: Node[] = [
  { t: "Plugin server", d: "Listed after a manifest check and a live handshake", owner: "plugin" },
  { t: "Poller", d: "Asks at most once a minute, for grid-cell centers only", owner: "cs" },
  { t: "Checks", d: "Known kinds, ttl up to a day, 500 alerts, 1 MB", owner: "cs" },
  { t: "Map markers", d: "Labelled with the plugin's name and trust tier", owner: "cs" },
  { t: "Everyone's map", d: "The app reads markers; it never calls the plugin", owner: "app" },
];
const PRIVATE: Node[] = [
  { t: "Your settings", d: "An https URL and an optional token", owner: "app" },
  { t: "Your app", d: "Calls the plugin itself, sending a snapped tile center", owner: "app" },
  { t: "Plugin server", d: "Answers your app directly", owner: "plugin" },
  { t: "Your map only", d: "No review, no checks, no relay by CommuteScout", owner: "app" },
];
const OWNER = { plugin: "Plugin", cs: "CommuteScout", app: "You" };

function Lane({ id, title, sub, nodes, on }: { id: string; title: string; sub: string; nodes: Node[]; on: boolean }) {
  return (
    <section className="pf-lane" data-on={on ? "" : undefined} aria-labelledby={`pf-${id}`}>
      <header className="pf-lane-head">
        <b id={`pf-${id}`}>{title}</b>
        <span>{sub}</span>
      </header>
      <ol className="pf-chain" data-count={nodes.length}>
        {nodes.map((nd, i) => (
          <li key={nd.t} className="pf-node" data-owner={nd.owner}>
            <span className="pf-owner">{OWNER[nd.owner]}</span>
            <b>
              <span className="csf-sr">Step {i + 1}: </span>
              {nd.t}
            </b>
            <span className="pf-d">{nd.d}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function PluginFlow({ n = 8 }: { n?: number | string }) {
  const [view, setView] = useState<View>("both");
  return (
    <FigureFrame
      n={n}
      title="Listed and private plugins"
      className="csf-plugin"
      hint="Compare the two paths"
      readout={view === "private" ? "Private: app to plugin, nothing in between" : view === "listed" ? "Listed: plugin to poller to checks to map" : "2 paths · 1 mediated, 1 direct"}
      controls={
        <div className="csf-controls" role="group" aria-label="Show a path">
          {(
            [
              ["both", "Both"],
              ["listed", "Listed"],
              ["private", "Private"],
            ] as [View, string][]
          ).map(([v, l]) => (
            <button key={v} type="button" className="csf-chip" aria-pressed={view === v} onClick={() => setView(v)}>
              {l}
            </button>
          ))}
        </div>
      }
      legend={
        <ul className="csf-keys">
          <li className="csf-key">
            <span className="csf-sw pf-sw" data-owner="cs" /> Runs on CommuteScout
          </li>
          <li className="csf-key">
            <span className="csf-sw pf-sw" data-owner="plugin" /> Runs on the plugin&apos;s server
          </li>
          <li className="csf-key">
            <span className="csf-sw pf-sw" data-owner="app" /> Runs in your app
          </li>
        </ul>
      }
      caption={
        <>
          A listed plugin is mediated: CommuteScout polls it, checks every answer, and shows the result to everyone with the
          plugin&apos;s name on it. A private plugin is yours alone: your app calls it directly and CommuteScout never sees,
          checks or relays what it returns. Either way the plugin learns an area, not your exact position.
        </>
      }
    >
      <div className="pf" data-view={view}>
        <Lane id="listed" title="Listed" sub="Mediated by CommuteScout" nodes={LISTED} on={view !== "private"} />
        <Lane id="private" title="Private" sub="Direct from your app" nodes={PRIVATE} on={view !== "listed"} />
      </div>
    </FigureFrame>
  );
}
