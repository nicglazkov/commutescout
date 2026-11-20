import Link from "next/link";
import { ArrowRight, ArrowUpRight, Bell, Navigation, Volume2 } from "lucide-react";
import { BrandMark } from "@/components/brand/brand-mark";
import { InstallButton } from "@/components/brand/app-install";
import { PhoneShot } from "@/components/phone-shot";
import { CopyField } from "@/components/copy-field";
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";
import { TESTFLIGHT_IN_REVIEW, TESTFLIGHT_IN_REVIEW_NOTE } from "@/lib/app-links";

// Homepage sections below the hero. Each claim is checked against the code:
// - map rebuilt about every 30 s: src/ca_roads_demo/snapshot.py (live.json.gz, 30 s)
// - watch alerts: WATCH_KINDS = incident, closure, chain, fire (src/ca_roads_demo/watch.py)
// - nationwide layers (NWS alerts, wildfires, traffic overlay) and the
//   per-state layers: docs/state-coverage.md, mirrored in lib/state-coverage.ts
// - 18 MCP tools: @mcp.tool in src/ca_roads_mcp/server.py
// - 2,000 requests a day per account on a free key: site/app/developers

/* ---------------- What you can do ---------------- */

const WAYS = [
  {
    n: "01",
    title: "Live map",
    body: "Incidents, closures, chain controls, cameras and wildfires, updated about every 30 seconds.",
    href: "/map",
    cta: "Open the map",
  },
  {
    n: "02",
    title: "Route planner",
    body: "Compare routes with everything reported along each one. Export to GPX or KML.",
    href: "/map",
    cta: "Plan a route",
  },
  {
    n: "03",
    title: "Watch areas",
    body: "Draw an area. Get a push or an email when an incident, closure, chain control or fire appears in it.",
    href: "/watch",
    cta: "Set up a watch area",
  },
  {
    n: "04",
    title: "AI assistants",
    body: "Ask Claude or another AI assistant about a drive. It answers from the same official sources.",
    href: "/mcp",
    cta: "Connect an assistant",
  },
];

export function FourWays() {
  return (
    <section aria-labelledby="ways-title" className="border-t border-cs-line py-20 md:py-28">
      <div className="cs-container">
        <h2 id="ways-title" className="cs-h2">
          What you can do
        </h2>
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

/* ---------------- Coverage: what each state gets ---------------- */

const STATS: { value: string; unit?: string; label: string }[] = [
  { value: String(AGENCY_FEED_COUNT), label: "official sources" },
  { value: String(STATE_COUNT), label: "states" },
  { value: "30", unit: "s", label: "between updates" },
];

type Layer = { label: string; dot: string };

const NATIONWIDE: Layer[] = [
  { label: "Weather alerts", dot: "bg-cs-weather" },
  { label: "Wildfires", dot: "bg-cs-fire" },
  { label: "Live traffic", dot: "bg-cs-ok" },
];

const BY_STATE: Layer[] = [
  { label: "Incidents", dot: "bg-cs-incident" },
  { label: "Closures", dot: "bg-cs-closure" },
  { label: "Cameras", dot: "bg-cs-ink-3" },
  { label: "Message signs", dot: "bg-cs-ink-3" },
  { label: "Road weather", dot: "bg-cs-weather" },
  { label: "Chain controls", dot: "bg-cs-chain" },
];

function LayerGroup({ title, note, layers }: { title: string; note: string; layers: Layer[] }) {
  return (
    <div className="px-5 py-6 sm:px-6">
      <h3 className="cs-h3">{title}</h3>
      <p className="mt-1 text-sm text-cs-ink-3">{note}</p>
      <ul className="mt-4 flex flex-wrap gap-2">
        {layers.map((l) => (
          <li
            key={l.label}
            className="inline-flex items-center gap-2 rounded-full border border-cs-line bg-cs-bg px-3 py-1.5 text-sm text-cs-ink"
          >
            <span aria-hidden className={`size-2 rounded-full ${l.dot}`} />
            {l.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Coverage() {
  return (
    <section aria-labelledby="coverage-title" className="border-t border-cs-line bg-cs-surface-2/50 py-20 md:py-28">
      <div className="cs-container grid gap-12 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-5">
          <h2 id="coverage-title" className="cs-h2">
            Clear answers, state by state
          </h2>
          <p className="cs-lede mt-5 max-w-[30rem]">
            Road reports come from each state&rsquo;s own agencies. Weather alerts, wildfires and
            live traffic cover the whole country.
          </p>
          <Link href="/data-sources" prefetch={false} className="cs-link mt-7 inline-flex min-h-6 items-center gap-1 text-[0.9375rem]">
            See the sources for each state
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
                <dd aria-hidden className="mt-2 text-[0.8125rem] leading-snug text-cs-ink-3">{s.label}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-4 divide-y divide-cs-line overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface">
            <LayerGroup title="Everywhere in the US" note="From national weather and wildfire agencies, and a live traffic service." layers={NATIONWIDE} />
            <LayerGroup
              title={`In ${STATE_COUNT} states`}
              note="From each state's own agencies, as much as each one publishes."
              layers={BY_STATE}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------------- The app ---------------- */

// Each line matches the app: spoken alerts per kind with a lead distance,
// routing around closures with alternates, watch-area pushes (see /app).
const DRIVE_POINTS = [
  { icon: Volume2, text: "Closures, chain controls, crashes and reports on your route, read out before you reach them." },
  { icon: Navigation, text: "Turn-by-turn directions that route around closures, with alternates to pick from." },
  { icon: Bell, text: "A push notification when something new appears in one of your watch areas." },
];

export function DriveBand() {
  return (
    <section aria-labelledby="drive-title" className="overflow-hidden border-t border-cs-line bg-cs-surface">
      <div className="cs-container grid grid-cols-1 items-center gap-12 py-20 md:py-24 lg:grid-cols-12 lg:gap-10 lg:py-0">
        <div className="lg:col-span-6 lg:py-24">
          <p className="flex items-center gap-2.5">
            <BrandMark className="size-8" />
            <span className="cs-eyebrow">CommuteScout Drive</span>
          </p>
          <h2 id="drive-title" className="cs-h2 mt-5">
            Also on iPhone and Android
          </h2>
          <p className="cs-lede mt-5 max-w-[32rem]">
            The same live road data, with turn-by-turn directions and alerts spoken ahead of
            time. Free while in beta.
          </p>
          <ul className="mt-8 max-w-[32rem] space-y-4">
            {DRIVE_POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3.5 text-[0.9375rem] leading-relaxed text-cs-ink-2">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-[var(--cs-radius-md)] bg-cs-accent-soft text-cs-accent">
                  <Icon aria-hidden className="size-4" strokeWidth={2} />
                </span>
                <span className="pt-1">{text}</span>
              </li>
            ))}
          </ul>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <InstallButton platform="ios" />
            <InstallButton platform="android" />
          </div>
          {TESTFLIGHT_IN_REVIEW && <p className="mt-3 text-sm text-cs-ink-3">{TESTFLIGHT_IN_REVIEW_NOTE}</p>}
          <Link href="/app" prefetch={false} className="cs-link mt-6 inline-flex min-h-6 items-center gap-1 text-[0.9375rem]">
            Features, screenshots and install steps
            <ArrowRight aria-hidden className="size-3.5" />
          </Link>
        </div>

        {/* Two real screenshots, one per platform, rising out of a tinted
            panel that runs to the section's bottom edge. */}
        <div className="min-w-0 lg:col-span-6 lg:self-stretch lg:pt-16">
          <div className="relative flex h-full min-h-[24rem] items-start justify-center gap-5 overflow-hidden rounded-t-[calc(var(--cs-radius-lg)+8px)] border border-b-0 border-cs-line bg-cs-accent-soft px-6 pt-10 sm:gap-7 sm:pt-12">
            <PhoneShot
              src="/shots/app/ios-alert.webp"
              alt="CommuteScout Drive on iPhone: a reported hazard ahead on the route, with how far ahead it is"
              width={270}
              className="-mb-28 w-[47%]"
            />
            <PhoneShot
              src="/shots/app/android-nav.webp"
              alt="CommuteScout Drive on Android: a closure ahead on the route in an alert strip above the arrival time"
              width={270}
              className="-mb-44 mt-14 w-[47%]"
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
    <section aria-labelledby="dev-title" className="border-y border-cs-band-line bg-cs-band text-cs-band-ink">
      <div className="cs-container grid gap-12 py-20 [&>*]:min-w-0 md:py-24 lg:grid-cols-12 lg:items-center lg:gap-10">
        <div className="lg:col-span-6">
          <h2 id="dev-title" className="cs-h2 text-cs-band-ink">
            For developers
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
