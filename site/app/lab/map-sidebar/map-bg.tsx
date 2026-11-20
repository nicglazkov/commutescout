// A generic, made-up basemap for the mockups: coast, a lake, a town grid,
// two interstates and a highway. No real places. World is 1280 x 800;
// mobile mockups crop the middle with a narrower viewBox.

export type MarkerKind = "incident" | "closure" | "chain" | "fire" | "weather" | "camera" | "sign";

export const MARKERS: { x: number; y: number; k: MarkerKind }[] = [
  { x: 742, y: 404, k: "incident" },
  { x: 902, y: 247, k: "closure" },
  { x: 640, y: 520, k: "camera" },
  { x: 462, y: 300, k: "incident" },
  { x: 700, y: 690, k: "sign" },
  { x: 520, y: 742, k: "closure" },
  { x: 980, y: 520, k: "incident" },
  { x: 1176, y: 300, k: "chain" },
  { x: 1214, y: 380, k: "chain" },
  { x: 1140, y: 132, k: "fire" },
  { x: 860, y: 610, k: "camera" },
  { x: 1050, y: 700, k: "weather" },
  { x: 610, y: 210, k: "sign" },
  { x: 800, y: 120, k: "incident" },
];

const KIND_VAR: Record<MarkerKind, string> = {
  incident: "var(--cs-incident)",
  closure: "var(--cs-closure)",
  chain: "var(--cs-chain)",
  fire: "var(--cs-fire)",
  weather: "var(--cs-weather)",
  camera: "var(--cs-ink-2)",
  sign: "var(--cs-stale)",
};

export function kindColor(k: MarkerKind) {
  return KIND_VAR[k];
}

// The planned route, Home (A) to Work (B). Drawn as a road too, so the
// line always sits on a street.
export const ROUTE_D =
  "M560 610 V490 C640 500 700 470 742 420 C760 360 760 300 800 262 C860 240 940 246 1010 250";
export const ALT_D = "M560 610 H800 C860 600 900 560 940 470 C980 380 990 300 1010 250";
export const A = { x: 560, y: 610 };
export const B = { x: 1010, y: 250 };

function Glyph({ k }: { k: MarkerKind }) {
  const w = { stroke: "#fff", strokeWidth: 1.8, fill: "none", strokeLinecap: "round" as const };
  switch (k) {
    case "incident":
      return (
        <g>
          <path d="M0 -4.5 V1" {...w} />
          <circle r="1.1" cy="3.6" fill="#fff" />
        </g>
      );
    case "closure":
      return <path d="M-4 0 H4" {...w} strokeWidth={2.4} />;
    case "chain":
      return (
        <g {...w} strokeWidth={1.5}>
          <ellipse cx="-2.2" rx="3" ry="2" />
          <ellipse cx="2.2" rx="3" ry="2" />
        </g>
      );
    case "fire":
      return <path d="M0 -5 C3 -2 4 1 2.5 3.5 C1 5 -1 5 -2.5 3.5 C-4 1 -2 -1 0 -5 Z" fill="#fff" />;
    case "weather":
      return <path d="M-4 1.5 C-4 -1 -2 -2.5 0 -2.5 C2 -2.5 3.5 -1 3.5 0.5 C4.8 0.5 5 3 3.5 3 H-3 C-4.5 3 -4.5 1.5 -4 1.5 Z" fill="#fff" />;
    case "camera":
      return (
        <g>
          <rect x="-4.5" y="-3" width="7" height="6" rx="1.2" fill="#fff" />
          <path d="M2.5 -1 L5 -2.5 V2.5 L2.5 1 Z" fill="#fff" />
        </g>
      );
    case "sign":
      return <rect x="-4.5" y="-2.5" width="9" height="5" rx="1" fill="none" stroke="#fff" strokeWidth="1.5" />;
  }
}

export function Marker({ x, y, k, r = 11, ring = false }: { x: number; y: number; k: MarkerKind; r?: number; ring?: boolean }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      {ring ? <circle r={r + 6} style={{ fill: "none", stroke: kindColor(k), strokeWidth: 2, opacity: 0.45 }} /> : null}
      <circle r={r + 1.5} fill="#fff" opacity="0.9" />
      <circle r={r} style={{ fill: kindColor(k) }} />
      <g transform={`scale(${r / 11})`}>
        <Glyph k={k} />
      </g>
    </g>
  );
}

export function PinA({ x = A.x, y = A.y }: { x?: number; y?: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle r="10" style={{ fill: "var(--cs-surface)", stroke: "var(--cs-ink)", strokeWidth: 3.5 }} />
    </g>
  );
}

export function PinB({ x = B.x, y = B.y, color = "var(--cs-closure)", ghost = false }: { x?: number; y?: number; color?: string; ghost?: boolean }) {
  return (
    <g transform={`translate(${x} ${y})`} opacity={ghost ? 0.55 : 1}>
      <ellipse cx="0" cy="1" rx="6" ry="2.4" fill="#000" opacity="0.18" />
      <path d="M0 0 C-3 -9 -13 -16 -13 -27 A13 13 0 1 1 13 -27 C13 -16 3 -9 0 0 Z" style={{ fill: color, stroke: "#fff", strokeWidth: 2 }} />
      <circle cy="-27" r="4.5" fill="#fff" />
    </g>
  );
}

type MapBgProps = {
  viewBox?: string;
  route?: boolean;
  alt?: boolean;
  traffic?: boolean;
  pins?: boolean;
  markers?: boolean | number;
  focus?: number[];
  dim?: boolean;
  labels?: boolean;
  className?: string;
  children?: React.ReactNode;
};

export function MapBg({
  viewBox = "0 0 1280 800",
  route = false,
  alt = false,
  traffic = false,
  pins = route,
  markers = true,
  focus = [],
  dim = false,
  labels = true,
  className = "",
  children,
}: MapBgProps) {
  const vx = [500, 560, 620, 680, 740, 800, 860];
  const hy = [370, 430, 490, 550, 610, 670];
  const list = markers === false ? [] : typeof markers === "number" ? MARKERS.slice(0, markers) : MARKERS;
  return (
    <svg viewBox={viewBox} preserveAspectRatio="xMidYMid slice" className={`absolute inset-0 h-full w-full ${className}`} aria-hidden="true">
      <rect x="-400" y="-400" width="2080" height="1600" style={{ fill: "var(--m-land)" }} />
      {/* town blocks */}
      <rect x="484" y="350" width="400" height="340" rx="10" style={{ fill: "var(--m-block)" }} />
      <rect x="930" y="180" width="170" height="130" rx="10" style={{ fill: "var(--m-block)" }} />
      {/* parks */}
      <path d="M640 120 c40 -20 110 -10 120 30 c10 40 -40 70 -90 60 c-40 -8 -60 -66 -30 -90 z" style={{ fill: "var(--m-park)" }} />
      <path d="M880 650 c50 -24 120 0 118 40 c-2 40 -70 58 -110 40 c-30 -14 -40 -66 -8 -80 z" style={{ fill: "var(--m-park)" }} />
      <path d="M300 80 c60 -30 130 10 120 60 c-10 40 -90 60 -120 30 c-24 -24 -24 -74 0 -90 z" style={{ fill: "var(--m-park)" }} />
      {/* water */}
      <path d="M-400 -400 H210 C250 90 190 170 236 260 C282 350 214 440 262 540 C300 620 236 700 270 1200 H-400 Z" style={{ fill: "var(--m-water)" }} />
      <path d="M1120 470 C1170 430 1250 440 1300 470 V660 C1230 690 1150 680 1118 630 C1090 585 1086 505 1120 470 Z" style={{ fill: "var(--m-water)" }} />
      <path d="M1118 590 C1020 620 980 700 900 820" style={{ fill: "none", stroke: "var(--m-water)", strokeWidth: 12 }} />

      {/* streets */}
      <g style={{ stroke: "var(--m-road-case)", strokeWidth: 5, fill: "none" }}>
        {vx.map((x) => (
          <path key={`vc${x}`} d={`M${x} 340 V720`} />
        ))}
        {hy.map((y) => (
          <path key={`hc${y}`} d={`M470 ${y} H900`} />
        ))}
        <path d="M300 690 C500 680 700 700 1300 722" />
        <path d="M420 -20 C430 200 400 500 450 820" />
        <path d="M940 180 V320 M1000 180 V320 M930 230 H1100 M930 280 H1100" />
        <path d={ROUTE_D} />
        <path d={ALT_D} />
        <path d="M880 300 C960 360 1060 330 1120 300 S1240 260 1300 280" />
      </g>
      <g style={{ stroke: "var(--m-road)", strokeWidth: 3, fill: "none" }}>
        {vx.map((x) => (
          <path key={`v${x}`} d={`M${x} 340 V720`} />
        ))}
        {hy.map((y) => (
          <path key={`h${y}`} d={`M470 ${y} H900`} />
        ))}
        <path d="M300 690 C500 680 700 700 1300 722" />
        <path d="M420 -20 C430 200 400 500 450 820" />
        <path d="M940 180 V320 M1000 180 V320 M930 230 H1100 M930 280 H1100" />
        <path d={ROUTE_D} />
        <path d={ALT_D} />
        <path d="M880 300 C960 360 1060 330 1120 300 S1240 260 1300 280" />
      </g>
      {/* highways */}
      <g style={{ fill: "none", stroke: "var(--m-hwy-case)", strokeWidth: 10, strokeLinecap: "round" }}>
        <path d="M150 470 C420 450 600 520 820 470 S1080 380 1320 400" />
        <path d="M760 -20 C770 160 700 280 740 400 S820 640 780 820" />
        <path d="M200 180 C480 220 820 170 1320 210" />
      </g>
      <g style={{ fill: "none", stroke: "var(--m-hwy)", strokeWidth: 6.5, strokeLinecap: "round" }}>
        <path d="M150 470 C420 450 600 520 820 470 S1080 380 1320 400" />
        <path d="M760 -20 C770 160 700 280 740 400 S820 640 780 820" />
        <path d="M200 180 C480 220 820 170 1320 210" />
      </g>
      {labels ? (
        <g style={{ fill: "var(--m-label)", fontFamily: "var(--cs-font-sans)", fontSize: 11, letterSpacing: "0.04em" }}>
          <text x="1050" y="392" transform="rotate(-4 1050 392)">INTERSTATE</text>
          <text x="772" y="86" transform="rotate(80 772 86)">STATE ROUTE</text>
          <text x="1180" y="560" style={{ fontStyle: "italic" }}>Lake</text>
          <rect x="826" y="455" width="40" height="17" rx="3" style={{ fill: "var(--cs-surface)", stroke: "var(--m-hwy-case)" }} />
          <text x="831" y="467" style={{ fontSize: 10, fill: "var(--cs-ink-2)", letterSpacing: 0 }}>Exit 14</text>
        </g>
      ) : null}

      {dim ? <rect x="-400" y="-400" width="2080" height="1600" style={{ fill: "var(--m-land)", opacity: 0.35 }} /> : null}

      {alt ? <path d={ALT_D} style={{ fill: "none", stroke: "var(--cs-ink-3)", strokeWidth: 6, strokeDasharray: "2 9", strokeLinecap: "round", opacity: 0.8 }} /> : null}
      {route ? (
        <g style={{ fill: "none", strokeLinecap: "round", strokeLinejoin: "round" }}>
          <path d={ROUTE_D} style={{ stroke: "#fff", strokeWidth: 11 }} />
          <path d={ROUTE_D} style={{ stroke: "var(--cs-accent)", strokeWidth: 7 }} />
          {traffic ? (
            <>
              <path d={ROUTE_D} pathLength={100} style={{ stroke: "var(--cs-fire)", strokeWidth: 7, strokeDasharray: "9 200", strokeDashoffset: -29 }} />
              <path d={ROUTE_D} pathLength={100} style={{ stroke: "var(--cs-closure)", strokeWidth: 7, strokeDasharray: "8 200", strokeDashoffset: -37, strokeLinecap: "butt" }} />
            </>
          ) : null}
        </g>
      ) : null}
      {list.map((m, i) => (
        <Marker key={i} {...m} ring={focus.includes(i)} />
      ))}
      {pins ? (
        <>
          <PinA />
          <PinB />
        </>
      ) : null}
      {children}
    </svg>
  );
}
