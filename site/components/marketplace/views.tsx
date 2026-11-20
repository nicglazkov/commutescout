import { alertsLabel, coverageLabel, refreshLabel, tierOf, type Source } from "./data";
import {
  CoverageMap,
  InstallButton,
  KindChips,
  KindStrip,
  KindTiles,
  MapLink,
  Operator,
  PluginIcon,
  TIER_META,
  TrustBadge,
} from "./parts";

type Ctl = { isInstalled: (s: Source) => boolean; onToggle: (s: Source) => void };

function blurb(s: Source) {
  return s.description || "Community alerts for the map.";
}

const NUM = { fontVariantNumeric: "tabular-nums" } as const;

// ---- featured banner ----

export function Featured({ s, isInstalled, onToggle }: { s: Source } & Ctl) {
  const t = tierOf(s);
  return (
    <section
      aria-labelledby="mk-featured-h"
      data-tier={t}
      className="mk-t-rule grid overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface shadow-[var(--cs-shadow-sm)] lg:grid-cols-12"
    >
      <div className="flex flex-col p-6 sm:p-8 lg:col-span-7 lg:justify-center">
        <p className="cs-data flex items-center gap-2 text-[11px] uppercase tracking-[0.1em] text-cs-ink-3">
          <span aria-hidden className="mk-t-dot size-1.5 rounded-full" />
          Featured
        </p>
        <div className="mt-4 flex items-start gap-4">
          <PluginIcon s={s} size="lg" />
          <div className="min-w-0">
            <h2 id="mk-featured-h" className="cs-h2 text-balance">
              {s.name}
            </h2>
            <p className="mt-1 text-sm text-cs-ink-3">
              <Operator s={s} />
            </p>
          </div>
        </div>
        <p className="mt-5 max-w-[60ch] text-[0.9375rem] leading-relaxed text-cs-ink-2">{blurb(s)}</p>
        <div className="mt-4">
          <KindChips s={s} />
        </div>
        <div className="mt-7 flex flex-wrap items-center gap-x-5 gap-y-3">
          <InstallButton s={s} installed={isInstalled(s)} onToggle={onToggle} />
          <MapLink s={s} />
        </div>
      </div>
      <div className="flex flex-col justify-between gap-6 border-t border-cs-line bg-cs-surface-2 p-6 sm:p-8 lg:col-span-5 lg:border-l lg:border-t-0">
        <CoverageMap s={s} className="mx-auto w-full max-w-[300px] sm:max-w-[380px]" />
        <dl className="grid grid-cols-3 gap-4">
          <div>
            <dt className="cs-data text-[11px] uppercase tracking-[0.06em] text-cs-ink-3">Alerts now</dt>
            <dd className="cs-data mt-1 text-lg text-cs-ink" style={NUM}>
              {alertsLabel(s)}
            </dd>
          </div>
          <div>
            <dt className="cs-data text-[11px] uppercase tracking-[0.06em] text-cs-ink-3">Refresh</dt>
            <dd className="mt-1 text-sm font-medium text-cs-ink">{refreshLabel(s.refresh_s)}</dd>
          </div>
          <div>
            <dt className="cs-data text-[11px] uppercase tracking-[0.06em] text-cs-ink-3">Trust</dt>
            <dd className="mt-1">
              <TrustBadge s={s} compact />
            </dd>
          </div>
        </dl>
      </div>
    </section>
  );
}

// ---- list view (dense rows, columns on wide screens) ----

const COLS = "lg:grid lg:grid-cols-[minmax(0,2.6fr)_minmax(0,1.7fr)_minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.95fr)_auto] lg:items-center lg:gap-4";

export function ListHead({ showTrust }: { showTrust: boolean }) {
  return (
    <div
      aria-hidden
      className={`cs-data hidden whitespace-nowrap border-b border-cs-line bg-cs-surface-2 px-4 py-2.5 text-[11px] uppercase tracking-[0.06em] text-cs-ink-3 ${COLS}`}
    >
      <span>Plugin</span>
      <span>Shows</span>
      <span>Coverage</span>
      <span>Alerts now</span>
      <span>Refresh</span>
      <span className="w-[148px]">{showTrust ? "Trust" : ""}</span>
    </div>
  );
}

export function ListRow({ s, isInstalled, onToggle, showTrust }: { s: Source; showTrust: boolean; featured?: boolean } & Ctl) {
  return (
    <li data-plugin={s.id} className={`px-4 py-4 lg:py-3 ${COLS}`}>
      <div className="flex min-w-0 items-center gap-3">
        <PluginIcon s={s} size="sm" />
        <div className="min-w-0 flex-1">
          <h3 className="flex flex-wrap items-center gap-x-2 text-[0.9375rem] font-medium text-cs-ink">
            <span className="min-w-0">{s.name}</span>
          </h3>
          <p className="truncate text-xs text-cs-ink-3">
            <Operator s={s} />
          </p>
        </div>
        <div className="flex items-center gap-1 lg:hidden">
          <InstallButton s={s} installed={isInstalled(s)} onToggle={onToggle} size="sm" />
        </div>
      </div>

      <div className="mt-3 lg:mt-0">
        <span className="sr-only">Shows: </span>
        <KindTiles s={s} max={5} />
      </div>

      {/* Phones: one meta line. Wide screens: one column each. */}
      <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-cs-ink-3 lg:hidden">
        {showTrust && <TrustBadge s={s} compact />}
        <span>{coverageLabel(s.coverage)}</span>
        <span>
          <span className="cs-data text-cs-ink" style={NUM}>
            {alertsLabel(s)}
          </span>{" "}
          alerts now
        </span>
        <span>{refreshLabel(s.refresh_s)}</span>
        <MapLink s={s} />
      </p>
      <span className="hidden text-sm text-cs-ink-2 lg:block">
        <span className="sr-only">Coverage: </span>
        {coverageLabel(s.coverage)}
      </span>
      <span className="cs-data hidden text-sm text-cs-ink lg:block" style={NUM}>
        <span className="sr-only">Alerts now: </span>
        {alertsLabel(s)}
      </span>
      <span className="hidden text-sm text-cs-ink-2 lg:block">
        <span className="sr-only">Refresh: </span>
        {refreshLabel(s.refresh_s)}
      </span>
      <div className="hidden w-[148px] items-center justify-end gap-1 lg:flex">
        {showTrust ? <TrustBadge s={s} compact /> : null}
        <MapLink s={s} iconOnly />
        <InstallButton s={s} installed={isInstalled(s)} onToggle={onToggle} size="sm" />
      </div>
    </li>
  );
}

// ---- cards view ----

export function Card({ s, isInstalled, onToggle, showTrust, featured }: { s: Source; showTrust: boolean; featured?: boolean } & Ctl) {
  const t = tierOf(s);
  return (
    <li
      data-plugin={s.id}
      className="flex min-w-0 flex-col overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface shadow-[var(--cs-shadow-sm)] transition-[border-color,box-shadow] duration-150 hover:border-cs-line-strong hover:shadow-[var(--cs-shadow-md)]"
    >
      <KindStrip s={s} />
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start gap-3">
          <PluginIcon s={s} />
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold leading-snug text-cs-ink text-balance">{s.name}</h3>
            <p className="mt-0.5 truncate text-sm text-cs-ink-3">
              <Operator s={s} />
            </p>
          </div>
          <InstallButton s={s} installed={isInstalled(s)} onToggle={onToggle} size="sm" />
        </div>
        <p className="mt-4 line-clamp-3 text-sm leading-relaxed text-cs-ink-2">{blurb(s)}</p>
        <div className="mt-3">
          <KindChips s={s} counts />
        </div>
        <div aria-hidden className="min-h-5 flex-1" />
        <dl className="grid grid-cols-3 gap-3 border-t border-cs-line pt-4">
          <div>
            <dt className="cs-data text-[10px] uppercase tracking-[0.06em] text-cs-ink-3">Alerts now</dt>
            <dd className="cs-data mt-0.5 text-sm text-cs-ink" style={NUM}>
              {alertsLabel(s)}
            </dd>
          </div>
          <div>
            <dt className="cs-data text-[10px] uppercase tracking-[0.06em] text-cs-ink-3">Coverage</dt>
            <dd className="mt-0.5 truncate text-sm text-cs-ink">{coverageLabel(s.coverage)}</dd>
          </div>
          <div>
            <dt className="cs-data text-[10px] uppercase tracking-[0.06em] text-cs-ink-3">Reports</dt>
            <dd className="mt-0.5 text-sm text-cs-ink">{s.capabilities?.report ? "Accepted" : "Read only"}</dd>
          </div>
        </dl>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          {showTrust || featured ? (
            <span className="flex flex-wrap items-center gap-2">
              {showTrust && <TrustBadge s={s} />}
              {featured && <span className="cs-data text-[10px] uppercase tracking-[0.08em] text-cs-ink-3">Featured</span>}
            </span>
          ) : (
            <span />
          )}
          <MapLink s={s} />
        </div>
        {showTrust && t === "unreviewed" && (
          <p className="mt-3 text-xs leading-relaxed text-cs-ink-3">{UNREVIEWED_NOTE}</p>
        )}
        {s.visibility === "unlisted" && t !== "private" && (
          <p className="mt-3 text-xs text-cs-ink-3">{TIER_META.private.why}</p>
        )}
      </div>
    </li>
  );
}

export const UNREVIEWED_NOTE =
  "Not reviewed by CommuteScout. Its alerts come from its operator, not from official sources. It alerts only after you tick that notice at install, and only in the apps. Turn its alerts, or speaking them, on or off in Settings > Alerts.";
