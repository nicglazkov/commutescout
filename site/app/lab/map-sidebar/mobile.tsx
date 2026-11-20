// Phone mockups (390 x 844) for the top five options.
import { Briefcase, ChevronDown, Clock, Crosshair, House, Layers, LocateFixed, Navigation, Plus, Signal, Wifi } from "lucide-react";
import { MapBg } from "./map-bg";
import { StripList } from "./options-b";
import { Chip, EVENTS, EventRow, Field, Kicker, RouteSummary, SearchBox, cx } from "./kit";

export const PHONE_VB = "445 20 390 800";
export const ROUTE_VB = "515 150 520 1125";

export function Phone({ children, route = false, focus = [] as number[], vb = PHONE_VB }: { children: React.ReactNode; route?: boolean; focus?: number[]; vb?: string }) {
  return (
    <div className="absolute inset-0">
      <MapBg viewBox={vb} route={route} traffic={route} focus={focus} />
      <div className="absolute left-0 right-0 top-0 flex h-11 items-center justify-between px-7 text-[14px] font-semibold text-cs-ink">
        <span>9:41</span>
        <span className="flex items-center gap-1.5">
          <Signal size={14} />
          <Wifi size={14} />
          <span className="h-[11px] w-[22px] rounded-[3px] border border-cs-ink p-[1px]">
            <span className="block h-full w-3/4 rounded-[1px] bg-cs-ink" />
          </span>
        </span>
      </div>
      {children}
      <span className="absolute bottom-2 left-1/2 h-[5px] w-[134px] -translate-x-1/2 rounded-full bg-cs-ink" />
    </div>
  );
}

export function Sheet({ h, children, className = "" }: { h: number; children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cx("msb-float absolute bottom-0 left-0 right-0 flex flex-col rounded-t-[18px] bg-cs-surface px-4 pb-8", className)}
      style={{ height: h }}
    >
      <span className="mx-auto mb-2 mt-2 h-[5px] w-9 shrink-0 rounded-full bg-cs-line-strong" />
      {children}
    </div>
  );
}

function RoundBtn({ icon: I, style, label }: { icon: typeof House; style: React.CSSProperties; label?: string }) {
  return (
    <span className="msb-float absolute flex h-11 items-center justify-center gap-1.5 rounded-full bg-cs-surface px-3 text-cs-ink-2" style={{ minWidth: 44, ...style }}>
      <I size={18} />
      {label ? <span className="text-[13px] font-medium text-cs-ink">{label}</span> : null}
    </span>
  );
}

export function M1() {
  return (
    <Phone>
      <RoundBtn icon={Layers} style={{ right: 14, top: 54 }} />
      <RoundBtn icon={LocateFixed} style={{ right: 14, bottom: 462 }} />
      <Sheet h={448}>
        <div className="text-[20px] font-semibold">Where to?</div>
        <div className="mt-2 text-[12.5px] text-cs-ink-2">From your location</div>
        <div className="mt-2">
          <Field end="b" placeholder="Search a place or address" />
        </div>
        <div className="mt-3 flex gap-1.5 overflow-hidden">
          <Chip icon={House}>Home</Chip>
          <Chip icon={Briefcase}>Work</Chip>
          <Chip icon={Crosshair}>On the map</Chip>
        </div>
        <div className="mt-2">
          <Chip icon={Clock}>
            Leave now <ChevronDown size={13} />
          </Chip>
        </div>
        <div className="mt-4">
          <Kicker>On the map now</Kicker>
          {EVENTS.slice(0, 2).map((e) => (
            <EventRow key={e.title} {...e} compact />
          ))}
        </div>
      </Sheet>
    </Phone>
  );
}

export function M2() {
  return (
    <Phone>
      <div className="absolute left-3 right-3 top-12">
        <SearchBox
          float
          placeholder="Search or ask"
          trailing={
            <span className="grid h-8 w-8 place-items-center rounded-full bg-cs-accent text-cs-accent-ink">
              <Navigation size={15} />
            </span>
          }
        />
        <div className="mt-2 flex gap-1.5 overflow-hidden">
          <Chip icon={House} className="msb-float border-transparent">
            Home
          </Chip>
          <Chip icon={Briefcase} className="msb-float border-transparent">
            Work
          </Chip>
          <Chip icon={Layers} className="msb-float border-transparent">
            Layers
          </Chip>
        </div>
      </div>
      <RoundBtn icon={LocateFixed} style={{ right: 14, bottom: 186 }} />
      <Sheet h={172}>
        <div className="flex items-baseline justify-between">
          <span className="text-[15px] font-semibold">31 live in view</span>
          <span className="text-[12px] text-cs-ink-3">Swipe up</span>
        </div>
        <div className="mt-2 flex gap-1.5 overflow-hidden">
          <Chip tone="closure">3 closures</Chip>
          <Chip tone="incident">18 incidents</Chip>
          <Chip tone="chain">2 chains</Chip>
        </div>
      </Sheet>
    </Phone>
  );
}

export function M13() {
  return (
    <Phone route focus={[0]} vb={ROUTE_VB}>
      <RoundBtn icon={Layers} style={{ right: 14, top: 54 }} />
      <Sheet h={500}>
        <SearchBox placeholder="Search or plan a new drive" />
        <div className="mt-4 flex items-center justify-between">
          <span className="text-[16px] font-semibold">Your drives</span>
          <span className="text-[12px] text-cs-ink-3">30 s ago</span>
        </div>
        {[
          ["Home to Work", "24 min · 1 crash on the way", false],
          ["Work to Home", "Clear · 21 min now", true],
          ["Home to School", "Clear · 12 min now", true],
        ].map(([a, b, ok]) => (
          <div key={a as string} className="mt-2 rounded-[12px] border border-cs-line p-3">
            <div className="font-semibold">{a as string}</div>
            <span
              className={cx(
                "mt-1 inline-block rounded-full px-2 py-0.5 text-[12px] font-medium",
                ok ? "bg-cs-ok-soft text-cs-ok" : "bg-cs-incident-soft text-cs-incident",
              )}
            >
              {b as string}
            </span>
          </div>
        ))}
        <span className="mt-3 flex items-center gap-1.5 text-[13px] font-medium text-cs-accent">
          <Plus size={15} /> Add a drive
        </span>
      </Sheet>
    </Phone>
  );
}

export function M11() {
  return (
    <Phone route focus={[0]} vb={ROUTE_VB}>
      <Sheet h={560}>
        <div className="flex items-baseline justify-between">
          <span className="text-[16px] font-semibold">Home to Work</span>
          <span className="text-[13px] font-semibold text-cs-incident">24 min</span>
        </div>
        <div className="text-[12px] text-cs-ink-2">11.2 mi · 6 min slower than usual · Leave now</div>
        <div className="mt-3">
          <StripList />
        </div>
      </Sheet>
    </Phone>
  );
}

export function M6() {
  return (
    <Phone focus={[0]}>
      <div className="absolute left-3 right-3 top-12">
        <SearchBox float placeholder="Search a place" />
      </div>
      <Sheet h={470}>
        <div className="flex gap-1.5 overflow-hidden">
          <Chip active>All 31</Chip>
          <Chip tone="closure" active>
            Closures 3
          </Chip>
          <Chip tone="incident" active>
            Incidents 18
          </Chip>
        </div>
        <div className="mt-2 text-[12px] text-cs-ink-2">Worst first, in the map above</div>
        <div className="mt-1 divide-y divide-cs-line">
          {EVENTS.slice(0, 5).map((e) => (
            <EventRow key={e.title} {...e} compact />
          ))}
        </div>
      </Sheet>
    </Phone>
  );
}

export function M1Result() {
  return (
    <Phone route focus={[0]} vb={ROUTE_VB}>
      <Sheet h={400}>
        <div className="flex items-baseline justify-between">
          <span className="text-[16px] font-semibold">Home to Work</span>
          <span className="text-[12px] text-cs-accent">Edit</span>
        </div>
        <div className="mt-2">
          <RouteSummary />
        </div>
        <div className="mt-2">
          <EventRow k="incident" title="Crash blocking right lane" meta="Mile 3.2 · Exit 14" compact />
          <EventRow k="closure" title="Right lane closed, roadwork" meta="Mile 8.9 · until 3 PM" compact />
        </div>
      </Sheet>
    </Phone>
  );
}
