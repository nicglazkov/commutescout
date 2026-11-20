// Mock UI parts for the sidebar mockups. Non-interactive: every mockup is
// rendered inside an inert, aria-hidden "screen" (see scaled.tsx).
import {
  ArrowUpDown,
  Ban,
  Camera,
  ChevronDown,
  CloudRain,
  Crosshair,
  Flame,
  Layers,
  LocateFixed,
  Minus,
  Plus,
  Search,
  Signpost,
  Snowflake,
  TriangleAlert,
  X,
  type LucideIcon,
} from "lucide-react";
import type { MarkerKind } from "./map-bg";

export const KIND_ICON: Record<MarkerKind, LucideIcon> = {
  incident: TriangleAlert,
  closure: Ban,
  chain: Snowflake,
  fire: Flame,
  weather: CloudRain,
  camera: Camera,
  sign: Signpost,
};
const KIND_BG: Record<MarkerKind, string> = {
  incident: "bg-cs-incident-soft text-cs-incident",
  closure: "bg-cs-closure-soft text-cs-closure",
  chain: "bg-cs-chain-soft text-cs-chain",
  fire: "bg-cs-fire-soft text-cs-fire",
  weather: "bg-cs-weather-soft text-cs-weather",
  camera: "bg-cs-surface-2 text-cs-ink-2",
  sign: "bg-cs-stale-soft text-cs-stale",
};

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Logo({ size = 22 }: { size?: number }) {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src="/logo.svg" alt="" width={size} height={size} className="shrink-0" />;
}

/** The site's top bar, slimmed. */
export function TopBar({ right = true, nav = true }: { right?: boolean; nav?: boolean }) {
  return (
    <div className="flex h-12 items-center gap-6 bg-cs-band px-4 text-[13px] text-cs-band-ink">
      <span className="flex items-center gap-2 font-semibold">
        <Logo /> CommuteScout
      </span>
      {nav ? (
        <span className="flex gap-5 text-cs-band-ink-2">
          <span>Data sources</span>
          <span>Developers</span>
          <span>MCP server</span>
          <span>Get the app</span>
          <span>Pricing</span>
        </span>
      ) : null}
      {right ? (
        <span className="ml-auto flex items-center gap-3">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-cs-band-2 text-[11px] font-semibold text-cs-band-ink">
            JD
          </span>
        </span>
      ) : null}
    </div>
  );
}

export function Kicker({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={cx("font-mono text-[10.5px] uppercase tracking-[0.1em] text-cs-ink-3", className)}>{children}</div>;
}

export function SearchBox({
  placeholder = "Search a place or get directions",
  value,
  className = "",
  trailing,
  float = false,
}: {
  placeholder?: string;
  value?: string;
  className?: string;
  trailing?: React.ReactNode;
  float?: boolean;
}) {
  return (
    <div
      className={cx(
        "flex h-11 items-center gap-2.5 rounded-[10px] border border-cs-line bg-cs-surface px-3.5",
        float && "msb-float border-transparent",
        className,
      )}
    >
      <Search size={16} className="shrink-0 text-cs-ink-3" />
      <span className={cx("min-w-0 flex-1 truncate", value ? "text-cs-ink" : "text-cs-ink-3")}>{value ?? placeholder}</span>
      {trailing}
    </div>
  );
}

/** A/B route field. */
export function Field({
  end,
  value,
  placeholder,
  focused = false,
  picking = false,
}: {
  end: "a" | "b" | "stop";
  value?: string;
  placeholder?: string;
  focused?: boolean;
  picking?: boolean;
}) {
  return (
    <div
      className={cx(
        "flex h-10 items-center gap-2.5 rounded-[8px] border bg-cs-surface px-3",
        focused || picking ? "border-cs-accent msb-pulse" : "border-cs-line",
      )}
    >
      <EndDot end={end} />
      {picking ? (
        <span className="flex items-center gap-1.5 text-cs-accent">
          <Crosshair size={14} /> Choosing on map…
        </span>
      ) : (
        <span className={cx("min-w-0 flex-1 truncate", value ? "text-cs-ink" : "text-cs-ink-3")}>{value ?? placeholder}</span>
      )}
      {value && focused ? <X size={14} className="ml-auto text-cs-ink-3" /> : null}
    </div>
  );
}

export function EndDot({ end }: { end: "a" | "b" | "stop" }) {
  if (end === "a") return <span className="h-3 w-3 shrink-0 rounded-full border-[3px] border-cs-ink bg-cs-surface" />;
  if (end === "b") return <span className="h-3 w-3 shrink-0 rounded-full bg-cs-closure ring-2 ring-cs-surface" />;
  return <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-cs-ink-3" />;
}

/** Stacked From/To pair with the dotted connector and a swap button. */
export function FromTo({
  from = "Home",
  to,
  toPlaceholder = "Where to?",
  fromPlaceholder = "Starting point",
  focusTo = false,
  pickingTo = false,
  swap = true,
}: {
  from?: string;
  to?: string;
  toPlaceholder?: string;
  fromPlaceholder?: string;
  focusTo?: boolean;
  pickingTo?: boolean;
  swap?: boolean;
}) {
  return (
    <div className="relative flex gap-2">
      <div className="flex flex-1 flex-col gap-2">
        <Field end="a" value={from || undefined} placeholder={fromPlaceholder} />
        <Field end="b" value={to} placeholder={toPlaceholder} focused={focusTo} picking={pickingTo} />
      </div>
      {swap ? (
        <div className="grid w-8 place-items-center">
          <span className="grid h-8 w-8 place-items-center rounded-full border border-cs-line bg-cs-surface text-cs-ink-2">
            <ArrowUpDown size={14} />
          </span>
        </div>
      ) : null}
      <span className="absolute left-[17px] top-[30px] h-[20px] border-l-2 border-dotted border-cs-line-strong" />
    </div>
  );
}

export function Chip({
  icon: Icon,
  children,
  active = false,
  tone,
  className = "",
}: {
  icon?: LucideIcon;
  children: React.ReactNode;
  active?: boolean;
  tone?: MarkerKind;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 text-[12.5px]",
        active ? "border-cs-accent bg-cs-accent-soft text-cs-accent" : "border-cs-line bg-cs-surface text-cs-ink",
        className,
      )}
    >
      {tone ? <span className={cx("h-2 w-2 rounded-full", DOT[tone])} /> : null}
      {Icon ? <Icon size={14} className={active ? "" : "text-cs-ink-2"} /> : null}
      {children}
    </span>
  );
}
const DOT: Record<MarkerKind, string> = {
  incident: "bg-cs-incident",
  closure: "bg-cs-closure",
  chain: "bg-cs-chain",
  fire: "bg-cs-fire",
  weather: "bg-cs-weather",
  camera: "bg-cs-ink-3",
  sign: "bg-cs-stale",
};

export function Btn({
  children,
  primary = false,
  icon: Icon,
  className = "",
  small = false,
}: {
  children?: React.ReactNode;
  primary?: boolean;
  icon?: LucideIcon;
  className?: string;
  small?: boolean;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[8px] font-medium",
        small ? "h-8 px-3 text-[12.5px]" : "h-10 px-4",
        primary ? "bg-cs-accent text-cs-accent-ink" : "border border-cs-line bg-cs-surface text-cs-ink",
        className,
      )}
    >
      {Icon ? <Icon size={small ? 14 : 15} /> : null}
      {children}
    </span>
  );
}

export function KindIcon({ k, size = 30 }: { k: MarkerKind; size?: number }) {
  const I = KIND_ICON[k];
  return (
    <span className={cx("grid shrink-0 place-items-center rounded-[8px]", KIND_BG[k])} style={{ width: size, height: size }}>
      <I size={size * 0.5} />
    </span>
  );
}

export function EventRow({
  k,
  title,
  meta,
  right,
  compact = false,
}: {
  k: MarkerKind;
  title: string;
  meta: string;
  right?: React.ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={cx("flex items-start gap-3", compact ? "py-2" : "py-2.5")}>
      <KindIcon k={k} size={compact ? 26 : 30} />
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium text-cs-ink">{title}</div>
        <div className="truncate text-[12px] text-cs-ink-2">{meta}</div>
      </div>
      {right}
    </div>
  );
}

export const EVENTS: { k: MarkerKind; title: string; meta: string }[] = [
  { k: "closure", title: "Full closure, both directions", meta: "State Route near Exit 22 · since 6:10 AM" },
  { k: "incident", title: "Crash blocking right lane", meta: "Interstate at Exit 14 · 12 min ago" },
  { k: "chain", title: "Chains required", meta: "Over the pass · 4WD with snow tires exempt" },
  { k: "incident", title: "Disabled vehicle on shoulder", meta: "Main St at 3rd · 25 min ago" },
  { k: "fire", title: "Wildfire, 2 mi from the road", meta: "42 acres · 10% contained" },
  { k: "sign", title: "Sign: EXPECT DELAYS 20 MIN", meta: "Interstate eastbound · read 2 min ago" },
  { k: "camera", title: "Camera: Interstate at Exit 14", meta: "Live video" },
];

/** Floating map controls, bottom right: locate + zoom. */
export function ZoomCtrls({ className = "" }: { className?: string }) {
  return (
    <div className={cx("absolute bottom-6 right-4 flex flex-col items-end gap-2", className)}>
      <span className="msb-float grid h-10 w-10 place-items-center rounded-[10px] bg-cs-surface text-cs-ink-2">
        <LocateFixed size={18} />
      </span>
      <span className="msb-float flex flex-col overflow-hidden rounded-[10px] bg-cs-surface text-cs-ink-2">
        <span className="grid h-10 w-10 place-items-center border-b border-cs-line">
          <Plus size={18} />
        </span>
        <span className="grid h-10 w-10 place-items-center">
          <Minus size={18} />
        </span>
      </span>
    </div>
  );
}

/** Floating "Layers" button, top right, with a count of hidden layers. */
export function LayersBtn({ className = "", off = 2 }: { className?: string; off?: number }) {
  return (
    <span className={cx("msb-float absolute right-4 top-4 flex h-10 items-center gap-2 rounded-[10px] bg-cs-surface px-3 font-medium", className)}>
      <Layers size={16} className="text-cs-ink-2" /> Layers
      {off ? <span className="rounded-full bg-cs-surface-2 px-1.5 font-mono text-[10.5px] text-cs-ink-2">{off} off</span> : null}
    </span>
  );
}

/** Freshness + sources chip, bottom left of the map. */
export function StatusChip({ className = "", left = 16 }: { className?: string; left?: number }) {
  return (
    <span
      className={cx("msb-float absolute bottom-6 flex h-8 items-center gap-2 rounded-full bg-cs-surface px-3 text-[12px] text-cs-ink-2", className)}
      style={{ left }}
    >
      <span className="h-2 w-2 rounded-full bg-cs-ok" />
      <span>
        Live · updated 12 s ago
      </span>
      <span className="text-cs-ink-3">·</span>
      <span>53 sources</span>
      <ChevronDown size={13} />
    </span>
  );
}

/** Route summary card used by several result states. */
export function RouteSummary({ selected = true, mins = "24 min", alt = false }: { selected?: boolean; mins?: string; alt?: boolean }) {
  return (
    <div className={cx("rounded-[10px] border p-3", selected ? "border-cs-accent bg-cs-accent-soft/40" : "border-cs-line bg-cs-surface")}>
      <div className="flex items-baseline gap-2">
        <span className={cx("text-[17px] font-semibold", alt ? "text-cs-ink" : "text-cs-incident")}>{mins}</span>
        <span className="text-cs-ink-2">{alt ? "13.0 mi" : "11.2 mi"}</span>
        <span className="ml-auto font-mono text-[11px] text-cs-ink-3">{alt ? "usual" : "+6 min vs usual"}</span>
      </div>
      <div className="mt-0.5 text-[12.5px] text-cs-ink-2">{alt ? "via Main St · Clear right now" : "via Interstate · fastest now"}</div>
      {!alt ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          <span className="inline-flex items-center gap-1 rounded-full bg-cs-closure-soft px-2 py-0.5 text-[11.5px] text-cs-closure">
            <Ban size={11} /> 1 closure on the way
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-cs-incident-soft px-2 py-0.5 text-[11.5px] text-cs-incident">
            <TriangleAlert size={11} /> 1 crash
          </span>
        </div>
      ) : null}
    </div>
  );
}

export function Divider({ className = "" }: { className?: string }) {
  return <div className={cx("h-px bg-cs-line", className)} />;
}
