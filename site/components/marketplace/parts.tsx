import {
  Ban,
  Camera,
  CarFront,
  Check,
  CloudRain,
  Gauge,
  Link as LinkIcon,
  Lock,
  MapPin,
  Puzzle,
  Shield,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  Users,
  type LucideIcon,
} from "lucide-react";
import { US_NATION, US_STATES, US_VIEWBOX } from "@/components/figures/us-map.geo";
import { project } from "@/components/home/albers";
import { GROUP_META, coverageLabel, groupsOf, mainGroup, operatorOf, tierOf, type Group, type Source, type Tier } from "./data";

export const GROUP_ICON: Record<Group, LucideIcon> = {
  crashes: CarFront,
  hazards: TriangleAlert,
  closures: Ban,
  weather: CloudRain,
  chains: LinkIcon,
  jams: Gauge,
  police: Shield,
  cameras: Camera,
  other: Puzzle,
};

export const TIER_META: Record<Tier, { Icon: LucideIcon; badge: string; short: string; shelf: string; why: string }> = {
  approved: {
    Icon: ShieldCheck,
    badge: "Approved by CommuteScout",
    short: "Approved",
    shelf: "Approved by CommuteScout",
    why: "The operator is known and the feed passed review.",
  },
  unreviewed: {
    Icon: ShieldAlert,
    badge: "Public, not reviewed",
    short: "Not reviewed",
    shelf: "Public, not reviewed",
    why: "Passed the conformance check. Run by their operators.",
  },
  private: {
    Icon: Lock,
    badge: "Private",
    short: "Private",
    shelf: "Private, shared with you",
    why: "Unlisted: shared with you by link, not on the catalog.",
  },
};

/** The app-icon tile: coloured by what the plugin mostly shows. */
export function PluginIcon({ s, size = "md" }: { s: Source; size?: "sm" | "md" | "lg" }) {
  const g = mainGroup(s);
  const Icon = g === "crowd" ? Users : GROUP_ICON[g];
  const tone = g === "crowd" ? "traffic" : GROUP_META[g].tone;
  const box = size === "lg" ? "size-14" : size === "sm" ? "size-9" : "size-11";
  const ico = size === "lg" ? "size-7" : size === "sm" ? "size-[18px]" : "size-[22px]";
  return (
    <span
      aria-hidden
      data-tone={tone}
      className={`mk-k inline-flex shrink-0 items-center justify-center rounded-[var(--cs-radius-md)] ${box}`}
    >
      <Icon className={ico} strokeWidth={1.75} />
    </span>
  );
}

export function TrustBadge({ s, compact }: { s: Source; compact?: boolean }) {
  const t = tierOf(s);
  const { Icon, badge, short } = TIER_META[t];
  return (
    <span
      data-tier={t}
      className="mk-t-bg inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium"
    >
      <Icon aria-hidden className="size-3.5" />
      {compact ? short : badge}
    </span>
  );
}

export function KindChips({ s, counts }: { s: Source; counts?: boolean }) {
  const gs = groupsOf(s);
  if (gs.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="What it shows">
      {gs.map(({ group, n }) => {
        const Icon = GROUP_ICON[group];
        return (
          <li
            key={group}
            data-tone={GROUP_META[group].tone}
            className="mk-k inline-flex items-center gap-1.5 rounded-[var(--cs-radius-sm)] px-2 py-0.5 text-xs font-medium"
          >
            <Icon aria-hidden className="size-3.5" />
            {GROUP_META[group].label}
            {counts && <span className="cs-data opacity-75">{n}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/** Compact kind tiles for the list view: icon only, the label goes to screen readers and the tooltip. */
export function KindTiles({ s, max = 6 }: { s: Source; max?: number }) {
  const gs = groupsOf(s);
  if (gs.length === 0) return <span className="text-sm text-cs-ink-3">Not stated</span>;
  const shown = gs.slice(0, gs.length > max ? max - 1 : max);
  const rest = gs.slice(shown.length);
  return (
    <ul className="flex flex-wrap gap-1" aria-label="What it shows">
      {shown.map(({ group }) => {
        const Icon = GROUP_ICON[group];
        return (
          <li
            key={group}
            data-tone={GROUP_META[group].tone}
            title={GROUP_META[group].label}
            className="mk-k inline-flex size-7 items-center justify-center rounded-[var(--cs-radius-sm)]"
          >
            <Icon aria-hidden className="size-4" strokeWidth={1.75} />
            <span className="sr-only">{GROUP_META[group].label}</span>
          </li>
        );
      })}
      {rest.length > 0 && (
        <li
          title={rest.map((r) => GROUP_META[r.group].label).join(", ")}
          className="inline-flex h-7 items-center rounded-[var(--cs-radius-sm)] bg-cs-surface-2 px-1.5 text-xs font-medium text-cs-ink-2"
        >
          <span aria-hidden>+{rest.length}</span>
          <span className="sr-only">{rest.map((r) => GROUP_META[r.group].label).join(", ")}</span>
        </li>
      )}
    </ul>
  );
}

/** A thin strip split by the kinds a plugin sends, in the map's colours. */
export function KindStrip({ s }: { s: Source }) {
  const gs = groupsOf(s);
  if (gs.length === 0) return <div aria-hidden className="h-1 bg-cs-line" />;
  return (
    <div aria-hidden className="flex h-1 gap-px">
      {gs.map(({ group, n }) => (
        <span key={group} data-tone={GROUP_META[group].tone} className="mk-k-bar" style={{ flexGrow: n }} />
      ))}
    </div>
  );
}

export function InstallButton({
  s,
  installed,
  onToggle,
  size = "md",
}: {
  s: Source;
  installed: boolean;
  onToggle: (s: Source) => void;
  size?: "sm" | "md";
}) {
  return (
    <button
      type="button"
      onClick={() => onToggle(s)}
      aria-pressed={installed}
      className={
        "inline-flex shrink-0 items-center justify-center gap-1 rounded-[var(--cs-radius-md)] font-medium transition-colors duration-150 " +
        (size === "sm" ? "h-8 px-3 text-[0.8125rem] " : "h-9 px-4 text-sm ") +
        (installed
          ? "border border-cs-line-strong bg-cs-surface text-cs-ink hover:bg-cs-surface-2"
          : "bg-cs-accent text-cs-accent-ink hover:bg-cs-accent-hover")
      }
    >
      {installed && <Check className="size-4" aria-hidden />}
      {installed ? "Installed" : "Install"}
      <span className="sr-only">: {s.name}</span>
    </button>
  );
}

export function MapLink({ s, iconOnly }: { s: Source; iconOnly?: boolean }) {
  return (
    <a
      href={`/map?plugin=${encodeURIComponent(s.id)}`}
      className={
        iconOnly
          ? "inline-flex size-8 shrink-0 items-center justify-center rounded-[var(--cs-radius-md)] text-cs-ink-3 transition-colors hover:bg-cs-surface-2 hover:text-cs-accent"
          : "inline-flex min-h-6 items-center gap-1 text-sm font-medium text-cs-accent hover:underline"
      }
      title={iconOnly ? "See it on the map" : undefined}
    >
      <MapPin className="size-4" aria-hidden />
      {iconOnly ? <span className="sr-only">See {s.name} on the map</span> : "See it on the map"}
    </a>
  );
}

export function Operator({ s }: { s: Source }) {
  const name = operatorOf(s);
  return s.attribution?.url ? (
    <a href={s.attribution.url} className="hover:text-cs-accent hover:underline">
      {name}
    </a>
  ) : (
    <>{name}</>
  );
}

/** The bounding box's outline in map pixels, sampled along each edge so
 * the conic projection's curved parallels are followed. */
function boxPolygon([south, west, north, east]: number[]): [number, number][] {
  const pts: [number, number][] = [];
  const steps = 24;
  for (let i = 0; i <= steps; i++) pts.push(project(south, west + ((east - west) * i) / steps));
  for (let i = 0; i <= steps; i++) pts.push(project(south + ((north - south) * i) / steps, east));
  for (let i = steps; i >= 0; i--) pts.push(project(north, west + ((east - west) * i) / steps));
  for (let i = steps; i >= 0; i--) pts.push(project(south + ((north - south) * i) / steps, west));
  return pts;
}

function inside([x, y]: [number, number], poly: [number, number][]): boolean {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

/** A state map with the states the plugin covers filled in: every state
 * when it covers the whole country, otherwise the states whose centre
 * falls inside its stated area. */
export function CoverageMap({ s, className = "" }: { s: Source; className?: string }) {
  const label = coverageLabel(s.coverage);
  const whole = label === "Whole country";
  const box = !whole && s.coverage && s.coverage.length === 4 ? boxPolygon(s.coverage) : null;
  return (
    <svg viewBox={US_VIEWBOX} className={className} role="img" aria-label={`Coverage: ${label}`}>
      <g strokeWidth={0.75} strokeLinejoin="round">
        {US_STATES.map((st) => {
          const on = whole || (box ? inside(st.c, box) : false);
          return (
            <path
              key={st.id}
              d={st.d}
              className={on ? "fill-cs-accent-soft stroke-cs-accent/50" : "fill-cs-surface-2 stroke-cs-line-strong"}
            />
          );
        })}
      </g>
      <path d={US_NATION} fill="none" className={whole ? "stroke-cs-accent" : "stroke-cs-line-strong"} strokeWidth={1.25} strokeLinejoin="round" />
    </svg>
  );
}
