import type { Metadata } from "next";
import Link from "next/link";
import { PluginCatalog } from "@/components/plugin-catalog";
import { DocsShell, Section, type TocItem } from "@/components/docs/docs-shell";
import { C, CodeBlock } from "@/components/docs/code-block";
import { Callout } from "@/components/docs/callout";
import { DocFigure } from "@/components/docs/doc-figure";
import { ArrowRight, Lock, ShieldAlert, ShieldCheck } from "lucide-react";
import { InstallFlow } from "./install-flow";
import "./plugins.css";

// The plugins section: what Flare is, how a plugin is run (private,
// unlisted or public), the full protocol, the rules, the conformance
// check, and the live public catalog. Source of truth for every factual
// claim is docs/flare.md (the specification, version 1) and
// src/ca_roads/flare.py (capabilities, kinds, caps, tier_of). This page
// restyles that document rather than rewording it; its examples use a
// generic plugin id instead of the spec's.
export const metadata: Metadata = {
  title: "Plugins - CommuteScout",
  description:
    "Flare is CommuteScout's open protocol for road alert sources: run a private, unlisted or public plugin that shows on the map and in the apps, with reports and confirmations.",
  alternates: {
    canonical: "https://commutescout.com/plugins",
  },
  openGraph: {
    title: "Plugins - CommuteScout",
    description:
      "Flare is CommuteScout's open protocol for road alert sources: run a private, unlisted or public plugin that shows on the map and in the apps, with reports and confirmations.",
    url: "https://commutescout.com/plugins",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

const TOC: TocItem[] = [
  { id: "install", label: "Install a plugin" },
  { id: "ways", label: "Trust levels" },
  { id: "catalog", label: "Public catalog" },
  { id: "what", label: "What a plugin is" },
  { id: "topology", label: "Who talks to whom" },
  { id: "start", label: "Build one" },
  {
    id: "endpoints",
    label: "Endpoints",
    children: [
      { id: "ep-handshake", label: "handshake" },
      { id: "ep-alerts", label: "alerts" },
      { id: "ep-report", label: "report" },
      { id: "ep-confirm", label: "confirm" },
      { id: "ep-snapshot", label: "snapshot" },
      { id: "ep-errors", label: "Errors" },
    ],
  },
  { id: "kinds", label: "Alert kinds" },
  { id: "record", label: "Alert record" },
  { id: "manifest", label: "Manifest and trust" },
  { id: "shared", label: "Shared data" },
  { id: "rules", label: "Rules" },
  { id: "conformance", label: "Conformance" },
  { id: "listing", label: "Get listed" },
  { id: "roadmap", label: "Roadmap" },
];

// The three levels a plugin is shown as (tier_of in src/ca_roads/flare.py),
// each with its own color so a reader can tell them apart at a glance. The
// same color marks the level everywhere on this page.
const TIERS = [
  {
    id: "approved",
    icon: ShieldCheck,
    name: "Approved",
    meta: "public · official or verified",
    body: "Reviewed by CommuteScout: the operator is known and the feed passed review. Drawn by default and badged as approved.",
    rows: ["Reviewed by CommuteScout", "Found in the marketplace", "No notice to tick", "Read through CommuteScout"],
  },
  {
    id: "unreviewed",
    icon: ShieldAlert,
    name: "Public, not reviewed",
    meta: "public or unlisted · community",
    body: "Anyone whose plugin passes the conformance check can be listed. It shows on the map, labelled as not reviewed, and alerts only after you tick the notice at install. Unlisted plugins are this level too, shared by link instead of listed.",
    rows: ["Passed the conformance check", "In the marketplace, or shared by link", "Notice ticked at install", "Read through CommuteScout"],
  },
  {
    id: "private",
    icon: Lock,
    name: "Private",
    meta: "added by URL on one device",
    body: "Something you run for your own devices, called straight from the app, with your own bearer token if you want one. It needs the same notice ticked at install, and may show anything, including personal data.",
    rows: ["Not reviewed", "Added by its URL in the app", "Notice ticked at install", "Called straight from your app"],
  },
] as const;

const KIND_TONE: Record<string, string> = {
  Police: "police",
  Crash: "incident",
  Hazard: "hazard",
  Weather: "weather",
  Closures: "closure",
  Traffic: "traffic",
  Chains: "chain",
  Cameras: "camera",
  Other: "other",
};

const CAPABILITIES: [string, string, boolean][] = [
  ["alerts", "Serve alerts near a point.", true],
  ["report", "Accept a new report from a user: police, crash, hazard, and the rest.", false],
  ["confirm", "Accept a \"still there\" or \"not there\" vote on an alert.", false],
  ["notify", "Mark alerts the apps may announce, not just draw. Announced in the apps only.", false],
  ["snapshot", "Serve the whole list in one response, for data that is the same for everyone.", false],
];

const KIND_GROUPS: [string, string[]][] = [
  ["Police", ["POLICE_VISIBLE", "POLICE_HIDING", "POLICE_OTHER"]],
  ["Crash", ["CRASH_MINOR", "CRASH_MAJOR"]],
  [
    "Hazard",
    [
      "HAZARD_ON_ROAD",
      "HAZARD_OBJECT",
      "HAZARD_POTHOLE",
      "HAZARD_ANIMAL",
      "HAZARD_CONSTRUCTION",
      "HAZARD_SHOULDER",
      "HAZARD_SHOULDER_CAR",
      "HAZARD_SHOULDER_ANIMAL",
    ],
  ],
  ["Weather", ["WEATHER_FLOOD", "WEATHER_FOG", "WEATHER_ICE", "WEATHER_HAIL", "WEATHER_SNOW"]],
  ["Closures", ["ROAD_CLOSED", "LANE_CLOSED", "RAMP_CLOSED"]],
  ["Traffic", ["JAM_MODERATE", "JAM_HEAVY", "JAM_STANDSTILL"]],
  ["Chains", ["CHAINS_REQUIRED", "CHAINS_NOT_REQUIRED"]],
  ["Cameras", ["CAMERA_SPEED", "CAMERA_RED_LIGHT", "CAMERA_ISSUE"]],
  ["Other", ["MAP_ISSUE", "OTHER"]],
];
const KIND_COUNT = KIND_GROUPS.reduce((n, [, k]) => n + k.length, 0);

const HANDSHAKE = `{
  "protocol": "flare/1",
  "id": "example-alerts",
  "name": "Example Alerts",
  "version": "2.1.0",
  "capabilities": {"alerts": true, "report": true, "confirm": true, "notify": true, "snapshot": false},
  "kinds": ["POLICE_VISIBLE", "POLICE_HIDING", "CRASH_MAJOR", "HAZARD_ON_ROAD"],
  "coverage": {"bbox": [MIN_LAT, MIN_LON, MAX_LAT, MAX_LON]},
  "refresh_s": 60,
  "attribution": {"name": "Example Alerts", "url": "https://example.com"},
  "contact": "mailto:owner@example.com",
  "auth": "none"
}`;

const ALERTS = `GET /flare/v1/alerts?lat=LAT&lon=LON&r=50000

200 {"alerts": [ ...alert records... ], "ttl_s": 60, "as_of": "2026-09-16T18:30:00-07:00"}`;

const REPORT = `{
  "kind": "HAZARD_ON_ROAD",
  "lat": LAT, "lon": LON,
  "heading_deg": 270,
  "ts": "2026-09-16T18:40:00-07:00",
  "description": "Ladder in the number 2 lane",
  "reporter": "r:9d2c8f...",
  "client": "commutescout-ios/1.0"
}`;

const REPORT_REPLIES = `201 {"id": "...", "alert": {...}}     accepted
202 {"queued": true}                 the plugin will decide later
422 {"error": {...}}                 refused, for example too far from a road`;

const CONFIRM = `{"alert_id": "example-alerts:2026-09-16:8f3a", "vote": "up", "ts": "...", "reporter": "r:9d2c8f..."}`;

const SNAPSHOT = `GET /flare/v1/snapshot

200 {"alerts": [ ...every alert... ], "ttl_s": 3600, "as_of": "2026-09-16T18:30:00-07:00"}`;

const RECORD = `{
  "id": "example-alerts:2026-09-16:8f3a",
  "kind": "POLICE_VISIBLE",
  "lat": LAT,
  "lon": LON,
  "heading_deg": 270,
  "road_names": ["ROUTE N"],
  "description": "Officer on the right shoulder past the exit",
  "report_ts": "2026-09-16T18:04:11-07:00",
  "confirm_ts": "2026-09-16T18:21:02-07:00",
  "n_confirmations": 3,
  "reliability": 0.8,
  "ttl_s": 1800,
  "notify": true,
  "geometry": {"type": "LineString", "coordinates": [[LON, LAT], [LON2, LAT2]]},
  "source_url": "https://example.com/alerts/8f3a",
  "extra": {"unit": "Unit 42"}
}`;

const RECORD_FIELDS: [string, boolean, string][] = [
  ["id", true, "Stable within the plugin. Confirmations and updates refer to it."],
  ["kind", true, "One of the kinds above. Unknown kinds are dropped."],
  ["lat, lon", true, "Where the alert is. For a stretch, the start."],
  ["heading_deg", false, "Direction of travel it applies to, 0 to 359. Omit for both directions."],
  ["road_names", false, "Road names as signed, most specific first."],
  ["description", false, "One sentence for a person. At most 200 characters."],
  ["report_ts", true, "When it was first reported."],
  ["confirm_ts", false, "When it was last confirmed."],
  ["n_confirmations", false, "Count of confirmations, 0 if none."],
  ["reliability", false, "0 to 1, the plugin's own confidence. Default 0.5."],
  ["ttl_s", true, "Seconds from report_ts (or confirm_ts when present) after which the alert is stale. At most 86400."],
  ["notify", false, "The app may announce it as the driver approaches. Needs the notify capability."],
  ["geometry", false, "GeoJSON Point or LineString when the alert covers a stretch. At most 500 points."],
  ["source_url", false, "Where a person can read more."],
  ["extra", false, "Anything else, at most 2 KB, shown in the details pane as key: value."],
];

const MANIFEST = `{
  "id": "example-alerts",
  "name": "Example Alerts",
  "base": "https://plugins.example.com",
  "protocol": "flare/1",
  "visibility": "public",
  "trust": "community",
  "attribution": {"name": "Example Alerts", "url": "https://example.com"}
}`;

const ERROR_ENVELOPE = `{"error": {"code": "outside_coverage", "message": "...", "hint": "..."}}`;

const ERROR_CODES: [string, string][] = [
  ["bad_request", "The request is malformed. Unknown codes are treated as this one."],
  ["unauthorized", "A bearer token is missing or wrong."],
  ["outside_coverage", "The point is outside coverage.bbox."],
  ["too_far_from_road", "A report was refused because it is not near a road."],
  ["rate_limited", "Slow down. Sent with Retry-After."],
  ["unknown_alert", "A confirm named an alert the plugin does not have."],
  ["unavailable", "The plugin cannot answer right now."],
];

const CALLER_RULES = [
  "Never send a user's exact position to a plugin. Send the center of an area.",
  "Never send an account identifier. reporter is a per-plugin pseudonym.",
  "Honor refresh_s, ttl_s, coverage.bbox and Retry-After.",
  "Drop alerts with unknown kind, no ttl_s, or past their ttl_s.",
  "Cap what one plugin can show: 500 alerts and 1 MB per response. A plugin over the caps is trimmed, not refused.",
  "Official agency data always outranks plugin alerts on the same spot.",
];

const PLUGIN_RULES = [
  "Serve over HTTPS with a valid certificate. Answer the handshake without authentication.",
  "Keep id stable for the life of an alert. Reusing an id means an update.",
  "Set ttl_s honestly. Stale alerts are the fastest way to lose trust.",
  "Do not log the callers' addresses beyond what abuse control needs.",
  "Say who you are: attribution and contact in the handshake.",
];

const START = `git clone https://github.com/nicglazkov/commutescout
cd commutescout/examples/flare-plugin
pip install starlette uvicorn && python server.py
python -m ca_roads.flare check http://127.0.0.1:8300`;

function Endpoint({
  id,
  method,
  path,
  needs,
  children,
}: {
  id: string;
  method: "GET" | "POST";
  path: string;
  needs?: string;
  children: React.ReactNode;
}) {
  return (
    <article className="dx-endpoint" aria-labelledby={id}>
      <div className="dx-endpoint-head">
        <div className="dx-endpoint-title">
          <h3 id={id} className="dx-endpoint-name">
            {path.split("/").pop()}
          </h3>
          {needs ? <span className="dx-tag dx-tag-muted">needs {needs}</span> : null}
        </div>
        <p className="dx-endpoint-path">
          <span className={`dx-tag ${method === "GET" ? "dx-tag-get" : "dx-tag-post"}`}>{method}</span>
          <span>{path}</span>
        </p>
      </div>
      <div className="dx-endpoint-body">{children}</div>
    </article>
  );
}

export default function PluginsPage() {
  return (
    <DocsShell
      current="/plugins"
      title="Plugins"
      dek={
        <>
          Plugins add community alerts to the map and the apps, from sources beyond the official feeds. Browse
          and install them in a minute, or build your own on Flare, the open protocol behind them.
        </>
      }
      actions={
        <>
          <Link href="/marketplace" prefetch={false} className="dx-btn dx-btn-primary">
            Browse plugins <ArrowRight aria-hidden="true" className="pg-btn-arrow" />
          </Link>
          <a href="#install" className="dx-btn dx-btn-ghost">
            How to install
          </a>
          <a href="#start" className="dx-textlink">
            Build a plugin
          </a>
        </>
      }
      facts={[
        { value: String(CAPABILITIES.length), label: "capabilities" },
        { value: String(KIND_COUNT), label: "alert kinds" },
        { value: "3", label: "trust levels" },
      ]}
      toc={TOC}
    >
      <Section id="install" title="Install a plugin">
        <div className="dx-prose dx-lead">
          <p>
            Plugins are free. Pick one in the{" "}
            <Link href="/marketplace" prefetch={false} className="dx-link">
              marketplace
            </Link>
            , install it, and decide whether it may alert you.
          </p>
        </div>
        <InstallFlow />
      </Section>

      <Section id="ways" title="Three trust levels">
        <div className="dx-prose dx-lead">
          <p>
            Every plugin is shown as one of three levels, so you can always see who is behind an alert. The
            level comes from the plugin&apos;s manifest and travels on every marker as <C>tier</C>. Official
            agency data is not a plugin and always outranks all three.
          </p>
        </div>
        <div className="pg-tiers">
          {TIERS.map((t) => (
            <article key={t.id} className="pg-tier" data-tier={t.id} aria-labelledby={`tier-${t.id}`}>
              <div className="pg-tier-head">
                <span className="pg-tier-icon">
                  <t.icon aria-hidden="true" />
                </span>
                <div>
                  <h3 id={`tier-${t.id}`}>{t.name}</h3>
                  <p className="pg-tier-meta">{t.meta}</p>
                </div>
              </div>
              <p className="pg-tier-body">{t.body}</p>
              <ul className="pg-tier-rows">
                {t.rows.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </Section>

      <Section id="catalog" title="Public catalog">
        <div className="dx-prose dx-lead">
          <p>
            The public plugins the map and the apps read right now. CommuteScout&apos;s own community reports
            (the Report button on the map and in the apps) are a source like any other, marked as community
            rather than official. To install one, open it in the{" "}
            <Link href="/marketplace" prefetch={false} className="dx-link">
              marketplace
            </Link>
            .
          </p>
        </div>
        <PluginCatalog />
      </Section>

      <div className="pg-part">
        <span className="pg-part-k">For builders</span>
        <p>
          A plugin is a small HTTPS server that the map and the apps read. Everything below is the Flare protocol,
          version 1.
        </p>
      </div>

      <Section id="what" title="A plugin says what it can do">
        <div className="dx-prose dx-lead">
          <p>
            A plugin declares what it supports in its handshake, and the apps only ask for what it declared.
            Five capabilities cover what a community alert network or a camera list needs.
          </p>
        </div>
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">Plugin capabilities</caption>
            <thead>
              <tr>
                <th scope="col">Capability</th>
                <th scope="col">What it means</th>
              </tr>
            </thead>
            <tbody>
              {CAPABILITIES.map(([name, what, req]) => (
                <tr key={name}>
                  <th scope="row">
                    <code>{name}</code> {req ? <span className="dx-req">required</span> : null}
                  </th>
                  <td data-label="What it means">{what}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="topology" title="Who talks to whom">
        <div className="dx-prose dx-lead">
          <p>A plugin is either listed, so CommuteScout reads it for everyone, or private to your own app.</p>
        </div>
        <DocFigure name="plugin-flow" />
        <div className="dx-cards">
          <div className="dx-card dx-card--accent">
            <h3>Mediated</h3>
            <p className="dx-card-meta">public and unlisted plugins</p>
            <p>
              CommuteScout reads the plugin, checks every answer, and shows the alerts on the map and in the
              apps. Reports and confirmations are passed on under CommuteScout&apos;s name. The plugin never
              sees who you are or exactly where you are.
            </p>
          </div>
          <div className="dx-card dx-card--plain">
            <h3>Direct</h3>
            <p className="dx-card-meta">private plugins only</p>
            <p>
              Your app calls the plugin itself. It is something you run for your own devices. The app sends
              the center of an area, never your exact position, and no account details. The plugin can ask
              for its own bearer token.
            </p>
          </div>
        </div>
      </Section>

      <Section id="start" title="Build one from the example">
        <div className="dx-prose dx-lead">
          <p>
            The example plugin is one file with every endpoint, an in-memory store and a passing conformance
            check. Start there, replace the store with your data, and keep the HTTP layer.
          </p>
        </div>
        <CodeBlock code={START} lang="bash" title="Clone, run, check" />
        <ol className="dx-rules dx-rules--compact">
          <li>
            <span>
              Set <C>FLARE_TOKEN</C> to require a bearer token on every call but the handshake (what a private
              plugin does), and <C>FLARE_ID</C>, <C>FLARE_NAME</C> and <C>FLARE_CONTACT</C> to name it.
            </span>
          </li>
          <li>
            <span>
              To use it privately, deploy it behind HTTPS, open the app, choose Tools, then Community sources,
              and add its URL. The app runs the handshake and starts reading alerts around where you are
              looking.
            </span>
          </li>
          <li>
            <span>
              The full example lives in{" "}
              <a
                href="https://github.com/nicglazkov/commutescout/tree/main/examples/flare-plugin"
                className="dx-link"
              >
                examples/flare-plugin
              </a>{" "}
              on GitHub.
            </span>
          </li>
        </ol>
      </Section>

      <Section id="endpoints" title="Endpoints">
        <div className="dx-prose dx-lead">
          <p>
            All paths are relative to the plugin&apos;s <C>base</C>, which must be <C>https://</C>. Every
            response is <C>application/json; charset=utf-8</C>. Every request carries{" "}
            <C>Accept: application/json</C> and a <C>User-Agent</C> naming the caller. Positions are decimal
            degrees (WGS 84), distances are meters, times are ISO 8601 with an offset.
          </p>
        </div>

        <Endpoint id="ep-handshake" method="GET" path="/flare/v1/handshake">
          <div className="dx-prose">
            <p>
              Who the plugin is and what it can do. Callers cache it for an hour. <C>auth</C> is <C>none</C>,
              or <C>bearer</C> when the plugin wants a token on every other call. <C>coverage.bbox</C> is{" "}
              <C>[south, west, north, east]</C>. Callers never ask outside it. <C>refresh_s</C> is the polling
              hint. Callers honor it and never poll more often than every 15 seconds.
            </p>
          </div>
          <CodeBlock code={HANDSHAKE} lang="json" title="200 response" />
        </Endpoint>

        <Endpoint id="ep-alerts" method="GET" path="/flare/v1/alerts">
          <div className="dx-prose">
            <p>
              Alerts within <C>r</C> meters of the point, <C>r</C> at most 100000. The point is the center
              of an area, never a user&apos;s exact position. <C>ttl_s</C> is how long the caller may cache
              the response.
            </p>
          </div>
          <CodeBlock code={ALERTS} lang="http" title="Request and response" />
        </Endpoint>

        <Endpoint id="ep-report" method="POST" path="/flare/v1/report" needs="report">
          <div className="dx-prose">
            <p>
              A new report from a user. <C>reporter</C> is a stable pseudonym, different for each plugin. It
              never identifies the person, but lets the plugin tell reporters apart.
            </p>
          </div>
          <CodeBlock code={REPORT} lang="json" title="Request body" />
          <CodeBlock code={REPORT_REPLIES} lang="http" title="Replies" />
        </Endpoint>

        <Endpoint id="ep-confirm" method="POST" path="/flare/v1/confirm" needs="confirm">
          <div className="dx-prose">
            <p>
              <C>vote</C> is <C>up</C> (still there) or <C>gone</C> (not there). The reply is <C>200</C> with
              the updated alert, or <C>404</C> when the alert is unknown.
            </p>
          </div>
          <CodeBlock code={CONFIRM} lang="json" title="Request body" />
        </Endpoint>

        <Endpoint id="ep-snapshot" method="GET" path="/flare/v1/snapshot" needs="snapshot">
          <div className="dx-prose">
            <p>
              Every alert the plugin has, in one response: the same shape as <C>alerts</C>, with up to 20,000
              records and 16 MB. It exists for{" "}
              <a href="#shared" className="dx-link">
                shared data
              </a>
              : fixed things that are the same for everyone, such as enforcement cameras.
            </p>
          </div>
          <CodeBlock code={SNAPSHOT} lang="http" title="Request and response" />
        </Endpoint>

        <h3 id="ep-errors" className="dx-mt-36">
          Errors
        </h3>
        <div className="dx-prose dx-mt-8">
          <p>The same envelope CommuteScout&apos;s API uses.</p>
        </div>
        <CodeBlock code={ERROR_ENVELOPE} lang="json" title="Error body" />
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">Flare error codes</caption>
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              {ERROR_CODES.map(([c, when]) => (
                <tr key={c}>
                  <th scope="row">
                    <code>{c}</code>
                  </th>
                  <td data-label="When">{when}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="kinds" title="Alert kinds">
        <div className="dx-prose dx-lead">
          <p>
            Every alert carries one <C>kind</C> from this list, the union of what community alert networks,
            radar communities and the state feeds distinguish. A plugin may use any subset.
          </p>
        </div>
        <ul className="dx-chips">
          {KIND_GROUPS.map(([group, kinds]) => (
            <li key={group} className="pg-kind" data-tone={KIND_TONE[group] ?? "other"}>
              <span>{group}</span>
              <ul>
                {kinds.map((k) => (
                  <li key={k}>{k}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="record" title="Alert record">
        <CodeBlock code={RECORD} lang="json" title="One alert" />
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">Alert record fields</caption>
            <thead>
              <tr>
                <th scope="col">Field</th>
                <th scope="col">Required</th>
                <th scope="col">Meaning</th>
              </tr>
            </thead>
            <tbody>
              {RECORD_FIELDS.map(([f, req, meaning]) => (
                <tr key={f}>
                  <th scope="row">
                    <code>{f}</code>
                  </th>
                  <td>
                    {req ? <span className="dx-req">required</span> : <span className="dx-opt">optional</span>}
                  </td>
                  <td data-label="Meaning">{meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="dx-small dx-mt-16">
          A response is capped at 500 alerts and 1 MB. A plugin that has more should return the nearest 500.
        </p>
      </Section>

      <Section id="manifest" title="Manifest and trust">
        <div className="dx-prose dx-lead">
          <p>
            What a plugin looks like in the catalog and in the apps&apos; sources list. <C>visibility</C> is{" "}
            <C>public</C> (listed, always mediated), <C>unlisted</C> (mediated, reachable by id) or{" "}
            <C>private</C> (direct, added by URL). <C>trust</C> is <C>official</C>,{" "}
            <C>verified</C>, <C>community</C> or <C>private</C>, and decides which tier the plugin is shown as.
          </p>
        </div>
        <CodeBlock code={MANIFEST} lang="json" title="Manifest" />
      </Section>

      <Section id="shared" title="Shared data">
        <div className="dx-prose dx-lead">
          <p>
            Most plugin alerts exist because a person was somewhere: a report of police is also a report of
            where the reporter was. So CommuteScout serves a plugin&apos;s alerts only in a small circle around
            the person asking, and a map zoomed out to a region shows none.
          </p>
          <p>
            Some data is not like that. A fixed camera is the same fact for everyone and says nothing about
            anybody. A plugin whose alerts are all of that kind can be marked <strong>shared</strong> in the
            catalog. Its alerts are read whole through <C>snapshot</C> and shown across the map at any zoom.
          </p>
        </div>
        <Callout>
          <C>shared</C> is set by CommuteScout on the catalog entry, never by the plugin: it is a statement
          about privacy that a plugin cannot make about itself. The catalog row carries <C>shared: true</C> so
          clients can tell. A plugin that is not shared may still offer <C>snapshot</C>, but it is not used.
        </Callout>
      </Section>

      <Section id="rules" title="Rules">
        <h3 className="dx-mt-8">For CommuteScout and its apps</h3>
        <ol className="dx-rules dx-rules--compact">
          {CALLER_RULES.map((r) => (
            <li key={r}>
              <span>{r}</span>
            </li>
          ))}
        </ol>
        <h3 className="dx-mt-36">For plugins</h3>
        <ol className="dx-rules dx-rules--compact">
          {PLUGIN_RULES.map((r) => (
            <li key={r}>
              <span>{r}</span>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="conformance" title="Conformance">
        <div className="dx-prose dx-lead">
          <p>
            One command runs the suite against a live plugin: handshake shape, an alerts call inside the
            coverage box, every alert validated against this page, the caps, and, when declared, a report and
            a confirm round trip with a clearly marked test record. The backend and the apps accept exactly
            what the check accepts.
          </p>
        </div>
        <CodeBlock code="python -m ca_roads.flare check https://your-plugin.example" lang="bash" title="Check a plugin" />
      </Section>

      <Section id="listing" title="Get listed">
        <div className="dx-prose dx-lead">
          <p>
            To be listed publicly, deploy behind HTTPS, pass the conformance check, and send the manifest
            through the{" "}
            <Link href="/contact" prefetch={false} className="dx-link">
              contact page
            </Link>
            . Listed plugins carry their attribution on every marker, and community sources are always drawn
            as community, never as official data.
          </p>
          <p>
            The specification is versioned in the repository at{" "}
            <a href="https://github.com/nicglazkov/commutescout/blob/main/docs/flare.md" className="dx-link">
              docs/flare.md
            </a>
            . This page follows it. The rest of the API is in the{" "}
            <Link href="/developers" prefetch={false} className="dx-link">
              REST API reference
            </Link>
            .
          </p>
        </div>
      </Section>

      <Section id="roadmap" title="Roadmap">
        <ul className="dx-list">
          <li>
            Plugin ideas on the list: aircraft enforcement (ADS-B), license plate readers, air quality, EV
            charging, and radar detector integration.
          </li>
          <li>Plugin choices that follow your account on the web, as they already do between the apps.</li>
        </ul>
      </Section>
    </DocsShell>
  );
}
