import type { Metadata } from "next";
import Link from "next/link";
import { PluginCatalog } from "@/components/plugin-catalog";

// The standalone plugins section: what Flare is, how a plugin is run
// (private, unlisted or public), the full protocol, the rules, the
// conformance check, and the live public catalog. Source of truth for
// every factual claim is docs/flare.md (the specification, version 1);
// this page restyles that document rather than rewording it. The apps'
// Sources screens and the developers page link here.
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

const SECTIONS = [
  { id: "what", label: "What a plugin is" },
  { id: "ways", label: "Private, unlisted, public" },
  { id: "catalog", label: "Public catalog" },
  { id: "start", label: "Run one in five minutes" },
  { id: "endpoints", label: "Endpoints" },
  { id: "kinds", label: "Alert kinds" },
  { id: "record", label: "Alert record" },
  { id: "manifest", label: "Manifest and trust" },
  { id: "rules", label: "Rules" },
  { id: "conformance", label: "Conformance" },
  { id: "listing", label: "Get listed" },
];

const CAPABILITIES = [
  ["alerts", "Serve alerts near a point. Required."],
  ["report", "Accept a new report from a user: police, crash, hazard, and the rest."],
  ["confirm", "Accept a \"still there\" or \"not there\" vote on an alert."],
  ["notify", "Mark alerts the apps should announce out loud, not just draw."],
];

const KINDS = [
  "POLICE_VISIBLE", "POLICE_HIDING", "POLICE_OTHER",
  "CRASH_MINOR", "CRASH_MAJOR",
  "HAZARD_ON_ROAD", "HAZARD_OBJECT", "HAZARD_POTHOLE", "HAZARD_ANIMAL", "HAZARD_CONSTRUCTION",
  "HAZARD_SHOULDER", "HAZARD_SHOULDER_CAR", "HAZARD_SHOULDER_ANIMAL",
  "WEATHER_FLOOD", "WEATHER_FOG", "WEATHER_ICE", "WEATHER_HAIL", "WEATHER_SNOW",
  "ROAD_CLOSED", "LANE_CLOSED", "RAMP_CLOSED",
  "JAM_MODERATE", "JAM_HEAVY", "JAM_STANDSTILL",
  "CHAINS_REQUIRED", "CHAINS_NOT_REQUIRED",
  "CAMERA_SPEED", "CAMERA_RED_LIGHT", "CAMERA_ISSUE",
  "MAP_ISSUE", "OTHER",
];

const HANDSHAKE = `GET /flare/v1/handshake

{
  "protocol": "flare/1",
  "id": "sabreplus",
  "name": "SABRE Plus (CHP + Waze)",
  "version": "2.1.0",
  "capabilities": {"alerts": true, "report": true, "confirm": true, "notify": true},
  "kinds": ["POLICE_VISIBLE", "POLICE_HIDING", "CRASH_MAJOR", "HAZARD_ON_ROAD"],
  "coverage": {"bbox": [32.5, -124.5, 42.0, -114.1]},
  "refresh_s": 60,
  "attribution": {"name": "SABRE Plus", "url": "https://example.com"},
  "contact": "mailto:owner@example.com",
  "auth": "none"
}`;

const ALERTS = `GET /flare/v1/alerts?lat=37.34&lon=-121.88&r=50000

{"alerts": [ ...alert records... ], "ttl_s": 60, "as_of": "2026-09-16T18:30:00-07:00"}`;

const REPORT = `POST /flare/v1/report

{
  "kind": "HAZARD_ON_ROAD",
  "lat": 37.34, "lon": -121.88,
  "heading_deg": 270,
  "ts": "2026-09-16T18:40:00-07:00",
  "description": "Ladder in the number 2 lane",
  "reporter": "r:9d2c8f...",
  "client": "commutescout-ios/1.0"
}

201 {"id": "...", "alert": {...}}     accepted
202 {"queued": true}                 the plugin will decide later
422 {"error": {...}}                 refused, for example too far from a road`;

const CONFIRM = `POST /flare/v1/confirm

{"alert_id": "sabreplus:2026-09-16:8f3a", "vote": "up", "ts": "...", "reporter": "r:9d2c8f..."}

200 the updated alert, or 404 when the alert is unknown`;

const RECORD = `{
  "id": "sabreplus:2026-09-16:8f3a",
  "kind": "POLICE_VISIBLE",
  "lat": 37.3382,
  "lon": -121.8863,
  "heading_deg": 270,
  "road_names": ["I-280 N"],
  "description": "CHP on the right shoulder past Meridian",
  "report_ts": "2026-09-16T18:04:11-07:00",
  "confirm_ts": "2026-09-16T18:21:02-07:00",
  "n_confirmations": 3,
  "reliability": 0.8,
  "ttl_s": 1800,
  "notify": true,
  "geometry": {"type": "LineString", "coordinates": [[-121.89, 37.34], [-121.87, 37.35]]},
  "source_url": "https://example.com/alerts/8f3a",
  "extra": {"unit": "CHP 42"}
}`;

const RECORD_FIELDS: [string, string, string][] = [
  ["id", "yes", "Stable within the plugin. Confirmations and updates refer to it."],
  ["kind", "yes", "One of the kinds above. Unknown kinds are dropped."],
  ["lat, lon", "yes", "Where the alert is. For a stretch, the start."],
  ["heading_deg", "no", "Direction of travel it applies to, 0 to 359. Omit for both directions."],
  ["road_names", "no", "Road names as signed, most specific first."],
  ["description", "no", "One sentence for a person. At most 200 characters."],
  ["report_ts", "yes", "When it was first reported."],
  ["confirm_ts", "no", "When it was last confirmed."],
  ["n_confirmations", "no", "Count of confirmations, 0 if none."],
  ["reliability", "no", "0 to 1, the plugin's own confidence. Default 0.5."],
  ["ttl_s", "yes", "Seconds from report_ts (or confirm_ts when present) after which the alert is stale. At most 86400."],
  ["notify", "no", "The app should announce it (voice, push) when the driver is approaching. Needs the notify capability."],
  ["geometry", "no", "GeoJSON Point or LineString when the alert covers a stretch. At most 500 points."],
  ["source_url", "no", "Where a person can read more."],
  ["extra", "no", "Anything else, at most 2 KB, shown in the details pane as key: value."],
];

const MANIFEST = `{
  "id": "sabreplus",
  "name": "SABRE Plus (CHP + Waze)",
  "base": "https://plugins.example.com",
  "protocol": "flare/1",
  "visibility": "public",
  "trust": "community",
  "attribution": {"name": "SABRE Plus", "url": "https://example.com"},
  "signature": "<JWS by CommuteScout, verified entries only>"
}`;

const ERRORS = `{"error": {"code": "outside_coverage", "message": "...", "hint": "..."}}

bad_request  unauthorized  outside_coverage  too_far_from_road
rate_limited (with Retry-After)  unknown_alert  unavailable`;

const CALLER_RULES = [
  "Never send a user's exact position to a plugin. Mediated: grid-cell centers. Direct: the snapped tile center.",
  "Never send an account identifier; reporter is a per-plugin pseudonym.",
  "Honor refresh_s, ttl_s, coverage.bbox and Retry-After.",
  "Drop alerts with unknown kind, no ttl_s, or past their ttl_s.",
  "Cap what one plugin can show: 500 alerts per response, 50 per grid cell, 1 MB per response; a plugin over the caps is trimmed, not refused.",
  "Official agency data always outranks plugin alerts on the same spot.",
];

const PLUGIN_RULES = [
  "Serve over HTTPS with a valid certificate. Answer the handshake without authentication.",
  "Keep id stable for the life of an alert; reuse means an update.",
  "Set ttl_s honestly; stale alerts are the fastest way to lose trust.",
  "Do not log the callers' addresses beyond what abuse control needs.",
  "Say who you are: attribution and contact in the handshake.",
];

function code(text: string) {
  return (
    <code className="rounded bg-cs-ink/5 px-1.5 py-0.5 text-[0.85em] text-cs-ink">{text}</code>
  );
}

function Block({ text }: { text: string }) {
  return (
    <pre className="mt-4 overflow-x-auto rounded-2xl bg-cs-navy p-5 text-[13px] leading-relaxed text-white/90">
      <code>{text}</code>
    </pre>
  );
}

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="scroll-mt-24 text-2xl font-semibold tracking-tight text-cs-ink md:text-3xl">
      {children}
    </h2>
  );
}

export default function PluginsPage() {
  return (
    <>
      <section className="bg-cs-navy py-16 text-white md:py-24">
        <div className="mx-auto max-w-5xl px-6">
          <p className="text-sm font-medium uppercase tracking-wider text-white/60">Flare, version 1</p>
          <h1 className="mt-3 text-balance text-4xl font-semibold tracking-tight md:text-5xl">
            Plugins: your own road alerts, on the map and in the apps
          </h1>
          <p className="mt-5 max-w-2xl text-balance text-lg text-white/75">
            Flare is the open protocol CommuteScout uses to talk to third-party alert sources.
            A plugin is a small HTTPS server, not an app: it answers a handful of requests, so
            it works the same for the web map, the iOS app, the Android app, and anything else
            that speaks the protocol. Run one for yourself, for a group, or for everyone.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#start" className="rounded-full bg-cs-sky px-5 py-2.5 text-sm font-semibold text-white hover:bg-cs-sky/90">
              Run one in five minutes
            </a>
            <a href="#endpoints" className="rounded-full border border-white/30 px-5 py-2.5 text-sm font-semibold text-white hover:bg-white/10">
              Read the protocol
            </a>
          </div>
          <nav aria-label="On this page" className="mt-10 flex flex-wrap gap-x-5 gap-y-2 text-sm text-white/70">
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`} className="hover:text-white">
                {s.label}
              </a>
            ))}
          </nav>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="what">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="what">What a plugin is</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            A plugin declares what it supports in its handshake, and the apps only ask for what
            it declared. Four capabilities cover everything a source like Waze or a radar
            community does.
          </p>
          <dl className="mt-6 grid gap-4 sm:grid-cols-2">
            {CAPABILITIES.map(([name, what]) => (
              <div key={name} className="rounded-2xl border border-cs-ink/10 bg-white p-5">
                <dt className="font-mono text-sm font-semibold text-cs-ink">{name}</dt>
                <dd className="text-cs-ink/70 mt-1 text-sm">{what}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="ways">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="ways">Private, unlisted, public</H2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-cs-ink/10 bg-white p-5">
              <h3 className="font-semibold text-cs-ink">Private</h3>
              <p className="text-cs-ink/70 mt-2 text-sm">
                Something you run on your own network for your own devices. The apps call it
                directly (add its URL under Sources), send only a snapped map tile and no
                account identifier, and can present your own bearer token. Nothing leaves your
                own path, so it may show anything, including personal data.
              </p>
            </div>
            <div className="rounded-2xl border border-cs-ink/10 bg-white p-5">
              <h3 className="font-semibold text-cs-ink">Unlisted</h3>
              <p className="text-cs-ink/70 mt-2 text-sm">
                Mediated by CommuteScout but not in the catalog: reachable by id, for a group
                that knows it exists. The backend polls it, validates and caps what comes back,
                and forwards reports under CommuteScout&apos;s own identity.
              </p>
            </div>
            <div className="rounded-2xl border border-cs-ink/10 bg-white p-5">
              <h3 className="font-semibold text-cs-ink">Public</h3>
              <p className="text-cs-ink/70 mt-2 text-sm">
                Listed in the catalog and drawn for everyone, always mediated. The plugin never
                sees a user, a device, an address or an exact position; abuse control is
                CommuteScout&apos;s. Passes the conformance check on every release.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="catalog">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="catalog">Public catalog</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            The public plugins the map and the apps read right now. CommuteScout&apos;s own
            community reports (the Report button on the map and in the apps) are a source like
            any other, marked as community rather than official.
          </p>
          <PluginCatalog />
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="start">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="start">Run one in five minutes</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            The example plugin is one file with every endpoint, an in-memory store and a passing
            conformance check. Start there, replace the store with your data, and keep the HTTP
            layer.
          </p>
          <Block text={"git clone https://github.com/nicglazkov/commutescout\ncd commutescout/examples/flare-plugin\npip install starlette uvicorn && python server.py\npython -m ca_roads.flare check http://127.0.0.1:8300"} />
          <ul className="text-cs-ink/70 mt-4 space-y-2 text-sm">
            <li>
              Set {code("FLARE_TOKEN")} to require a bearer token on every call but the
              handshake (what a private plugin does), and {code("FLARE_ID")},{" "}
              {code("FLARE_NAME")}, {code("FLARE_CONTACT")} to name it.
            </li>
            <li>
              To use it privately: deploy it behind HTTPS, open the app, Tools, Community
              sources, and add its URL. The app runs the handshake and starts reading alerts
              around where you are looking.
            </li>
            <li>
              The full example lives in{" "}
              <a
                href="https://github.com/nicglazkov/commutescout/tree/main/examples/flare-plugin"
                className="text-cs-sky hover:underline"
              >
                examples/flare-plugin
              </a>{" "}
              on GitHub.
            </li>
          </ul>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="endpoints">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="endpoints">Endpoints</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            All paths are relative to the plugin&apos;s {code("base")}, which must be{" "}
            {code("https://")}. Every response is {code("application/json; charset=utf-8")}.
            Every request carries {code("Accept: application/json")} and a {code("User-Agent")}{" "}
            naming the caller. Positions are decimal degrees (WGS 84), distances are meters,
            times are ISO 8601 with an offset.
          </p>
          <h3 className="mt-8 font-semibold text-cs-ink">Handshake</h3>
          <p className="text-cs-ink/70 mt-2 text-sm">
            Who the plugin is and what it can do. Cached by callers for an hour. {code("auth")}{" "}
            is {code("none")}, or {code("bearer")} when the plugin wants a token on every other
            call. {code("coverage.bbox")} is {code("[south, west, north, east]")}; callers
            never ask outside it. {code("refresh_s")} is the polling hint; callers honor it and
            never poll faster than 15 seconds.
          </p>
          <Block text={HANDSHAKE} />
          <h3 className="mt-8 font-semibold text-cs-ink">Alerts</h3>
          <p className="text-cs-ink/70 mt-2 text-sm">
            Alerts within {code("r")} meters of the point, {code("r")} at most 100000. Mediated
            callers pass grid-cell centers; direct callers pass the snapped tile center, never
            the raw position. {code("ttl_s")} is how long the caller may cache the response.
          </p>
          <Block text={ALERTS} />
          <h3 className="mt-8 font-semibold text-cs-ink">Report</h3>
          <p className="text-cs-ink/70 mt-2 text-sm">
            A new report from a user; needs the {code("report")} capability. {code("reporter")}{" "}
            is an opaque, per-plugin, stable pseudonym derived from the account with a keyed
            hash: it never identifies the person, and the plugin can still rate-limit and score
            a reporter.
          </p>
          <Block text={REPORT} />
          <h3 className="mt-8 font-semibold text-cs-ink">Confirm</h3>
          <p className="text-cs-ink/70 mt-2 text-sm">
            {code("vote")} is {code("up")} (still there) or {code("gone")} (not there).
          </p>
          <Block text={CONFIRM} />
          <h3 className="mt-8 font-semibold text-cs-ink">Errors</h3>
          <p className="text-cs-ink/70 mt-2 text-sm">
            The same envelope CommuteScout&apos;s API uses. Unknown codes are treated as{" "}
            {code("bad_request")}.
          </p>
          <Block text={ERRORS} />
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="kinds">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="kinds">Alert kinds</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            Every alert carries one {code("kind")} from this list, the union of what Waze,
            radar communities and the state feeds distinguish. A plugin may use any subset.
          </p>
          <ul className="mt-6 flex flex-wrap gap-2">
            {KINDS.map((k) => (
              <li key={k} className="rounded-full border border-cs-ink/10 bg-white px-3 py-1 font-mono text-xs text-cs-ink">
                {k}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="record">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="record">Alert record</H2>
          <Block text={RECORD} />
          <div className="mt-6 overflow-x-auto rounded-2xl border border-cs-ink/10">
            <table className="w-full text-sm">
              <thead className="bg-cs-bg text-left text-cs-ink/70">
                <tr>
                  <th className="px-4 py-2 font-medium">Field</th>
                  <th className="px-4 py-2 font-medium">Required</th>
                  <th className="px-4 py-2 font-medium">Meaning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cs-ink/10 bg-white">
                {RECORD_FIELDS.map(([f, req, meaning]) => (
                  <tr key={f}>
                    <td className="px-4 py-2 font-mono text-xs text-cs-ink">{f}</td>
                    <td className="px-4 py-2 text-cs-ink/70">{req}</td>
                    <td className="px-4 py-2 text-cs-ink/70">{meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-cs-ink/70 mt-4 text-sm">
            A response is capped at 500 alerts and 1 MB. A plugin that has more should return
            the nearest 500.
          </p>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="manifest">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="manifest">Manifest and trust</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            What a plugin looks like in the catalog and in the apps&apos; sources list.{" "}
            {code("visibility")} is {code("public")} (listed, always mediated),{" "}
            {code("unlisted")} (mediated, reachable by id), or {code("private")} (direct; the
            user typed the URL). {code("trust")} is {code("official")}, {code("verified")},{" "}
            {code("community")} or {code("private")}; it decides whether {code("notify")} alerts
            may speak: official and verified yes, community map-only until promoted, private
            the user&apos;s choice.
          </p>
          <Block text={MANIFEST} />
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="rules">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="rules">Rules</H2>
          <h3 className="mt-6 font-semibold text-cs-ink">For callers (the map, the apps, the backend)</h3>
          <ul className="text-cs-ink/70 mt-3 list-disc space-y-2 pl-5 text-sm">
            {CALLER_RULES.map((r) => <li key={r}>{r}</li>)}
          </ul>
          <h3 className="mt-8 font-semibold text-cs-ink">For plugins</h3>
          <ul className="text-cs-ink/70 mt-3 list-disc space-y-2 pl-5 text-sm">
            {PLUGIN_RULES.map((r) => <li key={r}>{r}</li>)}
          </ul>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="conformance">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="conformance">Conformance</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            One command runs the suite against a live plugin: handshake shape, an alerts call
            inside the coverage box, every alert validated against this page, the caps, and,
            when declared, a report and a confirm round trip with a clearly marked test record.
            The backend and the apps accept exactly what the check accepts.
          </p>
          <Block text="python -m ca_roads.flare check https://your-plugin.example" />
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="listing">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="listing">Get listed</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            To be listed publicly, deploy behind HTTPS, pass the conformance check, and send
            the manifest through the{" "}
            <Link href="/contact" prefetch={false} className="text-cs-sky hover:underline">
              contact page
            </Link>
            . Listed plugins carry their attribution on every marker, and community sources are
            always drawn as community, never as official data. The specification itself is
            versioned in the repository at{" "}
            <a
              href="https://github.com/nicglazkov/commutescout/blob/main/docs/flare.md"
              className="text-cs-sky hover:underline"
            >
              docs/flare.md
            </a>
            ; this page follows it. The rest of the API is on the{" "}
            <Link href="/developers" prefetch={false} className="text-cs-sky hover:underline">
              developers page
            </Link>
            .
          </p>
        </div>
      </section>
    </>
  );
}
