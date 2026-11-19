import Link from "next/link";
import { Apple, ArrowRight, ArrowUpRight, Smartphone } from "lucide-react";
import { CopyField } from "@/components/copy-field";
import { PhoneShot } from "@/components/phone-shot";
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";
import {
  ANDROID_RELEASES,
  TESTFLIGHT_IN_REVIEW,
  TESTFLIGHT_IN_REVIEW_NOTE,
  TESTFLIGHT_PUBLIC,
} from "@/lib/app-links";

// Homepage sections below the hero. Each claim is checked against the code:
// - map rebuilt about every 30 s: src/ca_roads_demo/snapshot.py (live.json.gz, 30 s)
// - watch alerts: WATCH_KINDS = incident, closure, chain, fire (src/ca_roads_demo/watch.py)
// - "sources" entries: source_status() in src/ca_roads_mcp/serialize.py
//   (source, description, ok, data_as_of, plus stale/error when set)
// - 18 MCP tools: @mcp.tool in src/ca_roads_mcp/server.py
// - 2,000 requests a day per account on a free key: site/app/developers

/* ---------------- What it reads ---------------- */

const FEED_KINDS = [
  "Highway patrol incident logs",
  "State DOT closures and roadwork",
  "Chain controls",
  "Cameras and message signs",
  "Road-weather stations",
  "NWS alerts and forecasts",
  "Wildfire perimeters",
  "Toll prices",
];

export function SourcesStrip() {
  return (
    <section aria-labelledby="reads-title" className="border-y border-cs-line bg-cs-surface">
      <div className="cs-container flex flex-col gap-3 py-5 md:flex-row md:items-baseline md:gap-8">
        <h2 id="reads-title" className="cs-eyebrow shrink-0">
          Reads live from
        </h2>
        <ul className="flex flex-wrap gap-x-6 gap-y-1.5 text-sm text-cs-ink-2">
          {FEED_KINDS.map((k) => (
            <li key={k}>{k}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ---------------- Four ways in ---------------- */

const WAYS = [
  {
    n: "01",
    title: "See it",
    body: "The live map of what agencies report right now, rebuilt about every 30 seconds.",
    href: "/map",
    cta: "Open the map",
  },
  {
    n: "02",
    title: "Plan it",
    body: "Route options with everything live along each one, exportable to GPX or KML.",
    href: "/map",
    cta: "Plan a route",
  },
  {
    n: "03",
    title: "Watch it",
    body: "Draw an area. Get a push or an email when an incident, closure, chain control or fire appears in it.",
    href: "/watch",
    cta: "Set up a watch area",
  },
  {
    n: "04",
    title: "Ask it",
    body: "Claude, ChatGPT, Cursor or any MCP client answers from the same feeds, with each source's time.",
    href: "/mcp",
    cta: "Connect an assistant",
  },
];

export function FourWays() {
  return (
    <section aria-labelledby="ways-title" className="py-20 md:py-28">
      <div className="cs-container">
        <div className="grid gap-6 md:grid-cols-12">
          <p className="cs-eyebrow md:col-span-3">One source of truth</p>
          <h2 id="ways-title" className="cs-h2 max-w-[22ch] md:col-span-9">
            One live picture of the road, four ways to use it.
          </h2>
        </div>
        <ol className="mt-12 grid border-t border-cs-line sm:grid-cols-2 lg:grid-cols-4">
          {WAYS.map((w, i) => (
            <li
              key={w.n}
              className={`group relative flex flex-col border-b border-cs-line py-7 sm:px-6 lg:border-b-0 ${
                i % 2 === 0 ? "sm:border-r sm:pl-0" : ""
              } ${i < 3 ? "lg:border-r" : ""} ${i === 2 ? "lg:pl-6" : ""}`}
            >
              <span className="cs-data text-xs text-cs-ink-3">{w.n}</span>
              <h3 className="cs-h3 mt-4">{w.title}</h3>
              <p className="mt-2 flex-1 text-[0.9375rem] leading-relaxed text-cs-ink-2">{w.body}</p>
              <Link
                href={w.href}
                prefetch={false}
                className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-cs-accent after:absolute after:inset-0"
              >
                {w.cta}
                <ArrowRight aria-hidden className="size-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
              </Link>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ---------------- Proof: sources on every answer ---------------- */

function Json() {
  // Illustrative values, real field names (source_status in serialize.py).
  const k = "text-cs-band-ink";
  const s = "text-[color-mix(in_srgb,var(--cs-accent)_45%,white)]";
  const b = "text-[color-mix(in_srgb,var(--cs-ok)_50%,white)]";
  const w = "text-[color-mix(in_srgb,var(--cs-fire)_55%,white)]";
  const c = "text-cs-band-ink-2";
  return (
    <pre className="cs-data overflow-x-auto p-5 text-[0.8125rem] leading-[1.7] text-cs-band-ink-2">
      <span className={c}>{"// part of every response (values illustrative)"}</span>
      {"\n"}
      <span className={k}>&quot;sources&quot;</span>: [{"\n"}
      {"  { "}
      <span className={k}>&quot;description&quot;</span>: <span className={s}>&quot;Highway patrol incident log&quot;</span>,{"\n"}
      {"    "}
      <span className={k}>&quot;ok&quot;</span>: <span className={b}>true</span>,{" "}
      <span className={k}>&quot;data_as_of&quot;</span>: <span className={s}>&quot;2026-01-14T18:02:10-08:00&quot;</span>{" },"}{"\n"}
      {"  { "}
      <span className={k}>&quot;description&quot;</span>: <span className={s}>&quot;State DOT lane closures&quot;</span>,{"\n"}
      {"    "}
      <span className={k}>&quot;ok&quot;</span>: <span className={b}>true</span>,{" "}
      <span className={k}>&quot;data_as_of&quot;</span>: <span className={s}>&quot;2026-01-14T17:59:44-08:00&quot;</span>{" },"}{"\n"}
      {"  { "}
      <span className={k}>&quot;description&quot;</span>: <span className={s}>&quot;Road-weather stations&quot;</span>,{"\n"}
      {"    "}
      <span className={k}>&quot;ok&quot;</span>: <span className={b}>true</span>,{" "}
      <span className={k}>&quot;stale&quot;</span>: <span className={w}>true</span>,{" "}
      <span className={k}>&quot;error&quot;</span>: <span className={w}>&quot;upstream timeout&quot;</span>{" }"}{"\n"}
      ]
    </pre>
  );
}

const STATS: { value: string; unit?: string; label: string }[] = [
  { value: String(AGENCY_FEED_COUNT), label: "official agency feeds" },
  { value: String(STATE_COUNT), label: "states covered" },
  { value: "30", unit: "s", label: "between map rebuilds" },
];

export function SourceProof() {
  return (
    <section aria-labelledby="proof-title" className="border-t border-cs-line py-20 md:py-28">
      <div className="cs-container grid gap-12 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-5">
          <p className="cs-eyebrow">Sources on every answer</p>
          <h2 id="proof-title" className="cs-h2 mt-4">
            Every answer shows where it came from.
          </h2>
          <p className="cs-lede mt-5 max-w-[34rem]">
            Each response lists the feeds it read, whether each one answered, and when that feed
            itself last changed. If a feed is down, the others still answer and that one says so.
          </p>
          <Link href="/data-sources" prefetch={false} className="cs-link mt-7 inline-flex items-center gap-1 text-[0.9375rem]">
            See every feed by state
            <ArrowRight aria-hidden className="size-3.5" />
          </Link>
        </div>
        <div className="min-w-0 lg:col-span-7">
          <dl className="grid grid-cols-3 overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface">
            {STATS.map((s, i) => (
              <div key={s.label} className={`px-4 py-5 sm:px-6 ${i > 0 ? "border-l border-cs-line" : ""}`}>
                <dt className="sr-only">{s.label}</dt>
                <dd className="cs-data text-[1.75rem] font-medium leading-none tracking-[-0.03em] text-cs-ink sm:text-[2.125rem]">
                  {s.value}
                  {s.unit && <span className="ml-0.5 font-sans text-[0.6em] tracking-normal text-cs-ink-2">{s.unit}</span>}
                </dd>
                <dd className="mt-2 text-[0.8125rem] leading-snug text-cs-ink-3">{s.label}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-4 overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-band-line bg-cs-band">
            <Json />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------------- The app ---------------- */

const APP_POINTS = [
  ["What is on your route.", "Incidents, closures, chain controls and reports along it, spoken a distance ahead that you set for each kind."],
  ["Reports from the road.", "One tap to report a crash, a hazard or a closure. Reports snap to the road and show on the map for everyone."],
  ["The same account.", "Sign in with Google or Apple; watch areas, saved places and plugins follow you."],
];

export function DriveBand() {
  return (
    <section aria-labelledby="drive-title" className="overflow-hidden border-t border-cs-line bg-cs-surface py-20 md:py-28">
      <div className="cs-container grid items-center gap-14 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-6">
          <p className="cs-eyebrow">iPhone and Android</p>
          <h2 id="drive-title" className="cs-h2 mt-4">
            Take the live map on the road.
          </h2>
          <p className="cs-lede mt-5 max-w-[34rem]">
            CommuteScout Drive is turn-by-turn navigation with the same official alerts as this
            site, spoken before you reach them.
          </p>
          <ul className="mt-8 space-y-4 border-l border-cs-line pl-5">
            {APP_POINTS.map(([b, t]) => (
              <li key={b} className="text-[0.9375rem] leading-relaxed text-cs-ink-2">
                <span className="font-medium text-cs-ink">{b}</span> {t}
              </li>
            ))}
          </ul>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <a
              href={TESTFLIGHT_PUBLIC}
              className="inline-flex h-11 items-center gap-2 rounded-[var(--cs-radius-md)] bg-cs-ink px-4 text-[0.9375rem] font-medium text-cs-bg transition-opacity hover:opacity-90"
            >
              <Apple aria-hidden className="size-4" />
              iPhone beta
            </a>
            <a
              href={ANDROID_RELEASES}
              className="inline-flex h-11 items-center gap-2 rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface px-4 text-[0.9375rem] font-medium text-cs-ink transition-colors hover:bg-cs-surface-2"
            >
              <Smartphone aria-hidden className="size-4" />
              Android APK
            </a>
            <Link href="/app" prefetch={false} className="cs-link ml-1 text-[0.9375rem]">
              What the app does
            </Link>
          </div>
          {TESTFLIGHT_IN_REVIEW && <p className="mt-4 max-w-md text-sm text-cs-ink-3">{TESTFLIGHT_IN_REVIEW_NOTE}</p>}
          <p className="mt-4 text-sm text-cs-ink-3">Free while in beta. Open source.</p>
        </div>

        <div className="relative lg:col-span-6">
          <div className="flex items-end justify-center gap-5 sm:gap-7">
            <PhoneShot
              src="/shots/app/android-map.webp"
              alt="CommuteScout Drive on Android: the live map around the driver with a closure marked"
              width={220}
              className="mb-10 hidden sm:block"
            />
            <PhoneShot
              src="/shots/app/ios-nav.webp"
              alt="CommuteScout Drive on iPhone: navigating with the next turn, the speed limit and the arrival time"
              width={250}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------------- Developers ---------------- */

const MCP_URL = "https://mcp.commutescout.com/mcp";

// The band's lede comes from app/page.tsx so the tool count sits in a
// page file, where tests/test_snapshot.py checks it against the registry.
export function DeveloperBand({ children }: { children: React.ReactNode }) {
  return (
    <section aria-labelledby="dev-title" className="bg-cs-band text-cs-band-ink">
      <div className="cs-container grid gap-12 py-20 [&>*]:min-w-0 md:py-24 lg:grid-cols-12 lg:items-center lg:gap-10">
        <div className="lg:col-span-6">
          <p className="cs-eyebrow text-cs-band-ink-2">For developers: MCP and REST</p>
          <h2 id="dev-title" className="cs-h2 mt-4 text-cs-band-ink">
            Live roads for your assistant, or your code.
          </h2>
          <p className="mt-5 max-w-[34rem] text-[1.0625rem] leading-relaxed text-cs-band-ink-2">
            {children}
          </p>
        </div>
        <div className="lg:col-span-6">
          <CopyField value={MCP_URL} label="MCP server URL" />
          <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
            <Link
              href="/mcp#connect"
              prefetch={false}
              className="inline-flex h-11 items-center gap-1.5 rounded-[var(--cs-radius-md)] bg-cs-accent px-4 text-[0.9375rem] font-medium text-cs-accent-ink transition-colors hover:bg-cs-accent-hover"
            >
              Set up your assistant
            </Link>
            <Link
              href="/developers"
              prefetch={false}
              className="inline-flex items-center gap-1 text-[0.9375rem] font-medium text-cs-band-ink hover:underline hover:underline-offset-4"
            >
              REST API reference
              <ArrowUpRight aria-hidden className="size-4 text-cs-band-ink-2" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
