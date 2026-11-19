// The homepage hero picture: a made-up area (Home, Work, an interstate up
// to "the pass") with three sample events, each shown the way CommuteScout
// shows one: what it is, where, and which feed said so and when. It is an
// illustration, labelled as one, with no real place in it.
//
// Pure server markup and CSS: no JavaScript, so the static state is the
// whole picture. Below sm the three event cards drop under the drawing as
// a list; from sm they sit on the drawing next to their markers.

type Kind = "incident" | "closure" | "chain";

const EVENTS: {
  kind: Kind;
  tag: string;
  title: string;
  detail: string;
  source: string;
  age: string;
  /** Card position on the drawing, from sm up (percent of the frame). */
  pos: { left?: string; right?: string; top?: string; bottom?: string };
  marker: number;
}[] = [
  {
    kind: "chain",
    tag: "Chain control",
    title: "Interstate over the pass",
    detail: "Chains or snow tires required",
    source: "State DOT chain controls",
    age: "3 min ago",
    pos: { right: "2.5%", top: "31%" },
    marker: 3,
  },
  {
    kind: "incident",
    tag: "Crash",
    title: "Interstate at Mile 38",
    detail: "Right lane blocked",
    source: "Highway patrol log",
    age: "2 min ago",
    pos: { left: "43%", top: "56%" },
    marker: 2,
  },
  {
    kind: "closure",
    tag: "Ramp closed",
    title: "Exit 14 off-ramp",
    detail: "Ramp only; the interstate stays open",
    source: "State DOT lane closures",
    age: "6 min ago",
    pos: { left: "2.5%", bottom: "2.5%" },
    marker: 1,
  },
];

const tone: Record<Kind, string> = {
  incident: "bg-cs-incident-soft text-cs-incident",
  closure: "bg-cs-closure-soft text-cs-closure",
  chain: "bg-cs-chain-soft text-cs-chain",
};
const dot: Record<Kind, string> = {
  incident: "bg-cs-incident",
  closure: "bg-cs-closure",
  chain: "bg-cs-chain",
};

// The interstate. The route (accent) is the same path, shown from 11% to
// 63% of its length with a dash pattern, so it sits exactly on the road.
const INTERSTATE = "M0,330 C120,320 200,270 290,230 S470,120 600,90";

function Marker({ x, y, color, n }: { x: number; y: number; color: string; n: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle r="13" fill={`color-mix(in srgb, ${color} 18%, transparent)`} />
      <circle r="7.5" fill={color} stroke="var(--cs-surface)" strokeWidth="2.5" />
      <text
        y="0.5"
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize="8"
        fontWeight="700"
        fill="var(--cs-surface)"
        fontFamily="var(--cs-font-mono)"
      >
        {n}
      </text>
    </g>
  );
}

export function HeroScene() {
  const streetsV = [70, 150, 230, 380, 460];
  const streetsH = [70, 150, 390];
  return (
    <figure className="relative">
      <div className="relative overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface-2 shadow-[var(--cs-shadow-md)] sm:aspect-[600/460]">
        <svg
          viewBox="0 0 600 460"
          className="block h-auto w-full sm:absolute sm:inset-0 sm:h-full"
          role="img"
          aria-label="Illustration of a made-up area: a route from Home to Work runs along an interstate, with a closed off-ramp at Exit 14, a crash at Mile 38 on the route, and chain controls on the interstate over the pass."
        >
          {/* water */}
          <path d="M408,460 C430,384 512,334 600,322 L600,460 Z" fill="color-mix(in srgb, var(--cs-accent) 9%, var(--cs-surface-2))" />
          {/* streets */}
          <g stroke="var(--cs-surface)" strokeWidth="7" strokeLinecap="round">
            {streetsV.map((x) => (
              <line key={`v${x}`} x1={x} y1="-10" x2={x} y2="470" />
            ))}
            {streetsH.map((y) => (
              <line key={`h${y}`} x1="-10" y1={y} x2="610" y2={y} />
            ))}
          </g>
          {/* blocks between streets get a hairline to read as a map */}
          <g fill="none" stroke="var(--cs-line)" strokeWidth="1">
            {streetsV.map((x) => (
              <line key={`hv${x}`} x1={x + 4.5} y1="-10" x2={x + 4.5} y2="470" />
            ))}
          </g>
          {/* the pass: terrain with contours */}
          <path
            d="M430,0 L600,0 L600,208 C560,214 520,196 492,170 C462,142 446,96 438,54 Z"
            fill="color-mix(in srgb, var(--cs-ok) 10%, var(--cs-surface-2))"
          />
          <g fill="none" stroke="color-mix(in srgb, var(--cs-ok) 26%, var(--cs-surface-2))" strokeWidth="1">
            <path d="M462,0 C470,60 500,118 552,150 C568,160 584,164 600,166" />
            <path d="M500,0 C506,46 528,86 566,110 C578,117 590,121 600,122" />
            <path d="M540,0 C546,30 562,56 600,74" />
          </g>
          <text x="582" y="28" textAnchor="end" fontSize="12" fill="var(--cs-ink-3)" fontFamily="var(--cs-font-mono)">
            the pass
          </text>
          {/* interstate: casing, road, then the route on top */}
          <path d={INTERSTATE} fill="none" stroke="var(--cs-line-strong)" strokeWidth="17" strokeLinecap="round" />
          <path d={INTERSTATE} fill="none" stroke="var(--cs-surface)" strokeWidth="12" strokeLinecap="round" />
          {/* closed off-ramp at Exit 14 */}
          <path d="M206,270 C222,288 229,304 230,330" fill="none" stroke="var(--cs-line-strong)" strokeWidth="9" strokeLinecap="round" />
          <path
            d="M206,270 C222,288 229,304 230,330"
            fill="none"
            stroke="var(--cs-closure)"
            strokeWidth="4"
            strokeDasharray="5 4"
            strokeLinecap="round"
          />
          {/* the route: Home down to the on-ramp, along the interstate, up to Work */}
          <path d="M70,112 L70,316" fill="none" stroke="var(--cs-accent)" strokeWidth="5" strokeLinecap="round" />
          <path
            d={INTERSTATE}
            pathLength={100}
            fill="none"
            stroke="var(--cs-accent)"
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray="52 48"
            strokeDashoffset={-11}
          />
          <path d="M380,184 L380,82" fill="none" stroke="var(--cs-accent)" strokeWidth="5" strokeLinecap="round" />
          <text x="96" y="298" fontSize="11" fill="var(--cs-ink-3)" fontFamily="var(--cs-font-mono)" transform="rotate(-8 96 298)">
            Interstate
          </text>
          {/* Home and Work */}
          <g>
            <rect x="60" y="94" width="20" height="20" rx="5" fill="var(--cs-ink)" />
            <path d="M65,106 L70,101 L75,106 L75,110 L65,110 Z" fill="var(--cs-surface)" />
            <text x="88" y="109" fontSize="13" fontWeight="600" fill="var(--cs-ink)" fontFamily="var(--cs-font-sans)">
              Home
            </text>
          </g>
          <g>
            <rect x="370" y="62" width="20" height="20" rx="5" fill="var(--cs-ink)" />
            <rect x="375" y="68" width="10" height="9" rx="1.5" fill="var(--cs-surface)" />
            <text x="398" y="77" fontSize="13" fontWeight="600" fill="var(--cs-ink)" fontFamily="var(--cs-font-sans)">
              Work
            </text>
          </g>
          {/* event markers, numbered to match the cards */}
          <Marker x={229} y={318} color="var(--cs-closure)" n={1} />
          <Marker x={300} y={226} color="var(--cs-incident)" n={2} />
          <Marker x={520} y={115} color="var(--cs-chain)" n={3} />
        </svg>

        <ul className="grid gap-2 border-t border-cs-line bg-cs-surface-2 p-3 sm:contents">
          {EVENTS.map((e, i) => (
            <li
              key={e.kind}
              style={{ left: e.pos.left, right: e.pos.right, top: e.pos.top, bottom: e.pos.bottom, animationDelay: `${220 + i * 140}ms` }}
              className="cs-rise rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface p-3 shadow-[var(--cs-shadow-sm)] sm:absolute sm:w-[13rem] sm:p-2.5 sm:shadow-[var(--cs-shadow-md)]"
            >
              <span className="flex items-center gap-2">
                <span
                  aria-hidden
                  className={`cs-data flex size-4 items-center justify-center rounded-full text-[0.625rem] font-bold text-cs-surface ${dot[e.kind]}`}
                >
                  {e.marker}
                </span>
                <span className={`rounded-[var(--cs-radius-sm)] px-1.5 py-0.5 text-[0.6875rem] font-semibold ${tone[e.kind]}`}>
                  {e.tag}
                </span>
                <span className="cs-data ml-auto text-[0.6875rem] text-cs-ink-3">{e.age}</span>
              </span>
              <span className="mt-2 block text-[0.8125rem] font-semibold leading-snug text-cs-ink">{e.title}</span>
              <span className="block text-[0.8125rem] leading-snug text-cs-ink-2">{e.detail}</span>
              <span className="cs-data mt-2 block border-t border-dashed border-cs-line pt-1.5 text-[0.6875rem] text-cs-ink-3">
                {e.source}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <figcaption className="mt-3 text-[0.8125rem] text-cs-ink-3">
        Illustration: a made-up area with sample events.
      </figcaption>
    </figure>
  );
}
