import type { Metadata } from "next";
import Link from "next/link";
import { CircleCheck, MessageCircleQuestion, Plug } from "lucide-react";
import { CopyField } from "@/components/copy-field";

// MCP page takes its own metadata, matching the shape every other
// marketing page uses (title/description/canonical/openGraph/twitter).
// Description is one sentence, Google style. Source for every factual
// claim on this page: docs/mcp.md; this page restyles that doc into a
// visual developer page rather than rewording its content.
//
// Tool count note: docs/mcp.md's tool-reference table previously listed
// only nine tools, missing get_nearby_events (src/ca_roads_mcp/server.py),
// while README.md's feature list correctly said "ten tools." mcp.md was
// the stale artifact; both it and this page's TOOLS array below now
// include all ten (coordinator ruling, 2026-08-05).
export const metadata: Metadata = {
  title: "MCP server - CommuteScout",
  description:
    "Connect Claude or any MCP client to CommuteScout's live road data: ten tools over curated corridors and regions, no key required.",
  alternates: {
    canonical: "https://commutescout.com/mcp",
  },
  openGraph: {
    title: "MCP server - CommuteScout",
    description:
      "Connect Claude or any MCP client to CommuteScout's live road data: ten tools over curated corridors and regions, no key required.",
    url: "https://commutescout.com/mcp",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

const MCP_URL = "https://mcp.commutescout.com/mcp";

const STEPS = [
  {
    icon: Plug,
    title: "Add the connector",
    body:
      "Add a custom connector with the URL above (streamable HTTP), or " +
      "run the server locally over stdio for Claude Desktop or Claude " +
      "Code. No key or account needed either way.",
  },
  {
    icon: MessageCircleQuestion,
    title: "Ask about a drive",
    body:
      "Ask about a route or region in plain English. The assistant " +
      "already knows 17 curated corridors, from I-80 Sacramento to " +
      "Reno to the Bay Area freeways.",
  },
  {
    icon: CircleCheck,
    title: "Get sourced answers",
    body:
      "Every answer reads from the same live feeds behind the map, " +
      "with per-source timestamps and context that changes the advice.",
  },
];

type Tool = { signature: string; description: string };

const TOOLS: Tool[] = [
  {
    signature: "check_route(from_place, to_place)",
    description:
      "Everything active along a major corridor (17 curated corridors: " +
      "I-80 Sacramento-Reno, US-50 to Tahoe, I-5, US-101, SR-17, SR-99, " +
      "SR-1, I-15 to Vegas, Bay Area freeways, Tahoe locals), ordered by " +
      "miles along the route",
  },
  {
    signature: "check_region(region)",
    description:
      "One-call report for a whole region (Bay Area, SoCal, Sierra, " +
      "Central Valley, and four more): exact counts, incidents " +
      "severity-sorted, full closures first, capped lists that say when " +
      "they truncate",
  },
  {
    signature: "get_incidents(highway?, area?, center?)",
    description: "Live CHP incidents by route, dispatch area, or a point and radius",
  },
  {
    signature: "get_lane_closures(route?, district?, center?)",
    description: "Closures in place right now, classified per the closure taxonomy",
  },
  {
    signature: "get_chain_controls(route?, center?)",
    description:
      'Current chain requirements; says "none active" explicitly in the off-season',
  },
  {
    signature: "get_wildfires(near_route?, center?)",
    description:
      "Active fires with size, containment, and mapped perimeter edges, " +
      "flagged near major highways",
  },
  {
    signature: "get_cameras(center?, route?)",
    description:
      "Roadside camera snapshots, each verified live before it is " +
      "returned (offline placeholder frames are filtered by image " +
      "freshness)",
  },
  {
    signature: "get_road_signs(route?, center?)",
    description: "What changeable message signs are displaying right now, verbatim",
  },
  {
    signature: "rank_routes(by?, limit?)",
    description:
      'All 17 corridors ranked by live events or measured congestion, ' +
      'with reasons; answers "what are the busiest routes right now"',
  },
  {
    signature: "get_nearby_events(center, radius_km?, kinds?)",
    description:
      "Live road events near a point across every covered state, 38 " +
      "states, not just California; the fallback for locations outside " +
      "California, near a state border, or when a California tool comes " +
      "back empty",
  },
];

const CONTEXT_TEXT =
  "Route and region reports also carry context that changes the " +
  "advice: weather alerts sampled along the trip, road-weather " +
  "stations reporting something notable, recent significant " +
  "earthquakes, the signs and cameras along the way, and live speeds " +
  "when a TomTom key is set. Route names are normalized (\"17\", " +
  "\"hwy 50\", \"I80\" all work), and docstrings are written for the " +
  "LLM consumer: what the data is, its refresh cadence, and its limits.";

const STDIO_CONFIG = `{
  "mcpServers": {
    "commutescout": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nicglazkov/commutescout", "ca-roads-mcp"]
    }
  }
}`;

export default function McpPage() {
  return (
    <>
      {/* Hero band. Not a vendored Tailark block: styled to match the
          homepage's own navy developer band, since this whole page is
          that band's expanded, full-page form. */}
      <section className="bg-cs-navy text-white">
        <div className="mx-auto max-w-4xl px-6 py-16 text-center md:py-24">
          <h1 className="text-balance text-4xl font-medium tracking-tight md:text-5xl">
            Bring live roads to your assistant.
          </h1>
          <p className="text-white/70 mx-auto mt-4 max-w-2xl text-balance md:text-lg">
            CommuteScout exposes its entire data layer as an MCP server, so
            Claude (or any MCP client) can answer questions about
            California roads with live data instead of guesses.
          </p>

          <div className="mx-auto mt-8 max-w-md">
            <CopyField value={MCP_URL} />
          </div>

          <p className="text-white/60 mt-4 text-sm text-balance">
            No key or account needed. It is the same server behind{" "}
            <Link href="/" prefetch={false} className="underline underline-offset-2 hover:text-white">
              commutescout.com
            </Link>
            , with the same live feeds.
          </p>

          <Link
            href="https://github.com/nicglazkov/commutescout/blob/main/docs/mcp.md"
            prefetch={false}
            className="mt-6 inline-flex items-center gap-1.5 text-sm text-white/70 underline underline-offset-4 transition-colors hover:text-white"
          >
            View the full reference on GitHub
          </Link>
        </div>
      </section>

      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-6 sm:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, index) => (
              <div
                key={title}
                className="ring-cs-line bg-cs-paper flex flex-col gap-3 rounded-xl p-6 shadow ring-1"
              >
                <div className="flex items-center gap-2">
                  <span className="bg-cs-sky/15 text-cs-sky flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-medium">
                    {index + 1}
                  </span>
                  <Icon className="text-cs-sky size-4" aria-hidden="true" />
                </div>
                <p className="text-cs-ink font-medium">{title}</p>
                <p className="text-cs-ink/60 text-sm text-balance">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-cs-bg py-16 md:py-20" aria-labelledby="tools-heading">
        <div className="mx-auto max-w-7xl px-6">
          <h2
            id="tools-heading"
            className="text-cs-ink text-balance text-3xl font-medium tracking-tight md:text-4xl"
          >
            Ten tools, one live data spine
          </h2>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {TOOLS.map((tool) => (
              <div
                key={tool.signature}
                className="ring-cs-line bg-cs-paper flex flex-col gap-2.5 rounded-xl p-5 ring-1"
              >
                <code className="text-cs-ink text-sm font-medium break-all">
                  {tool.signature}
                </code>
                <p className="text-cs-ink/60 text-sm">
                  {tool.signature === "get_lane_closures(route?, district?, center?)" ? (
                    <>
                      Closures in place right now, classified per the{" "}
                      <Link
                        href="/data-sources#the-closure-taxonomy"
                        prefetch={false}
                        className="text-cs-sky hover:underline"
                      >
                        closure taxonomy
                      </Link>
                      .
                    </>
                  ) : (
                    tool.description
                  )}
                </p>
              </div>
            ))}
          </div>

          <p className="text-cs-ink/60 mt-8 max-w-3xl text-sm text-balance">
            {CONTEXT_TEXT}
          </p>
        </div>
      </section>

      <section className="py-16 md:py-20" aria-labelledby="local-heading">
        <div className="mx-auto max-w-3xl px-6">
          <h2
            id="local-heading"
            className="text-cs-ink text-balance text-3xl font-medium tracking-tight md:text-4xl"
          >
            Run it locally
          </h2>
          <p className="text-cs-ink/60 mt-4 text-balance">
            The server is a single Python package with zero required keys.
            Config for Claude Desktop or Claude Code:
          </p>

          <pre className="bg-cs-navy2 mt-6 overflow-x-auto rounded-xl p-5 text-sm text-white/90">
            <code>{STDIO_CONFIG}</code>
          </pre>

          <p className="text-cs-ink/60 mt-6 text-balance">
            From a checkout: <code className="bg-cs-bg text-cs-ink rounded px-1.5 py-0.5 text-sm">pip install .</code>{" "}
            then <code className="bg-cs-bg text-cs-ink rounded px-1.5 py-0.5 text-sm">ca-roads-mcp</code> for stdio,
            or{" "}
            <code className="bg-cs-bg text-cs-ink rounded px-1.5 py-0.5 text-sm">
              ca-roads-mcp --transport http
            </code>{" "}
            for streamable HTTP on{" "}
            <code className="bg-cs-bg text-cs-ink rounded px-1.5 py-0.5 text-sm">$PORT</code>. The http transport
            is tuned for Cloud Run (binds 0.0.0.0, host-header checks off), so bind it to localhost when running
            it on your machine:{" "}
            <code className="bg-cs-bg text-cs-ink rounded px-1.5 py-0.5 text-sm">
              ca-roads-mcp --transport http --host 127.0.0.1
            </code>
            .
          </p>
        </div>
      </section>

      <section className="bg-cs-bg pb-16 md:pb-20">
        <div className="mx-auto max-w-3xl px-6">
          <div className="grid gap-8 sm:grid-cols-2">
            <div>
              <h2 className="text-cs-ink text-xl font-medium tracking-tight">
                How good are the answers?
              </h2>
              <p className="text-cs-ink/60 mt-3 text-sm text-balance">
                An eval suite with recorded fixtures and 91 golden questions
                gates every release; the scorecard is public.
              </p>
              <a
                href="https://github.com/nicglazkov/commutescout/blob/main/EVALS.md"
                className="text-cs-sky mt-3 inline-block text-sm font-medium hover:underline"
              >
                See the scorecard
              </a>
            </div>

            <div>
              <h2 className="text-cs-ink text-xl font-medium tracking-tight">Registry</h2>
              <p className="text-cs-ink/60 mt-3 text-sm text-balance">
                The server is published as{" "}
                <code className="bg-cs-paper text-cs-ink rounded px-1.5 py-0.5">
                  io.github.nicglazkov/commutescout
                </code>
                .
              </p>
              <a
                href="https://github.com/nicglazkov/commutescout/blob/main/docs/registry.md"
                className="text-cs-sky mt-3 inline-block text-sm font-medium hover:underline"
              >
                Registry notes
              </a>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
