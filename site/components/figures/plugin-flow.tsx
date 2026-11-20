import { FigureFrame } from "./frame";

// Flare plugins, two paths (protocol: src/ca_roads/flare.py).
// Listed (public or unlisted): CommuteScout reads the plugin, every answer goes through
// accept_alerts (known kinds, ttl at most a day, 500 alerts, 1 MB: flare.py MAX_*), and accepted
// alerts carry the plugin's name and trust tier. The app never calls a listed plugin.
// Private: the user adds the plugin's https URL (and an optional token) in their own settings and
// the app calls it directly with the center of an area. CommuteScout does not see or relay it.
// Static on purpose (owner review): how often and on what grid CommuteScout asks is not published.

type Node = { t: string; d: string; owner: "plugin" | "cs" | "app" };
const LISTED: Node[] = [
  { t: "Plugin server", d: "Answers with alerts around an area", owner: "plugin" },
  { t: "Checks", d: "Every answer is checked against the protocol", owner: "cs" },
  { t: "Labels", d: "Each alert carries the plugin's name and trust level", owner: "cs" },
  { t: "Map and apps", d: "Shown to everyone who uses the plugin", owner: "app" },
];
const PRIVATE: Node[] = [
  { t: "Your settings", d: "The plugin's address, and a token if it needs one", owner: "app" },
  { t: "Your app", d: "Asks the plugin for alerts around an area", owner: "app" },
  { t: "Plugin server", d: "Answers your app directly", owner: "plugin" },
  { t: "Your map", d: "Only you see it. CommuteScout does not see or pass it on", owner: "app" },
];
const OWNER = { plugin: "Plugin", cs: "CommuteScout", app: "You" };

function Lane({ id, title, sub, nodes }: { id: string; title: string; sub: string; nodes: Node[] }) {
  return (
    <section className="pf-lane" data-on="" aria-labelledby={`pf-${id}`}>
      <header className="pf-lane-head">
        <b id={`pf-${id}`}>{title}</b>
        <span>{sub}</span>
      </header>
      <ol className="pf-chain">
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
  return (
    <FigureFrame
      n={n}
      title="Listed and private plugins"
      className="csf-plugin"
      legend={
        <ul className="csf-keys">
          <li className="csf-key">
            <span className="csf-sw pf-sw" data-owner="cs" /> CommuteScout
          </li>
          <li className="csf-key">
            <span className="csf-sw pf-sw" data-owner="plugin" /> The plugin&apos;s server
          </li>
          <li className="csf-key">
            <span className="csf-sw pf-sw" data-owner="app" /> Your app
          </li>
        </ul>
      }
      caption={
        <>
          A listed plugin is read by CommuteScout, checked, and shown with its name on it. A private plugin is yours alone: your
          app calls it directly. Either way the plugin learns an area, never your exact position.
        </>
      }
    >
      <div className="pf">
        <Lane id="listed" title="Listed" sub="Read by CommuteScout" nodes={LISTED} />
        <Lane id="private" title="Private" sub="Called by your app" nodes={PRIVATE} />
      </div>
    </FigureFrame>
  );
}
