import {
  Ban,
  Camera,
  CarFront,
  CloudRain,
  Gauge,
  Link as LinkIcon,
  Puzzle,
  Shield,
  ShieldCheck,
  TriangleAlert,
  Users,
  type LucideIcon,
} from "lucide-react";
import { US_NATION, US_VIEWBOX } from "@/components/figures/us-map.geo";
import { PLUGINS, type Plugin } from "./plugins-snapshot";

// Shared helpers for the marketplace lab board. Grouping follows
// components/marketplace.tsx (kindsLabel) so every option reads the real
// catalog the same way the live page does.

export const SNAP_AT = Date.parse("2026-11-20T00:35:00Z");

export type Group =
  | "police"
  | "crashes"
  | "hazards"
  | "jams"
  | "closures"
  | "weather"
  | "cameras"
  | "chain controls"
  | "other";

export function groupOf(kind: string): Group {
  if (kind.startsWith("POLICE")) return "police";
  if (kind.startsWith("CRASH")) return "crashes";
  if (kind.startsWith("HAZARD")) return "hazards";
  if (kind.startsWith("JAM")) return "jams";
  if (kind.startsWith("ROAD_CLOSED") || kind.startsWith("LANE")) return "closures";
  if (kind.startsWith("WEATHER")) return "weather";
  if (kind.startsWith("CAMERA")) return "cameras";
  if (kind.startsWith("CHAINS")) return "chain controls";
  return "other";
}

/** Groups in a fixed display order, each with the raw kinds it covers. */
export function groupsOf(p: Plugin): { group: Group; kinds: string[] }[] {
  const m = new Map<Group, string[]>();
  for (const k of p.kinds) {
    const g = groupOf(k);
    m.set(g, [...(m.get(g) || []), k]);
  }
  return ORDER.filter((g) => m.has(g)).map((g) => ({ group: g, kinds: m.get(g)! }));
}

export const ORDER: Group[] = ["crashes", "hazards", "closures", "weather", "chain controls", "police", "jams", "cameras", "other"];

// Semantic colours only where the group is the road event that colour means
// on the live map. Everything else stays neutral and is told apart by its icon.
export const GROUP_STYLE: Record<Group, { Icon: LucideIcon; label: string; text: string; soft: string; dot: string }> = {
  crashes: { Icon: CarFront, label: "Crashes", text: "text-cs-incident", soft: "bg-cs-incident-soft", dot: "bg-cs-incident" },
  hazards: { Icon: TriangleAlert, label: "Hazards", text: "text-cs-incident", soft: "bg-cs-incident-soft", dot: "bg-cs-incident" },
  closures: { Icon: Ban, label: "Closures", text: "text-cs-closure", soft: "bg-cs-closure-soft", dot: "bg-cs-closure" },
  weather: { Icon: CloudRain, label: "Weather", text: "text-cs-weather", soft: "bg-cs-weather-soft", dot: "bg-cs-weather" },
  "chain controls": { Icon: LinkIcon, label: "Chain controls", text: "text-cs-chain", soft: "bg-cs-chain-soft", dot: "bg-cs-chain" },
  police: { Icon: Shield, label: "Police", text: "text-cs-ink-2", soft: "bg-cs-surface-2", dot: "bg-cs-ink-3" },
  jams: { Icon: Gauge, label: "Jams", text: "text-cs-ink-2", soft: "bg-cs-surface-2", dot: "bg-cs-ink-3" },
  cameras: { Icon: Camera, label: "Cameras", text: "text-cs-ink-2", soft: "bg-cs-surface-2", dot: "bg-cs-ink-3" },
  other: { Icon: Puzzle, label: "Other", text: "text-cs-ink-2", soft: "bg-cs-surface-2", dot: "bg-cs-ink-3" },
};

export function coverageLabel(b: number[]): string {
  if (b.length !== 4) return "Coverage not stated";
  const [s, w, n, e] = b;
  if (n - s >= 20 && e - w >= 50) return "Whole country";
  return `${Math.round(n - s)}° by ${Math.round(e - w)}° area`;
}

export function refreshLabel(s: number): string {
  if (s <= 60) return "Every minute";
  if (s < 3600) return `Every ${Math.round(s / 60)} min`;
  if (s === 3600) return "Every hour";
  return `Every ${Math.round(s / 3600)} h`;
}

export function agoLabel(iso: string): string {
  const m = Math.max(0, Math.round((SNAP_AT - Date.parse(iso)) / 60000));
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  return `${Math.round(m / 60)} h ago`;
}

export function operatorOf(p: Plugin): string {
  return p.attribution.name && p.attribution.name !== p.name ? p.attribution.name : "Run by its community";
}

export const approved = (p: Plugin) => p.tier === "approved";

/** The category that picks a plugin's icon, as on the live page. */
export function mainCategory(p: Plugin): "cameras" | "crowd" | "other" {
  if (p.kinds.length > 0 && p.kinds.every((k) => k.startsWith("CAMERA"))) return "cameras";
  if (p.kinds.some((k) => /^(POLICE|CRASH|HAZARD)/.test(k))) return "crowd";
  return "other";
}

export function PluginGlyph({ p, size = 48 }: { p: Plugin; size?: number }) {
  const cat = mainCategory(p);
  const Icon = cat === "cameras" ? Camera : cat === "crowd" ? Users : Puzzle;
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface-2 text-cs-ink-2"
      style={{ width: size, height: size }}
    >
      <Icon style={{ width: size / 2, height: size / 2 }} strokeWidth={1.75} />
    </span>
  );
}

export function TrustBadge({ p, compact }: { p: Plugin; compact?: boolean }) {
  return approved(p) ? (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-cs-ok-soft px-2.5 py-0.5 text-xs font-medium text-cs-ok">
      <ShieldCheck aria-hidden className="size-3.5" />
      {compact ? "Approved" : "Approved by CommuteScout"}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-cs-line-strong px-2.5 py-0.5 text-xs font-medium text-cs-ink-2">
      {compact ? "Not reviewed" : "Public, not reviewed"}
    </span>
  );
}

export function KindChip({ group, n }: { group: Group; n?: number }) {
  const s = GROUP_STYLE[group];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-[var(--cs-radius-sm)] px-2 py-0.5 text-xs font-medium ${s.soft} ${s.text}`}>
      <s.Icon aria-hidden className="size-3.5" />
      {s.label}
      {n !== undefined && <span className="cs-data opacity-80">{n}</span>}
    </span>
  );
}

export function NotReviewedNote() {
  return (
    <p className="text-xs leading-relaxed text-cs-ink-3">
      Not reviewed by CommuteScout. Its alerts come from its operator, not from official sources. It alerts only
      after you tick that notice at install, and only in the apps.
    </p>
  );
}

/** The whole-country coverage box drawn on the real state outline. */
export function MiniUS({ p, className = "" }: { p: Plugin; className?: string }) {
  const whole = coverageLabel(p.coverage) === "Whole country";
  return (
    <svg viewBox={US_VIEWBOX} className={className} role="img" aria-label={`Coverage: ${coverageLabel(p.coverage)}`}>
      <path d={US_NATION} className={whole ? "fill-cs-accent-soft stroke-cs-accent" : "fill-cs-surface-2 stroke-cs-line-strong"} strokeWidth={1.5} />
    </svg>
  );
}

export { PLUGINS };
export type { Plugin };
