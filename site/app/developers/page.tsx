import type { Metadata } from "next";
import Link from "next/link";
import { CopyField } from "@/components/copy-field";
import reference from "@/lib/api-reference.json";

// The developer documentation: the REST API in full (base URL, keys,
// limits, errors, conventions, every tool with every parameter), the
// MCP server, bulk snapshots, and what not to do. The tool reference is
// rendered from site/lib/api-reference.json, which
// scripts/gen_api_reference.py generates from the tools' own schemas;
// tests/test_api_reference.py fails when the JSON is stale, so the
// parameter list here cannot drift from the server.
export const metadata: Metadata = {
  title: "Developers - CommuteScout",
  description:
    "Use CommuteScout's live road data from your own code: a REST API with an OpenAPI document, an MCP server, keys and limits, and every tool documented parameter by parameter.",
  alternates: {
    canonical: "https://commutescout.com/developers",
  },
  openGraph: {
    title: "Developers - CommuteScout",
    description:
      "Use CommuteScout's live road data from your own code: a REST API with an OpenAPI document, an MCP server, keys and limits, and every tool documented parameter by parameter.",
    url: "https://commutescout.com/developers",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

const BASE = reference.base;
const API_ROOT = `${BASE}${reference.prefix}`;
// Link text for the OpenAPI, docs, and index links: the same URL as the
// href without the scheme, so a reader sees which host answers.
const API_ROOT_TEXT = API_ROOT.replace(/^https?:\/\//, "");
const MCP_URL = `${BASE}/mcp`;

const SECTIONS = [
  { id: "quickstart", label: "Quickstart" },
  { id: "basics", label: "Base URL and versioning" },
  { id: "keys", label: "Keys and limits" },
  { id: "responses", label: "Responses and conventions" },
  { id: "errors", label: "Errors" },
  { id: "rules", label: "What not to do" },
  { id: "tools", label: "Tool reference" },
  { id: "mcp", label: "MCP server" },
  { id: "bulk", label: "Bulk snapshots" },
  { id: "flare", label: "Flare plugins" },
  { id: "terms", label: "Attribution and terms" },
];

const CURL_QUICK = `curl "${API_ROOT}/tools/get_incidents?center=37.48,-122.14&radius_km=20"`;

const RESPONSE_SHAPE = `{
  "count": 1,
  "filters": { "highway": null, "area": null, "center": "37.48,-122.14" },
  "incidents": [
    {
      "id": "260916GG0001",
      "type": "1182-Trfc Collision-No Inj",
      "location": "Sr84 E / University Ave Onr",
      "direction_hint": "eastbound",
      "area": "Redwood City",
      "lat": 37.482, "lon": -122.14,
      "reported_at": "2026-09-16T12:00:00+00:00"
    }
  ],
  "sources": [
    { "source": "chp",
      "description": "CHP live incidents (media.chp.ca.gov, refreshes ~1/min)",
      "ok": true, "data_as_of": "2026-09-16T12:00:41+00:00" }
  ],
  "signs": [
    { "route": "US-101", "direction": "N", "near": "Redwood City",
      "county": "San Mateo", "lat": 37.49, "lon": -122.23,
      "message": "CRASH AHEAD / EXPECT DELAYS" }
  ],
  "cameras": [
    { "name": "SR-84 at University Ave", "route": "SR-84", "direction": "E",
      "near": "Redwood City", "lat": 37.48, "lon": -122.15,
      "image_url": "https://cwwp2.dot.ca.gov/.../image.jpg", "stream_url": null }
  ]
}`;

const CURL_KEYED = `curl -H "X-API-Key: cs_live_..." \\
  "${API_ROOT}/tools/check_route?from_place=Sacramento&to_place=Reno"`;

const ERROR_SHAPE = `{
  "error": {
    "code": "missing_parameter",
    "message": "check_route needs to_place.",
    "hint": "See ${API_ROOT}/docs#operation/check_route."
  }
}`;

const ERRORS = [
  ["400", "missing_parameter", "A required parameter is absent. The message names it."],
  ["400", "unknown_parameter", "A parameter the tool does not have. The hint lists the accepted names."],
  ["400", "invalid_parameter", "A value of the wrong type, for example radius_km=wide."],
  ["400", "tool_error", "The tool refused the arguments for a reason it explains."],
  ["401", "invalid_key", "The key is unknown or revoked. There is no silent fallback to keyless."],
  ["404", "unknown_tool", "No tool by that name. The index at /v1 lists them."],
  ["429", "rate_limited", "Too many requests at once. Retry-After says how long to wait."],
  ["429", "daily_limit", "The key or address has used its day. Retry-After is 3600."],
  ["502", "upstream_error", "A source feed did not answer. Retry in a minute."],
  ["503", "keys_unavailable", "Key checks are down. Retry, or call without a key."],
];

const TIERS = [
  ["No key", "Per address", "30 a minute sustained, 20 in a burst", "10,000 shared by everything behind that address"],
  ["Free key", "Per key", "30 a minute, 30 in a burst", "2,000"],
  ["Pro key", "Per key", "120 a minute, 60 in a burst", "10,000"],
];

const RULES = [
  {
    title: "Do not poll faster than the data changes.",
    body:
      "Every tool below says how often its source refreshes. Asking more often returns the same answer and spends your limit. A dashboard that re-reads incidents every 60 seconds and closures every five minutes is doing it right.",
  },
  {
    title: "Do not put a key in a web page or a mobile app.",
    body:
      "A key is a secret. Anyone who can open your app can read it and spend your limit. Call keyless from browsers (the API allows cross-origin reads) or keep the key on a server you control.",
  },
  {
    title: "Do not call the map's private endpoints.",
    body:
      "Everything under commutescout.com/api is for the site's own pages and changes without notice. The supported surface is this API, the MCP server, and the bulk snapshots below.",
  },
  {
    title: "Do not present the data as complete or official.",
    body:
      "It is a live compilation of agency feeds, each with its own delay. Show the data_as_of time next to what you display, name the source, and tell your users to verify with 511 or the state DOT before they drive. Never use it for evacuation or emergency decisions.",
  },
  {
    title: "Do not resell the raw feeds.",
    body:
      "Build on the data, do not redistribute it as a feed of your own. If your product needs the whole stream, use the bulk snapshots with attribution, or contact us.",
  },
  {
    title: "Do not share one key across products.",
    body:
      "One key per app or job. When a key leaks, revoke it in Settings; requests with it stop within a minute.",
  },
];

type Param = { name: string; required: boolean; doc: string };
type Tool = {
  name: string;
  path: string;
  title: string;
  summary: string;
  reads: string;
  refresh: string;
  caps: string;
  poll_s: number;
  example: string;
  params: Param[];
};

const TOOLS = reference.tools as Tool[];

function code(text: string) {
  return (
    <code className="bg-cs-bg text-cs-ink rounded px-1.5 py-0.5 text-[0.85em]">{text}</code>
  );
}

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2
      id={id}
      className="text-cs-ink scroll-mt-24 text-balance text-2xl font-medium tracking-tight md:text-3xl"
    >
      {children}
    </h2>
  );
}

export default function DevelopersPage() {
  return (
    <>
      <section className="bg-cs-navy text-white">
        <div className="mx-auto max-w-4xl px-6 py-16 md:py-20">
          <h1 className="text-balance text-4xl font-medium tracking-tight md:text-5xl">
            Live roads, from your own code.
          </h1>
          <p className="text-white/70 mt-4 max-w-2xl text-balance md:text-lg">
            One REST API and one MCP server over the same live data as the map:
            incidents, closures, chain controls, wildfires, cameras and message
            signs, California in the most depth and live events across every
            covered state. This page is the whole contract. Nothing here needs
            guessing.
          </p>
          <div className="mt-8 max-w-xl">
            <CopyField value={`${API_ROOT}/tools/{tool}`} />
          </div>
          <nav aria-label="On this page" className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-sm">
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`} className="text-white/70 hover:text-white">
                {s.label}
              </a>
            ))}
          </nav>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="quickstart">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="quickstart">Quickstart</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            No key, no account, no SDK. One GET returns JSON.
          </p>
          <pre className="bg-cs-navy2 mt-5 overflow-x-auto rounded-xl p-5 text-sm text-white/90">
            <code>{CURL_QUICK}</code>
          </pre>
          <p className="text-cs-ink/70 mt-5 text-balance">
            Every response carries the records you asked for, the filters the
            server understood, and a {code("sources")} list with each source&apos;s
            own {code("data_as_of")} time. Show that time to your users.
            When {code("get_incidents")}, {code("get_lane_closures")}, or{" "}
            {code("get_chain_controls")} is filtered by route or center, the
            response also carries the {code("signs")} and verified{" "}
            {code("cameras")} near the returned records, when there are any.
          </p>
          <pre className="bg-cs-navy2 mt-5 overflow-x-auto rounded-xl p-5 text-sm text-white/90">
            <code>{RESPONSE_SHAPE}</code>
          </pre>
          <p className="text-cs-ink/70 mt-5 text-balance">
            The full machine-readable contract is the OpenAPI document at{" "}
            <a href={`${API_ROOT}/openapi.json`} className="text-cs-sky hover:underline">
              {API_ROOT_TEXT}/openapi.json
            </a>
            , with a browsable reference at{" "}
            <a href={`${API_ROOT}/docs`} className="text-cs-sky hover:underline">
              {API_ROOT_TEXT}/docs
            </a>{" "}
            and an index at{" "}
            <a href={API_ROOT} className="text-cs-sky hover:underline">
              {API_ROOT_TEXT}
            </a>
            . It is generated from the tools&apos; own schemas, so it is never out of date.
          </p>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="basics">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="basics">Base URL and versioning</H2>
          <ul className="text-cs-ink/70 mt-4 space-y-3 text-balance">
            <li>
              <b className="text-cs-ink">Base URL:</b> {code(API_ROOT)}. Every tool is{" "}
              {code("GET " + reference.prefix + "/tools/{tool}")} with arguments as query
              parameters. Only GET and OPTIONS are accepted.
            </li>
            <li>
              <b className="text-cs-ink">Versioning:</b> the path carries the version.
              Changes within {code("/v1")} are additive: new fields, new parameters with
              defaults, new tools. Nothing is renamed or removed within a version. A
              breaking change would ship as {code("/v2")} with {code("/v1")} kept running.
            </li>
            <li>
              <b className="text-cs-ink">Encoding:</b> query strings are URL-encoded UTF-8;
              a place name with a space is {code("Bay%20Area")}. Responses are{" "}
              {code("application/json")}, UTF-8, uncompressed unless you send{" "}
              {code("Accept-Encoding: gzip")}.
            </li>
            <li>
              <b className="text-cs-ink">Cross-origin:</b> every {code("/v1")} response
              carries {code("Access-Control-Allow-Origin: *")} and answers preflight, so a
              browser page can call it directly. Do that keyless (see the rules below).
            </li>
            <li>
              <b className="text-cs-ink">Caching:</b> tool responses are{" "}
              {code("Cache-Control: no-store")}; cache them yourself for as long as the
              tool&apos;s refresh interval says.
            </li>
          </ul>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="keys">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="keys">Keys and limits</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            Without a key, requests are limited per network address, and everything
            behind that address shares the day. A key moves you onto your own limits.
            Every key belongs to a signed-in account: open the{" "}
            <Link href="/map" prefetch={false} className="text-cs-sky hover:underline">
              live map
            </Link>
            , choose Settings in the rail, sign in with Google or an email link, and
            create a key under API keys. The key is shown once. Send it as{" "}
            {code("X-API-Key")} or {code("Authorization: Bearer cs_live_...")}.
          </p>
          <pre className="bg-cs-navy2 mt-5 overflow-x-auto rounded-xl p-5 text-sm text-white/90">
            <code>{CURL_KEYED}</code>
          </pre>
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-cs-ink/60 border-cs-line border-b">
                <tr>
                  <th className="py-2 pr-4 font-medium">Tier</th>
                  <th className="py-2 pr-4 font-medium">Counted</th>
                  <th className="py-2 pr-4 font-medium">Rate</th>
                  <th className="py-2 font-medium">Requests per UTC day</th>
                </tr>
              </thead>
              <tbody className="text-cs-ink/80">
                {TIERS.map((row) => (
                  <tr key={row[0]} className="border-cs-line border-b">
                    <td className="py-2 pr-4 font-medium">{row[0]}</td>
                    <td className="py-2 pr-4">{row[1]}</td>
                    <td className="py-2 pr-4">{row[2]}</td>
                    <td className="py-2">{row[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="text-cs-ink/70 mt-6 space-y-3 text-balance">
            <li>
              Every keyed response carries {code("RateLimit-Limit")} and{" "}
              {code("RateLimit-Remaining")} for the day. A spent day answers 429 with{" "}
              {code("Retry-After: 3600")}; a burst answers 429 with {code("Retry-After: 2")}.
            </li>
            <li>
              Days reset at midnight UTC. Limits apply to {code("/v1")} and {code("/mcp")}{" "}
              alike.
            </li>
            <li>
              New keys are Free. Pro is switched on per key; more than Pro is a
              conversation.{" "}
              <Link href="/contact" prefetch={false} className="text-cs-sky hover:underline">
                Ask through the contact page
              </Link>{" "}
              with what you are building and the volume you expect. Nothing is billed
              yet; that comes with the Pro tier later.
            </li>
            <li>An account holds up to five active keys. Revoking a key stops it within a minute.</li>
          </ul>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="responses">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="responses">Responses and conventions</H2>
          <ul className="text-cs-ink/70 mt-4 space-y-3 text-balance">
            <li>
              <b className="text-cs-ink">Coordinates</b> are decimal degrees, WGS 84, as{" "}
              {code("lat")} and {code("lon")} fields on records. Parameters take a point
              as one string, {code("\"lat,lon\"")}, for example {code("37.48,-122.14")}.
            </li>
            <li>
              <b className="text-cs-ink">Distances</b> are kilometers unless the field
              name says otherwise ({code("miles_from_start")}, {code("size_acres")}).
              Radii are {code("radius_km")}.
            </li>
            <li>
              <b className="text-cs-ink">Timestamps</b> are ISO 8601 with an offset. Most
              are UTC; CHP&apos;s {code("reported_at")} carries the Pacific offset it was
              logged in. Parse the offset rather than assuming one.
            </li>
            <li>
              <b className="text-cs-ink">Lists</b> carry {code("count")}. A capped list also
              carries {code("total")} and {code("truncated: true")}, and a note saying so.
              Counts are exact even when the list is cut.
            </li>
            <li>
              <b className="text-cs-ink">Sources</b>: every response lists each source it
              read with {code("ok")} and {code("data_as_of")}. When a source is down the
              response still answers from the others and marks that one{" "}
              {code("ok: false")}.
            </li>
            <li>
              <b className="text-cs-ink">Notes</b>: a {code("notes")} list explains anything
              the server did on your behalf, such as clamping a radius or listing the
              corridors when a route did not match. Read it; it is meant for people.
            </li>
            <li>
              <b className="text-cs-ink">Semantic errors inside a 200</b>: a tool that
              understood the request but could not act on it (an unrecognized region, a
              malformed center) answers 200 with an {code("error")} field in the body and
              usually the accepted values next to it. Transport and parameter errors use
              the envelope below.
            </li>
          </ul>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="errors">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="errors">Errors</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            One envelope everywhere: a status code, a stable {code("code")} you can branch
            on, a {code("message")} for a log line, and a {code("hint")} for a person.
          </p>
          <pre className="bg-cs-navy2 mt-5 overflow-x-auto rounded-xl p-5 text-sm text-white/90">
            <code>{ERROR_SHAPE}</code>
          </pre>
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-cs-ink/60 border-cs-line border-b">
                <tr>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">code</th>
                  <th className="py-2 font-medium">Meaning</th>
                </tr>
              </thead>
              <tbody className="text-cs-ink/80">
                {ERRORS.map((row) => (
                  <tr key={row[1]} className="border-cs-line border-b align-top">
                    <td className="py-2 pr-4">{row[0]}</td>
                    <td className="py-2 pr-4">
                      <code className="text-cs-ink">{row[1]}</code>
                    </td>
                    <td className="py-2">{row[2]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-cs-ink/70 mt-5 text-balance">
            Retry only 429, 502 and 503, after the {code("Retry-After")} the response gives
            or one minute when it gives none, with backoff. A 400 or 401 will not fix
            itself.
          </p>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="rules">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="rules">What not to do</H2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {RULES.map((r) => (
              <div key={r.title} className="ring-cs-line bg-cs-paper rounded-xl p-5 ring-1">
                <p className="text-cs-ink font-medium">{r.title}</p>
                <p className="text-cs-ink/60 mt-2 text-sm">{r.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="tools">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="tools">Tool reference</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            Ten tools. Each one lists every parameter it accepts, what it reads, how
            fresh that is, and what it caps. The examples are complete URLs relative to{" "}
            {code(BASE)}. Optional parameters combine; leave them out for everything.
          </p>
          <div className="mt-8 space-y-10">
            {TOOLS.map((t) => (
              <article
                key={t.name}
                id={`tool-${t.name}`}
                className="ring-cs-line bg-cs-paper scroll-mt-24 rounded-xl p-6 ring-1"
              >
                <h3 className="text-cs-ink text-xl font-medium tracking-tight">{t.title}</h3>
                <code className="text-cs-ink/80 mt-1 block text-sm break-all">GET {t.path}</code>
                <p className="text-cs-ink/70 mt-3 text-balance">{t.summary}</p>
                <dl className="text-cs-ink/70 mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[7rem_1fr]">
                  <dt className="text-cs-ink font-medium">Reads</dt>
                  <dd>{t.reads}</dd>
                  <dt className="text-cs-ink font-medium">Refresh</dt>
                  <dd>{t.refresh}</dd>
                  <dt className="text-cs-ink font-medium">Poll at most</dt>
                  <dd>every {t.poll_s} seconds</dd>
                  <dt className="text-cs-ink font-medium">Limits</dt>
                  <dd>{t.caps}</dd>
                </dl>
                <h4 className="text-cs-ink mt-5 text-sm font-medium">Parameters</h4>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <tbody className="text-cs-ink/80">
                      {t.params.map((p) => (
                        <tr key={p.name} className="border-cs-line border-b align-top">
                          <td className="py-2 pr-4 whitespace-nowrap">
                            <code className="text-cs-ink">{p.name}</code>
                            {p.required ? (
                              <span className="text-cs-sky ml-2 text-xs font-medium">required</span>
                            ) : (
                              <span className="text-cs-ink/50 ml-2 text-xs">optional</span>
                            )}
                          </td>
                          <td className="py-2">{p.doc}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <h4 className="text-cs-ink mt-5 text-sm font-medium">Example</h4>
                <pre className="bg-cs-navy2 mt-2 overflow-x-auto rounded-lg p-4 text-xs text-white/90">
                  <code>{`${API_ROOT}/tools/${t.example}`}</code>
                </pre>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="mcp">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="mcp">MCP server</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            The same ten tools for Claude and any other MCP client, over streamable
            HTTP. Add it as a custom connector; no key is needed, and a key works the
            same way as on {code("/v1")} when you want your own limits.
          </p>
          <div className="mt-5 max-w-xl">
            <CopyField value={MCP_URL} />
          </div>
          <p className="text-cs-ink/70 mt-5 text-balance">
            Local stdio setup, the registry entry and the eval scorecard are on the{" "}
            <Link href="/mcp" prefetch={false} className="text-cs-sky hover:underline">
              MCP server page
            </Link>
            . The server is open source; the tool docstrings there are written for the
            model reading them and say the same things this page says.
          </p>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="bulk">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="bulk">Bulk snapshots</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            The map does not poll the API; it reads three gzip JSON snapshots the
            server publishes and the edge caches. They are public and the cheapest way
            to read everything at once. They carry the same records as the map&apos;s
            markers, so their shape follows the map, not this API, and it can change
            between releases.
          </p>
          <div className="mt-5 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-cs-ink/60 border-cs-line border-b">
                <tr>
                  <th className="py-2 pr-4 font-medium">Object</th>
                  <th className="py-2 pr-4 font-medium">Rebuilt</th>
                  <th className="py-2 font-medium">Holds</th>
                </tr>
              </thead>
              <tbody className="text-cs-ink/80">
                <tr className="border-cs-line border-b">
                  <td className="py-2 pr-4"><code>https://data.commutescout.com/live.json.gz</code></td>
                  <td className="py-2 pr-4">every 30 seconds</td>
                  <td className="py-2">incidents, closures, chain controls, wildfires, toll prices</td>
                </tr>
                <tr className="border-cs-line border-b">
                  <td className="py-2 pr-4"><code>https://data.commutescout.com/signs.json.gz</code></td>
                  <td className="py-2 pr-4">every 5 minutes</td>
                  <td className="py-2">message signs and road-weather stations</td>
                </tr>
                <tr className="border-cs-line border-b">
                  <td className="py-2 pr-4"><code>https://data.commutescout.com/cameras.json.gz</code></td>
                  <td className="py-2 pr-4">every hour</td>
                  <td className="py-2">the camera inventory</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-cs-ink/70 mt-5 text-balance">
            Fetch with {code("If-None-Match")} and honor the {code("Cache-Control")} you
            get back; the objects only change on their rebuild cadence. Attribution
            applies exactly as it does to the API.
          </p>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16" aria-labelledby="flare">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="flare">Flare plugins</H2>
          <p className="text-cs-ink/70 mt-4 text-balance">
            Flare is CommuteScout&apos;s open protocol for third-party alert sources: a
            small HTTPS contract a plugin server implements (handshake, alerts by
            radius, reports, confirmations) so that anyone can run a public or private
            source that shows on the map and in the app, with full read and write
            support.{" "}
            <Link href="/plugins" prefetch={false} className="text-cs-sky hover:underline">
              Read the plugins page
            </Link>
            , then run the conformance check against your plugin:{" "}
            {code("python -m ca_roads.flare check https://your-plugin.example")}. The
            backend and the apps accept exactly what the check accepts.
          </p>
        </div>
      </section>

      <section className="py-14 md:py-16" aria-labelledby="terms">
        <div className="mx-auto max-w-3xl px-6">
          <H2 id="terms">Attribution and terms</H2>
          <ul className="text-cs-ink/70 mt-4 space-y-3 text-balance">
            <li>
              Credit CommuteScout and the agency named in each record&apos;s{" "}
              {code("source")} wherever the data is shown. The{" "}
              <Link href="/data-sources" prefetch={false} className="text-cs-sky hover:underline">
                data sources page
              </Link>{" "}
              lists every agency and what it publishes.
            </li>
            <li>
              The data is informational and can be delayed, incomplete or wrong. Show
              the {code("data_as_of")} time, and tell people to verify with 511 or the
              state DOT before they drive.
            </li>
            <li>
              Limits are enforced and keys can be revoked. The{" "}
              <Link href="/terms" prefetch={false} className="text-cs-sky hover:underline">
                terms
              </Link>{" "}
              and{" "}
              <Link href="/privacy" prefetch={false} className="text-cs-sky hover:underline">
                privacy page
              </Link>{" "}
              apply to API use; keyed requests are logged per key (key id, tool,
              status) for metering and nothing else.
            </li>
            <li>
              Questions, a higher limit, or a feed you would like added:{" "}
              <Link href="/contact" prefetch={false} className="text-cs-sky hover:underline">
                contact
              </Link>
              .
            </li>
          </ul>
        </div>
      </section>
    </>
  );
}
