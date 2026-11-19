import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { DocsShell, Section, type TocItem } from "@/components/docs/docs-shell";
import { C, CodeBlock, CopyField } from "@/components/docs/code-block";
import { Callout } from "@/components/docs/callout";
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

// MCP page. Sources for every factual claim: docs/mcp.md,
// src/ca_roads_mcp/server.py (tools, the three prompts, the server
// instructions' grouping), src/ca_roads_mcp/planning.py (how
// best_time_to_go picks a departure), src/ca_roads/apikeys.py (limits).
// tests/test_snapshot.py checks the state count and every "N tools"
// claim on this page against the registry.
export const metadata: Metadata = {
  title: "MCP server - CommuteScout",
  description:
    "Connect Claude or any MCP client to CommuteScout: plan any US drive, find the best time to leave, and read live road data, weather and history. No key required.",
  alternates: {
    canonical: "https://commutescout.com/mcp",
  },
  openGraph: {
    title: "MCP server - CommuteScout",
    description:
      "Connect Claude or any MCP client to CommuteScout: plan any US drive, find the best time to leave, and read live road data, weather and history. No key required.",
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
    blurb: "Pass \"home\", \"work\" or a saved place's name as any origin or destination; leave the origin out to start from Home.",
    tools: ["plan_trip", "best_time_to_go", "find_place", "get_my_places"],
  },
  {
    title: "Around one place",
    blurb: "Live events, weather, speeds and history around a point, across every covered state.",
    tools: ["get_nearby_events", "get_weather", "get_traffic", "get_area_history", "get_coverage"],
  },
  {
    title: "California, in depth",
    blurb: "California publishes the deepest feeds; these tools read them directly, including 17 curated corridors.",
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

const STDIO_CONFIG = `{
  "mcpServers": {
    "commutescout": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nicglazkov/commutescout", "ca-roads-mcp"]
    }
  }
}`;

const LOCAL = `pip install .
ca-roads-mcp                                        # stdio
ca-roads-mcp --transport http --host 127.0.0.1      # streamable HTTP on $PORT`;

const TOC: TocItem[] = [
  { id: "how", label: "How a question is answered" },
  { id: "connect", label: "Connect your client" },
  { id: "saved-places", label: "Your places" },
  { id: "tools", label: "Tools and prompts" },
  { id: "local", label: "Run it locally" },
  { id: "quality", label: "Evals and registry" },
];

export default function McpPage() {
  return (
    <DocsShell
      current="/mcp"
      eyebrow="MCP server"
      title="Bring live roads to your assistant."
      dek={
        <>
          Claude, ChatGPT, Cursor or any MCP client can answer road questions in 37 states from live
          data instead of guesses: plan any US drive, find the best time to leave, and read what is on
          the road right now. No key or account needed.
        </>
      }
      actions={
        <>
          <CopyField value={MCP_URL} label="MCP endpoint" />
          <a href="#connect" className="dx-textlink">
            Setup for your client
          </a>
        </>
      }
      facts={[
        { value: String(TOOLS.length), label: "tools, the same as the REST API" },
        { value: String(PROMPTS.length), label: "ready-made prompts" },
        { value: "No key", label: "needed; a key adds your places" },
        { value: "HTTP", label: "streamable, stateless" },
      ]}
      toc={TOC}
    >
      <Section id="how" kicker="A question, answered" title="Your assistant calls a tool. The tool reads the feeds.">
        <div className="dx-prose dx-lead">
          <p>
            Ask in plain English: &ldquo;When should I leave for the airport tomorrow?&rdquo;, &ldquo;Is the
            pass on my route open?&rdquo;, &ldquo;What is going on near work?&rdquo; The assistant picks a
            tool and sends one call. The server reads the same live feeds behind the map and
            answers with each source&apos;s own <C>data_as_of</C> time.
          </p>
        </div>
        <DocFigure name="mcp-call" />
        <DocFigure name="route-strip" n={2} />
        <dl className="dx-defs">
          <div>
            <dt>plan_trip</dt>
            <dd>
              The route for that departure with full closures excluded, the drive time (with traffic,
              typical and free-flow), and everything live on the line grouped by kind, each list in mile
              order: incidents, closures, chain controls, cameras, signs, tolls, road weather and
              wildfires, plus weather alerts and the forecast on arrival.
            </dd>
          </div>
          <div>
            <dt>best_time_to_go</dt>
            <dd>
              Up to 16 departures compared. Departures with snow, ice, sleet, freezing rain or a
              blizzard forecast on arrival are set aside, then the shortest drive wins, with fewer usual
              incidents that hour breaking a tie. With <C>arrive_by</C> it picks the latest departure that
              still arrives on time.
            </dd>
          </div>
        </dl>
        <DocFigure name="departure-chart" n={3} />
      </Section>

      <Section id="connect" kicker="Connect" title="One URL for every client">
        <div className="dx-prose dx-lead">
          <p>
            The endpoint is <C>{setup.endpoint}</C> (streamable HTTP, stateless). It works without a key;
            the key lines are optional and turn on your saved places. Agents can read the same steps as
            plain text at{" "}
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

      <Section id="saved-places" kicker="Your places" title="Home, work and favorites">
        <div className="dx-prose dx-lead">
          <p>
            With an API key, &ldquo;home&rdquo;, &ldquo;work&rdquo; and the names of your saved places work in
            every trip tool, and a trip with no starting point starts from Home. The places are the ones
            you save on the map and in the app, and they are only ever read for your own account.
          </p>
        </div>
        <ol className="dx-rules dx-rules--compact">
          <li>
            <span>
              Open the{" "}
              <Link href="/map" prefetch={false} className="dx-link">
                live map
              </Link>
              , choose Settings, and sign in.
            </span>
          </li>
          <li>
            <span>Under API keys, create a key. It is shown once, so copy it then.</span>
          </li>
          <li>
            <span>
              Add it to your client as the header <C>{setup.key_header}</C>, using the key lines in your
              client&rsquo;s steps above.
            </span>
          </li>
        </ol>
        <Callout>
          A key also moves your client onto your account&rsquo;s limits: 2,000 requests a day on the free
          tier, shared by every key on the account, against 10,000 a day per address without one. No MCP
          server can see your device&rsquo;s location, so for &ldquo;from here&rdquo; the assistant uses a
          place you name or asks you.{" "}
          <Link href="/developers#keys" prefetch={false} className="dx-link">
            Keys and limits in detail
          </Link>
          .
        </Callout>
      </Section>

      <Section id="tools" kicker="What it exposes" title={`${TOOLS.length} tools and ${PROMPTS.length} prompts`}>
        <div className="dx-prose dx-lead">
          <p>
            The same 18 tools as the REST API. Every parameter, refresh interval and cap is in the{" "}
            <Link href="/developers#tools" prefetch={false} className="dx-link">
              tool reference
            </Link>
            . Route and region answers also carry context that changes the advice: weather alerts along
            the trip, road-weather stations reporting something notable, recent significant earthquakes,
            and the signs and cameras along the way. Route names are normalized, so a highway can be written the way
            people say it, with or without a prefix or a space.
          </p>
        </div>
        {GROUPS.map((g) => (
          <div key={g.title} style={{ marginTop: 36 }}>
            <h3>{g.title}</h3>
            {g.blurb ? (
              <p className="dx-small" style={{ marginTop: 6, maxWidth: "68ch" }}>
                {g.blurb}
              </p>
            ) : null}
            <ul className="dx-toolgrid">
              {g.tools.map((n) => {
                const t = BY_NAME.get(n);
                if (!t) return null;
                return (
                  <li key={n}>
                    <Link href={`/developers#tool-${n}`} prefetch={false} style={{ textDecoration: "none" }}>
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
        <h3 style={{ marginTop: 36 }}>Prompts</h3>
        <p className="dx-small" style={{ marginTop: 6, maxWidth: "68ch" }}>
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
                    <code style={{ fontWeight: 400, color: "var(--dx-ink-3)" }}>{name}</code>
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

      <Section id="local" kicker="Self-hosting" title="Run it locally">
        <div className="dx-prose dx-lead">
          <p>
            The hosted server is the easy path. To run your own copy, the server is a single Python package
            with no required keys (the trip tools use <C>STADIA_API_KEY</C> and <C>TOMTOM_API_KEY</C> when
            set, and live speeds need the TomTom key). A stdio config for Claude Desktop or Claude Code needs{" "}
            <a href="https://docs.astral.sh/uv/" className="dx-link">
              uv
            </a>
            :
          </p>
        </div>
        <CodeBlock code={STDIO_CONFIG} lang="json" title="claude_desktop_config.json" />
        <CodeBlock code={LOCAL} lang="bash" title="From a checkout" />
        <Callout tone="warn">
          The HTTP transport is tuned for Cloud Run: it binds 0.0.0.0 and turns host-header checks off. On
          your own machine, bind it to localhost with <C>--host 127.0.0.1</C>.
        </Callout>
      </Section>

      <Section id="quality" kicker="Quality" title="Evals and registry">
        <div className="dx-cards">
          <div className="dx-card">
            <h3>How good are the answers?</h3>
            <p>
              An eval suite with recorded fixtures and 91 golden questions runs on demand, not on a release
              schedule. Each published scorecard names the version it reflects.
            </p>
            <p>
              <a href="https://github.com/nicglazkov/commutescout/blob/main/EVALS.md" className="dx-textlink">
                See the scorecard <ArrowUpRight aria-hidden="true" />
              </a>
            </p>
          </div>
          <div className="dx-card">
            <h3>MCP Registry</h3>
            <p>
              Published as <C>io.github.nicglazkov/commutescout</C>, with the server card at{" "}
              <C>/.well-known/mcp/server-card.json</C> on the MCP host.
            </p>
            <p>
              <a href="https://github.com/nicglazkov/commutescout/blob/main/docs/registry.md" className="dx-textlink">
                Registry notes <ArrowUpRight aria-hidden="true" />
              </a>
            </p>
          </div>
        </div>
        <div className="dx-prose" style={{ marginTop: 20 }}>
          <p>
            Not running an MCP client? Every tool is also a plain HTTP GET; see the{" "}
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
