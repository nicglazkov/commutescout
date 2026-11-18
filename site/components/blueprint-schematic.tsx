import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";

// The Blueprint skin's hero drawing for the developer pages: one block for
// the agency feeds, wired to the two ways in (the MCP server and the REST
// API). Plain inline SVG in the skin's ink color, drawn like a drafting
// sheet: dashed leaders, dimension ticks, mono labels. Decorative; the page
// text says the same thing, so it is hidden from assistive tech.
export function BlueprintSchematic({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 420 260"
      fill="none"
      aria-hidden="true"
      className={className}
      stroke="#e9f0ff"
      strokeOpacity="0.75"
      strokeWidth="1.25"
    >
      {/* Feeds block */}
      <rect x="12" y="88" width="132" height="84" rx="3" />
      <path d="M12 76 V70 M144 76 V70 M12 73 H144" strokeOpacity="0.45" />
      <text x="78" y="64" textAnchor="middle" fill="#9fc0ff" stroke="none" fontSize="10" fontFamily="var(--font-plex-mono)">
        {STATE_COUNT} STATES
      </text>
      <text x="26" y="122" fill="#e9f0ff" stroke="none" fontSize="15" fontWeight="600" fontFamily="var(--font-plex-sans)">
        {AGENCY_FEED_COUNT} agency
      </text>
      <text x="26" y="142" fill="#e9f0ff" stroke="none" fontSize="15" fontWeight="600" fontFamily="var(--font-plex-sans)">
        feeds
      </text>
      <text x="26" y="160" fill="#9fc0ff" stroke="none" fontSize="9" fontFamily="var(--font-plex-mono)">
        STATE DOTS + CHP
      </text>

      {/* Leaders */}
      <path d="M144 130 H206 V66 H268 M206 130 V194 H268" strokeDasharray="5 4" />
      <circle cx="206" cy="130" r="3.5" fill="#e9f0ff" stroke="none" />
      <path d="M262 62 L268 66 L262 70 M262 190 L268 194 L262 198" />

      {/* MCP block */}
      <rect x="268" y="34" width="140" height="64" rx="3" />
      <text x="282" y="60" fill="#e9f0ff" stroke="none" fontSize="14" fontWeight="600" fontFamily="var(--font-plex-mono)">
        /mcp
      </text>
      <text x="282" y="80" fill="#9fc0ff" stroke="none" fontSize="9" fontFamily="var(--font-plex-mono)">
        STREAMABLE HTTP
      </text>

      {/* REST block */}
      <rect x="268" y="162" width="140" height="64" rx="3" />
      <text x="282" y="188" fill="#e9f0ff" stroke="none" fontSize="14" fontWeight="600" fontFamily="var(--font-plex-mono)">
        /v1/tools
      </text>
      <text x="282" y="208" fill="#9fc0ff" stroke="none" fontSize="9" fontFamily="var(--font-plex-mono)">
        REST + OPENAPI
      </text>

      {/* Title block, bottom left, like a drawing sheet */}
      <path d="M12 238 H150" strokeOpacity="0.45" />
      <text x="12" y="252" fill="#9fc0ff" stroke="none" fontSize="8.5" letterSpacing="1.2" fontFamily="var(--font-plex-mono)">
        COMMUTESCOUT / DATA LAYER
      </text>
    </svg>
  );
}
