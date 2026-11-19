import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { DocsShell, Section, type TocItem } from "@/components/docs/docs-shell";
import { C, CodeBlock, CopyField } from "@/components/docs/code-block";
import { Callout } from "@/components/docs/callout";
import { DocFigure } from "@/components/docs/doc-figure";
import reference from "@/lib/api-reference.json";

// The developer documentation: the REST API in full (base URL, keys,
// limits, errors, conventions, every tool with every parameter), the
// MCP server, bulk snapshots, and what not to do. The tool reference is
// rendered from site/lib/api-reference.json, which
// scripts/gen_api_reference.py generates from the tools' own schemas;
// tests/test_api_reference.py fails when the JSON is stale, so the
// parameter list here cannot drift from the server.
//
// Limits on this page come from src/ca_roads/apikeys.py (TIERS, five keys
// per account, ten new keys a day) and src/ca_roads_mcp/ratelimit.py (the
// keyless bucket: 20 burst, 0.5 a second; the bad-key budget; Retry-After
// values). Bulk cadences come from src/ca_roads_demo/snapshot.py BUNDLES.
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
const BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));

// The same three groups the MCP server's instructions use. Every tool in
// the generated reference lands in exactly one group (checked below).
const GROUPS: { id: string; title: string; blurb: string; tools: string[] }[] = [
  {
    id: "tools-trips",
    title: "Trips, anywhere in the US",
    blurb: "Plan a drive between any two US places, pick the best time to leave, resolve an address, and read your saved places.",
    tools: ["plan_trip", "best_time_to_go", "find_place", "get_my_places"],
  },
  {
    id: "tools-place",
    title: "Around one place",
    blurb: "Live events, weather, traffic speed and history around a point, in every covered state.",
    tools: ["get_nearby_events", "get_weather", "get_traffic", "get_area_history", "get_coverage"],
  },
  {
    id: "tools-ca",
    title: "California, in depth",
    blurb: "California publishes the deepest feeds, so these tools read them directly: highway patrol logs, closures in place, chain controls, fires, cameras and message signs.",
    tools: [
      "check_route",
      "check_region",
      "get_incidents",
      "get_lane_closures",
      "get_chain_controls",
      "get_wildfires",
      "get_cameras",
      "get_road_signs",
      "rank_routes",
    ],
  },
];
const GROUPED = new Set(GROUPS.flatMap((g) => g.tools));
const UNGROUPED = TOOLS.filter((t) => !GROUPED.has(t.name));
if (UNGROUPED.length) {
  // A tool added to the server but not to a group still renders, last.
  GROUPS.push({ id: "tools-more", title: "More tools", blurb: "", tools: UNGROUPED.map((t) => t.name) });
}

const TOC: TocItem[] = [
  { id: "quickstart", label: "Quickstart" },
  { id: "basics", label: "Base URL and versioning" },
  { id: "keys", label: "Keys and limits" },
  { id: "responses", label: "Responses" },
  { id: "errors", label: "Errors" },
  { id: "rules", label: "What not to do" },
  {
    id: "tools",
    label: "Tool reference",
    children: GROUPS.flatMap((g) => g.tools).map((n) => ({ id: `tool-${n}`, label: n })),
  },
  { id: "mcp", label: "MCP server" },
  { id: "bulk", label: "Bulk snapshots" },
  { id: "flare", label: "Flare plugins" },
  { id: "terms", label: "Attribution and terms" },
];

const CURL_QUICK = `curl "${API_ROOT}/tools/get_incidents?center=LAT,LON&radius_km=20"`;

// A sample, not a record: the id keeps the real shape (date, then a
// dispatch-center code, then a sequence) with a placeholder center code.
const RESPONSE_SHAPE = `{
  "count": 1,
  "filters": { "highway": null, "area": null, "center": "LAT,LON" },
  "incidents": [
    {
      "id": "260916XX0001",
      "type": "1182-Trfc Collision-No Inj",
      "location": "ROUTE / Cross St Onr",
      "direction_hint": "eastbound",
      "area": "Dispatch area",
      "lat": LAT, "lon": LON,
      "reported_at": "2026-09-16T12:00:00+00:00"
    }
  ],
  "sources": [
    { "source": "chp",
      "description": "CHP live incidents (media.chp.ca.gov, refreshes ~1/min)",
      "ok": true, "data_as_of": "2026-09-16T12:00:41+00:00" }
  ],
  "signs": [
    { "route": "ROUTE", "direction": "N", "near": "Nearest town",
      "county": "County", "lat": LAT, "lon": LON,
      "message": "CRASH AHEAD / EXPECT DELAYS" }
  ],
  "cameras": [
    { "name": "ROUTE at Cross St", "route": "ROUTE", "direction": "E",
      "near": "Nearest town", "lat": LAT, "lon": LON,
      "image_url": "https://cwwp2.dot.ca.gov/.../image.jpg", "stream_url": null }
  ]
}`;

const CURL_KEYED = `curl -H "X-API-Key: cs_live_..." \\
  "${API_ROOT}/tools/plan_trip?origin=home&destination=work"`;

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
  ["429", "daily_limit", "The account (for a keyed request) or the address (without a key) has used its day. Retry-After is 3600."],
  ["502", "upstream_error", "A source feed did not answer. Retry in a minute."],
  ["503", "keys_unavailable", "Key checks are down. Retry, or call without a key."],
];

// [tier, counted per, sustained, burst, per UTC day]
const TIERS = [
  ["No key", "Network address", "30 a minute", "20", "10,000"],
  ["Free key", "Account, all keys together", "30 a minute", "30", "2,000"],
  ["Pro key (coming soon)", "Account, all keys together", "120 a minute", "60", "10,000"],
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

const BULK = [
  ["live.json.gz", "Every 30 seconds", "Incidents, closures, chain controls, wildfires, toll prices and plugin alerts"],
  ["signs.json.gz", "Every 5 minutes", "Message signs and road-weather stations"],
  ["cameras.json.gz", "Every hour", "The camera inventory"],
];

function statusTag(status: string) {
  const cls = status.startsWith("5") ? "dx-tag-5xx" : status.startsWith("4") ? "dx-tag-4xx" : "dx-tag-2xx";
  return <span className={`dx-tag ${cls}`}>{status}</span>;
}

function pollText(s: number) {
  if (s % 3600 === 0) return s === 3600 ? "every hour" : `every ${s / 3600} hours`;
  if (s % 60 === 0) return s === 60 ? "every minute" : `every ${s / 60} minutes`;
  return `every ${s} seconds`;
}

// Examples that read saved places need a key; show it in the command.
function exampleCommand(t: Tool) {
  const url = `${API_ROOT}/tools/${t.example}`;
  const needsKey = t.name === "get_my_places" || /=(home|work)\b/.test(t.example);
  return needsKey ? `curl -H "X-API-Key: cs_live_..." \\\n  "${url}"` : `curl "${url}"`;
}

function ToolEntry({ t }: { t: Tool }) {
  return (
    <article id={`tool-${t.name}`} className="dx-endpoint" aria-labelledby={`tool-${t.name}-h`}>
      <div className="dx-endpoint-head">
        <div className="dx-endpoint-title">
          <h4 id={`tool-${t.name}-h`} className="dx-endpoint-name">
            {t.name}
          </h4>
          <span className="dx-tag dx-tag-muted">{t.title}</span>
        </div>
        <p className="dx-endpoint-path">
          <span className="dx-tag dx-tag-get">GET</span>
          <span>{t.path}</span>
        </p>
        <p className="dx-endpoint-sum">{t.summary}</p>
      </div>
      <div className="dx-endpoint-body">
        <dl className="dx-meta">
          <dt>Reads</dt>
          <dd>{t.reads}</dd>
          <dt>Refresh</dt>
          <dd>{t.refresh}</dd>
          <dt>Poll at most</dt>
          <dd>{pollText(t.poll_s)}</dd>
          <dt>Limits</dt>
          <dd>{t.caps}</dd>
        </dl>
        <h5 className="dx-subhead dx-kicker dx-mb-0">
          {t.params.length ? "Query parameters" : "Parameters"}
        </h5>
        {t.params.length ? (
          <ul className="dx-params">
            {t.params.map((p) => (
              <li key={p.name}>
                <div className="dx-param-name">
                  <code>{p.name}</code>
                  {p.required ? <span className="dx-req">required</span> : <span className="dx-opt">optional</span>}
                </div>
                <p className="dx-param-doc">{p.doc}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="dx-param-doc">None.</p>
        )}
        <CodeBlock code={exampleCommand(t)} lang="bash" title="Example" />
      </div>
    </article>
  );
}

export default function DevelopersPage() {
  return (
    <DocsShell
      current="/developers"
      eyebrow="REST API · v1"
      title="Live roads, from your own code."
      dek={
        <>
          One REST API and one MCP server over the same live data as the map: trip planning and the
          best time to leave anywhere in the US, plus incidents, closures, chain controls, wildfires,
          cameras, message signs, traffic, weather and event history. Every tool is one GET. No key,
          account or SDK needed to start.
        </>
      }
      actions={
        <>
          <CopyField method="GET" value={`${API_ROOT}/tools/{tool}`} label="Tool URL pattern" />
          <a href={`${API_ROOT}/docs`} className="dx-textlink">
            Browse the OpenAPI reference <ArrowUpRight aria-hidden="true" />
          </a>
        </>
      }
      facts={[
        { value: String(TOOLS.length), label: "tools, each a GET" },
        { value: "No key", label: "needed to start" },
        { value: "2,000 a day", label: "with a free key, per account" },
        { value: "/v1", label: "additive changes only" },
      ]}
      toc={TOC}
    >
      <Section id="quickstart" kicker="Quickstart" title="One GET returns JSON.">
        <div className="dx-prose dx-lead">
          <p>
            Replace <C>LAT,LON</C> with the point you care about. Highlighted capitals in every example
            are placeholders.
          </p>
        </div>
        <CodeBlock code={CURL_QUICK} lang="bash" title="Request" />
        <div className="dx-prose dx-mt-20">
          <p>
            Every response carries the records you asked for, the filters the server understood, and a{" "}
            <C>sources</C> list with each source&apos;s own <C>data_as_of</C> time. Show that time to your
            users. When <C>get_incidents</C>, <C>get_lane_closures</C> or <C>get_chain_controls</C> is
            filtered by route or center, the response also carries the <C>signs</C> and verified{" "}
            <C>cameras</C> near the returned records, when there are any.
          </p>
        </div>
        <CodeBlock code={RESPONSE_SHAPE} lang="json" title="200 OK · sample response" />
        <div className="dx-prose dx-mt-20">
          <p>
            The full machine-readable contract is the OpenAPI document at{" "}
            <a href={`${API_ROOT}/openapi.json`} className="dx-link">
              {API_ROOT_TEXT}/openapi.json
            </a>
            , with a browsable reference at{" "}
            <a href={`${API_ROOT}/docs`} className="dx-link">
              {API_ROOT_TEXT}/docs
            </a>{" "}
            and an index at{" "}
            <a href={API_ROOT} className="dx-link">
              {API_ROOT_TEXT}
            </a>
            . It is generated from the tools&apos; own schemas, so it is never out of date.
          </p>
        </div>
      </Section>

      <Section id="basics" kicker="Basics" title="Base URL and versioning">
        <dl className="dx-defs">
          <div>
            <dt>Base URL</dt>
            <dd>
              <C>{API_ROOT}</C>. Every tool is <C>{"GET " + reference.prefix + "/tools/{tool}"}</C> with
              arguments as query parameters. Only GET and OPTIONS are accepted.
            </dd>
          </div>
          <div>
            <dt>Versioning</dt>
            <dd>
              The path carries the version. Changes within <C>/v1</C> are additive: new fields, new
              parameters with defaults, new tools. Nothing is renamed or removed within a version. A
              breaking change would ship as <C>/v2</C> with <C>/v1</C> kept running.
            </dd>
          </div>
          <div>
            <dt>Encoding</dt>
            <dd>
              Query strings are URL-encoded UTF-8; a space in a value is <C>%20</C>, as in{" "}
              <C>Main%20St</C>. Responses are <C>application/json</C>, UTF-8, uncompressed unless you
              send <C>Accept-Encoding: gzip</C>.
            </dd>
          </div>
          <div>
            <dt>Cross-origin</dt>
            <dd>
              Every <C>/v1</C> response carries <C>Access-Control-Allow-Origin: *</C> and answers
              preflight, so a browser page can call it directly. Do that keyless (see the rules below).
            </dd>
          </div>
          <div>
            <dt>Caching</dt>
            <dd>
              Tool responses are <C>Cache-Control: no-store</C>; cache them yourself for as long as the
              tool&apos;s refresh interval says.
            </dd>
          </div>
        </dl>
      </Section>

      <Section id="keys" kicker="Keys and limits" title="Limits are counted per account.">
        <div className="dx-prose dx-lead">
          <p>
            Without a key, requests are limited per network address, and everything behind that address
            shares the day. A key moves you onto your own limits. Every key belongs to a signed-in
            account: open the{" "}
            <Link href="/map" prefetch={false} className="dx-link">
              live map
            </Link>
            , choose Settings, sign in with Google or an email link, and create a key under API keys.
            The key is shown once. Send it as <C>X-API-Key</C> or{" "}
            <C>Authorization: Bearer cs_live_...</C>.
          </p>
        </div>
        <CodeBlock code={CURL_KEYED} lang="bash" title="A keyed request" />
        <DocFigure name="rate-limit" />
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">Rate limits by tier</caption>
            <thead>
              <tr>
                <th scope="col">Tier</th>
                <th scope="col">Counted per</th>
                <th scope="col">Sustained</th>
                <th scope="col">Burst</th>
                <th scope="col">Requests per UTC day</th>
              </tr>
            </thead>
            <tbody>
              {TIERS.map((row) => (
                <tr key={row[0]}>
                  <th scope="row">{row[0]}</th>
                  <td data-label="Counted per">{row[1]}</td>
                  <td data-label="Sustained" className="num">{row[2]}</td>
                  <td data-label="Burst" className="num">{row[3]}</td>
                  <td data-label="Requests per UTC day" className="num">{row[4]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="dx-list dx-mt-20">
          <li>
            The limits belong to the account: all of its keys share one burst allowance and one daily
            count, so creating another key never buys a fresh allowance. An account holds up to five
            active keys and creates up to ten a day. Revoking a key stops it within a minute.
          </li>
          <li>
            Every keyed response carries <C>RateLimit-Limit</C> and <C>RateLimit-Remaining</C> for the
            day. A spent day answers 429 with <C>Retry-After: 3600</C>; a burst answers 429 with{" "}
            <C>Retry-After: 2</C>. Days reset at midnight UTC. Limits apply to <C>/v1</C> and{" "}
            <C>/mcp</C> alike.
          </li>
          <li>
            A bad key is a 401, never a quiet fallback to keyless. Ten bad keys from one address in about
            a minute block that address for 60 seconds.
          </li>
        </ul>
        <Callout>
          New keys are on the Free tier. <strong>Pro is coming soon.</strong> If you need more than Free
          today, write to{" "}
          <a href="mailto:hello@commutescout.com" className="dx-link">
            hello@commutescout.com
          </a>{" "}
          with what you are building and the volume you expect.
        </Callout>
      </Section>

      <Section id="responses" kicker="Responses" title="What every response carries">
        <dl className="dx-defs">
          <div>
            <dt>Coordinates</dt>
            <dd>
              Decimal degrees, WGS 84, as <C>lat</C> and <C>lon</C> fields on records. Parameters take a
              point as one string, <C>&quot;lat,lon&quot;</C>: latitude first, then longitude.
            </dd>
          </div>
          <div>
            <dt>Distances</dt>
            <dd>
              Kilometers unless the field name says otherwise (<C>miles_from_start</C>,{" "}
              <C>size_acres</C>). Radii are <C>radius_km</C>.
            </dd>
          </div>
          <div>
            <dt>Timestamps</dt>
            <dd>
              ISO 8601 with an offset. Most are UTC; some sources log in their own local offset. Parse
              the offset rather than assuming one.
            </dd>
          </div>
          <div>
            <dt>Lists</dt>
            <dd>
              Carry <C>count</C>. A capped list also carries <C>total</C> and <C>truncated: true</C>,
              and a note saying so. Counts are exact even when the list is cut.
            </dd>
          </div>
          <div>
            <dt>Sources</dt>
            <dd>
              Every response lists each source it read with <C>ok</C> and <C>data_as_of</C>. When a
              source is down the response still answers from the others and marks that one{" "}
              <C>ok: false</C>.
            </dd>
          </div>
          <div>
            <dt>Notes</dt>
            <dd>
              A <C>notes</C> list explains anything the server did on your behalf, such as clamping a
              radius or listing the corridors when a route did not match. Read it; it is meant for
              people.
            </dd>
          </div>
          <div>
            <dt>Errors inside a 200</dt>
            <dd>
              A tool that understood the request but could not act on it (an unrecognized region, a
              malformed center) answers 200 with an <C>error</C> field in the body and usually the
              accepted values next to it. Transport and parameter errors use the envelope below.
            </dd>
          </div>
        </dl>
      </Section>

      <Section id="errors" kicker="Errors" title="One envelope everywhere">
        <div className="dx-prose dx-lead">
          <p>
            A status code, a stable <C>code</C> you can branch on, a <C>message</C> for a log line, and a{" "}
            <C>hint</C> for a person.
          </p>
        </div>
        <CodeBlock code={ERROR_SHAPE} lang="json" title="400 Bad Request" />
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">Error codes</caption>
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">code</th>
                <th scope="col">Meaning</th>
              </tr>
            </thead>
            <tbody>
              {ERRORS.map((row) => (
                <tr key={row[1]}>
                  <td>{statusTag(row[0])}</td>
                  <th scope="row">
                    <code>{row[1]}</code>
                  </th>
                  <td>{row[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Callout>
          Retry only 429, 502 and 503: after the <C>Retry-After</C> the response gives, or one minute when
          it gives none, with backoff. A 400 or 401 will not fix itself.
        </Callout>
      </Section>

      <Section id="rules" kicker="Fair use" title="What not to do">
        <ol className="dx-rules">
          {RULES.map((r) => (
            <li key={r.title}>
              <b>{r.title}</b>
              <p>{r.body}</p>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="tools" kicker="Tool reference" title={`${TOOLS.length} tools, parameter by parameter`}>
        <div className="dx-prose dx-lead">
          <p>
            18 tools. Each one lists every parameter it accepts, what it reads, how fresh that is, and
            what it caps. Replace the capitalized placeholders (<C>LAT,LON</C>, <C>ROUTE</C>,{" "}
            <C>PLACE</C> and the like) with your own values. <C>home</C> and <C>work</C> need a key whose
            account has them saved. Optional parameters combine; leave them out for everything.
          </p>
        </div>
        {GROUPS.map((g) => (
          <div key={g.id} className="dx-mt-36">
            <h3 id={g.id}>{g.title}</h3>
            {g.blurb ? (
              <p className="dx-small dx-mt-8 dx-measure">
                {g.blurb}
              </p>
            ) : null}
            {g.tools.map((n) => {
              const t = BY_NAME.get(n);
              return t ? <ToolEntry key={n} t={t} /> : null;
            })}
          </div>
        ))}
      </Section>

      <Section id="mcp" kicker="MCP" title="The same tools over MCP">
        <div className="dx-prose dx-lead">
          <p>
            The same {TOOLS.length} tools for Claude and any other MCP client, over streamable HTTP. No
            key is needed. A key works the same way as on <C>/v1</C>: it gives your client its own
            limits, and it lets <C>&quot;home&quot;</C>, <C>&quot;work&quot;</C> and your saved places
            work in every trip tool.
          </p>
        </div>
        <div className="dx-mt-20">
          <CopyField value={`${BASE}/mcp`} label="MCP endpoint" />
        </div>
        <div className="dx-prose dx-mt-20">
          <p>
            Setup for Claude Code, claude.ai, Cursor, VS Code, Windsurf, Codex, Gemini CLI and ChatGPT,
            plus local stdio, is on the{" "}
            <Link href="/mcp#connect" prefetch={false} className="dx-link">
              MCP server page
            </Link>
            . Agents can read the same steps as plain text at{" "}
            <a href="/llms.txt" className="dx-link">
              /llms.txt
            </a>
            . The server is open source; its tool descriptions are written for the model reading them and
            say the same things this page says.
          </p>
        </div>
      </Section>

      <Section id="bulk" kicker="Bulk" title="Bulk snapshots">
        <div className="dx-prose dx-lead">
          <p>
            The map does not poll the API; it reads three gzip JSON snapshots the server publishes and the
            edge caches. They are public and the cheapest way to read everything at once. They carry the
            same records as the map&apos;s markers, so their shape follows the map, not this API, and it
            can change between releases.
          </p>
        </div>
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">Bulk snapshot objects</caption>
            <thead>
              <tr>
                <th scope="col">Object</th>
                <th scope="col">Rebuilt</th>
                <th scope="col">Holds</th>
              </tr>
            </thead>
            <tbody>
              {BULK.map(([name, every, holds]) => (
                <tr key={name}>
                  <th scope="row">
                    <code>https://data.commutescout.com/{name}</code>
                  </th>
                  <td data-label="Rebuilt" className="num">{every}</td>
                  <td data-label="Holds">{holds}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="dx-prose dx-mt-20">
          <p>
            An object is only uploaded when its contents changed. Fetch with <C>If-None-Match</C> and honor
            the <C>Cache-Control</C> you get back. Attribution applies exactly as it does to the API.
          </p>
        </div>
      </Section>

      <Section id="flare" kicker="Plugins" title="Flare plugins">
        <div className="dx-prose dx-lead">
          <p>
            Flare is CommuteScout&apos;s open protocol for third-party alert sources: a small HTTPS contract
            a plugin server implements (handshake, alerts by radius, reports, confirmations) so that anyone
            can run a public or private source that shows on the map and in the apps.{" "}
            <Link href="/plugins" prefetch={false} className="dx-link">
              Read the plugins page
            </Link>
            , then run the conformance check against your plugin. The backend and the apps accept exactly
            what the check accepts.
          </p>
        </div>
        <CodeBlock code="python -m ca_roads.flare check https://your-plugin.example" lang="bash" />
      </Section>

      <Section id="terms" kicker="Terms" title="Attribution and terms">
        <ul className="dx-list dx-lead dx-mt-16">
          <li>
            Credit CommuteScout and the agency named in each record&apos;s <C>source</C> wherever the data
            is shown. The{" "}
            <Link href="/data-sources" prefetch={false} className="dx-link">
              data sources page
            </Link>{" "}
            lists every agency and what it publishes.
          </li>
          <li>
            The data is informational and can be delayed, incomplete or wrong. Show the <C>data_as_of</C>{" "}
            time, and tell people to verify with 511 or the state DOT before they drive.
          </li>
          <li>
            Limits are enforced and keys can be revoked. The{" "}
            <Link href="/terms" prefetch={false} className="dx-link">
              terms
            </Link>{" "}
            and{" "}
            <Link href="/privacy" prefetch={false} className="dx-link">
              privacy page
            </Link>{" "}
            apply to API use; keyed requests are logged per key (key id, tool, status) for metering and
            nothing else.
          </li>
          <li>
            Questions, a higher limit, or a feed you would like added:{" "}
            <Link href="/contact" prefetch={false} className="dx-link">
              contact
            </Link>
            .
          </li>
        </ul>
      </Section>
    </DocsShell>
  );
}

