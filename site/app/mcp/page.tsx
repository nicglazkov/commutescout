import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, Briefcase, Dumbbell, House, MapPin, Plus } from "lucide-react";
import { DocsShell, Section, type TocItem } from "@/components/docs/docs-shell";
import { C, CodeBlock, CopyField } from "@/components/docs/code-block";
import { Tabs } from "@/components/docs/tabs";
import { DocFigure } from "@/components/docs/doc-figure";
// Per-client setup, generated from src/ca_roads_mcp/connect.py by
// scripts/gen_api_reference.py. The same source renders /llms.txt, so the
// steps people read here and the steps agents read there cannot drift.
import setup from "@/lib/mcp-clients.json";
// The tool list, names, parameters and one-line summaries come from the
// same generated reference as /developers, so this page cannot list a tool
// the server does not register or miss one it does.
import reference from "@/lib/api-reference.json";
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";

// MCP page. Sources for every factual claim: docs/mcp.md,
// src/ca_roads_mcp/server.py (tools, the three prompts, the server
// instructions' grouping), src/ca_roads_mcp/planning.py (how
// best_time_to_go picks a departure), src/ca_roads/apikeys.py (limits).
// tests/test_snapshot.py checks the state count and every "N tools"
// claim on this page against the registry.
//
// Access: every /mcp call needs an API key (owner decision, 2026-11-19).
// The per-client steps render site/lib/mcp-clients.json as-is; that file
// is generated from src/ca_roads_mcp/connect.py, which owns the wording.
export const metadata: Metadata = {
  title: "MCP Server - CommuteScout",
  description:
    "Connect Claude or any MCP client to CommuteScout: plan any US drive, find the best time to leave, and read live road data, weather and history.",
  alternates: {
    canonical: "https://commutescout.com/mcp",
  },
  openGraph: {
    title: "MCP Server - CommuteScout",
    description:
      "Connect Claude or any MCP client to CommuteScout: plan any US drive, find the best time to leave, and read live road data, weather and history.",
    url: "https://commutescout.com/mcp",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

const MCP_URL = setup.endpoint;

type Param = { name: string; required: boolean };
type Tool = { name: string; summary: string; params: Param[] };
const TOOLS = reference.tools as Tool[];
const BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));

const GROUPS: { title: string; blurb: string; tools: string[] }[] = [
  {
    title: "Trips, anywhere in the US",
    blurb: "Pass \"home\", \"work\" or a saved place's name as any origin or destination. Leave the origin out to start from Home.",
    tools: ["plan_trip", "best_time_to_go", "find_place", "get_my_places"],
  },
  {
    title: "Around one place",
    blurb: "Live events, weather, speeds and history around a point, across every covered state.",
    tools: ["get_nearby_events", "get_weather", "get_traffic", "get_area_history", "get_coverage"],
  },
  {
    title: "California, in depth",
    blurb: "California publishes the most detail. These tools read it directly, including 17 curated corridors.",
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
const EXTRA = TOOLS.filter((t) => !GROUPED.has(t.name)).map((t) => t.name);
if (EXTRA.length) GROUPS.push({ title: "More", blurb: "", tools: EXTRA });

// A signature a reader can scan: required parameters plain, optional ones
// with a question mark. More than four optional ones collapse to "...".
function signature(t: Tool) {
  const req = t.params.filter((p) => p.required).map((p) => p.name);
  const opt = t.params.filter((p) => !p.required).map((p) => `${p.name}?`);
  const shown = [...req, ...opt.slice(0, Math.max(0, 4 - req.length))];
  if (shown.length < req.length + opt.length) shown.push("...");
  return `(${shown.join(", ")})`;
}

const PROMPTS = [
  ["Best time to visit", "best_time", "origin, destination, day", "Calls best_time_to_go, then plan_trip for the recommended departure."],
  ["Plan a trip", "trip_check", "origin, destination, depart_at", "Calls plan_trip and lists, in order along the route, what could change the drive."],
  ["Road trip check", "road_trip_check", "from_place, to_place", "Calls check_route for a trip between two California places, with fallbacks when no corridor matches."],
];

const TOC: TocItem[] = [
  { id: "how", label: "How it works" },
  { id: "connect", label: "Setup" },
  { id: "saved-places", label: "Saved places" },
  { id: "tools", label: "Tools and prompts" },
  { id: "local", label: "Self-hosting" },
  { id: "registry", label: "MCP Registry" },
];

export default function McpPage() {
  return (
    <DocsShell
      current="/mcp"
      title="MCP Server"
      dek={
        <>
          Give Claude, Cursor or any MCP client live road data in 37 states. Plan a drive, find the
          best time to leave, or check what is on the road right now.
        </>
      }
      actions={
        <>
          <CopyField value={MCP_URL} label="MCP endpoint" />
          <a href="#connect" className="dx-textlink">
            Setup
          </a>
        </>
      }
      facts={[
        { value: String(TOOLS.length), label: "tools" },
        { value: String(STATE_COUNT), label: "states" },
        { value: String(AGENCY_FEED_COUNT), label: "official feeds" },
      ]}
      toc={TOC}
    >
      <Section id="how" title="How it works">
        <div className="dx-prose dx-lead">
          <p>You ask a question. Your assistant calls a tool, and CommuteScout answers from live agency data.</p>
        </div>
        <DocFigure name="mcp-call" />
        <DocFigure name="route-strip" n={2} />
        <DocFigure name="departure-chart" n={3} />
      </Section>

      <Section id="connect" title="Setup">
        <div className="dx-prose dx-lead">
          <p>
            Add the endpoint <C>{setup.endpoint}</C> to your client with your API key.{" "}
            <Link href="/developers#quickstart" prefetch={false} className="dx-link">
              Get a free key
            </Link>{" "}
            from Settings on the live map. Agents can read the same steps at{" "}
            <a href="/llms.txt" className="dx-link">
              commutescout.com/llms.txt
            </a>
            .
          </p>
        </div>
        <Tabs
          label="MCP clients"
          tabs={setup.clients.map((client) => ({
            id: client.id,
            label: client.name.replace(" and Claude Desktop", "").replace(" (GitHub Copilot)", "").replace("OpenAI Codex CLI", "Codex").replace("Any other MCP client", "Other"),
            content: (
              <div id={client.id}>
                <h3 className="sr-only">{client.name}</h3>
                {client.steps.map((step, i) =>
                  "code" in step && step.code ? (
                    <CodeBlock
                      key={i}
                      code={step.code}
                      lang={step.lang === "sh" ? "bash" : step.lang === "json" ? "json" : step.lang === "toml" ? "toml" : "text"}
                    />
                  ) : (
                    <p key={i}>{"text" in step ? step.text : null}</p>
                  ),
                )}
              </div>
            ),
          }))}
        />
      </Section>

      <Section id="saved-places" title="Saved places">
        <div className="dx-prose dx-lead">
          <p>
            Save Home, Work and any other place you like, such as the gym, school or a friend&apos;s place, on
            the map or in the app. With your key connected, your assistant can use those names in every trip
            tool: &ldquo;from home to the gym&rdquo; just works, and a trip with no starting point begins at
            Home. Your places are only read for your own account.
          </p>
        </div>
        <ul className="dx-places" aria-label="Examples of saved places">
          <li>
            <House aria-hidden="true" /> Home
          </li>
          <li>
            <Briefcase aria-hidden="true" /> Work
          </li>
          <li>
            <Dumbbell aria-hidden="true" /> The gym
          </li>
          <li>
            <MapPin aria-hidden="true" /> A friend&apos;s place
          </li>
          <li data-any="">
            <Plus aria-hidden="true" /> Any place you name
          </li>
        </ul>
        <div className="dx-prose dx-mt-20">
          <p>
            The server never sees where your device is. When you say &ldquo;from here&rdquo;, your assistant
            uses a place you have named in the conversation, or asks you. Keys and limits are the same as for
            the{" "}
            <Link href="/developers#keys" prefetch={false} className="dx-link">
              REST API
            </Link>
            .
          </p>
        </div>
      </Section>

      <Section id="tools" title={`${TOOLS.length} tools and ${PROMPTS.length} prompts`}>
        <div className="dx-prose dx-lead">
          <p>
            The same tools as the REST API. Every parameter, refresh interval and cap is in the{" "}
            <Link href="/developers#tools" prefetch={false} className="dx-link">
              tool reference
            </Link>
            .
          </p>
        </div>
        {GROUPS.map((g) => (
          <div key={g.title} className="dx-mt-36">
            <h3>{g.title}</h3>
            {g.blurb ? (
              <p className="dx-small dx-mt-8 dx-measure">
                {g.blurb}
              </p>
            ) : null}
            <ul className="dx-toolgrid">
              {g.tools.map((n) => {
                const t = BY_NAME.get(n);
                if (!t) return null;
                return (
                  <li key={n}>
                    <Link href={`/developers#tool-${n}`} prefetch={false} className="dx-plain">
                      <code>
                        {t.name}
                        <span className="sig">{signature(t)}</span>
                      </code>
                    </Link>
                    <p>{t.summary}</p>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
        <h3 className="dx-mt-36">Prompts</h3>
        <p className="dx-small dx-mt-8 dx-measure">
          Clients that show MCP prompts offer these as one-click starting points.
        </p>
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">MCP prompts</caption>
            <thead>
              <tr>
                <th scope="col">Prompt</th>
                <th scope="col">Arguments</th>
                <th scope="col">What it does</th>
              </tr>
            </thead>
            <tbody>
              {PROMPTS.map(([title, name, args, what]) => (
                <tr key={name}>
                  <th scope="row">
                    {title}
                    <br />
                    <code className="dx-code-quiet">{name}</code>
                  </th>
                  <td data-label="Arguments">
                    <code>{args}</code>
                  </td>
                  <td data-label="What it does">{what}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="local" title="Self-hosting">
        {/* Owner review: self-hosting is not a supported path yet, so it is marked work in progress. */}
        <p className="dx-mt-8">
          <span className="dx-tag dx-tag-muted">Work in progress</span>
        </p>
        <div className="dx-prose dx-lead">
          <p>
            The server is open source, but running your own copy is not supported yet. Use the hosted endpoint
            above. Developer notes are in{" "}
            <a href="https://github.com/nicglazkov/commutescout/blob/main/docs/mcp.md" className="dx-link">
              docs/mcp.md
            </a>{" "}
            on GitHub.
          </p>
        </div>
      </Section>

      <Section id="registry" title="MCP Registry">
        <div className="dx-registry">
          <div className="dx-registry-main">
            <p className="dx-registry-k">Listed in the official MCP Registry as</p>
            <CopyField value="io.github.nicglazkov/commutescout" label="Registry name" />
            <p className="dx-registry-note">
              Clients that browse the registry find CommuteScout under this name. The server card is served at{" "}
              <C>/.well-known/mcp/server-card.json</C> on the MCP host.
            </p>
          </div>
          <a href="https://github.com/nicglazkov/commutescout/blob/main/docs/registry.md" className="dx-textlink">
            Registry notes <ArrowUpRight aria-hidden="true" />
          </a>
        </div>
        <div className="dx-prose dx-mt-20">
          <p>
            Not running an MCP client? Every tool is also a plain HTTP GET. See the{" "}
            <Link href="/developers" prefetch={false} className="dx-link">
              REST API
            </Link>
            . The full reference also lives in{" "}
            <a href="https://github.com/nicglazkov/commutescout/blob/main/docs/mcp.md" className="dx-link">
              docs/mcp.md
            </a>{" "}
            on GitHub.
          </p>
        </div>
      </Section>
    </DocsShell>
  );
}
