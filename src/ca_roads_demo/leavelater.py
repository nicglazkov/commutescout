"""Leave later: drive time for a route if you leave now or at the next
few ten-minute marks, and the departure that saves the most.

Each departure is one TomTom route (traffic-aware, cached by the feed
module), so the window is short and the step coarse: the trip screen
shows a handful of bars, not a timetable.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from ca_roads.feeds import tomtom as tomtom_feed

WINDOW_MIN = 60
STEP_MIN = 10
MAX_WINDOW_MIN = 90
# A departure has to save this much before it is worth suggesting.
MIN_SAVING_MIN = 3


def slots(now: datetime, window: int = WINDOW_MIN, step: int = STEP_MIN) -> list[datetime | None]:
    """None (leave now), then each ``step``-minute mark from at least
    five minutes out to ``window`` minutes out."""
    first = now + timedelta(minutes=5)
    mark = first.replace(second=0, microsecond=0)
    mark += timedelta(minutes=(-mark.minute) % step)
    out: list[datetime | None] = [None]
    while mark <= now + timedelta(minutes=window):
        out.append(mark)
        mark += timedelta(minutes=step)
    return out


def summarize(now: datetime, rows: list[tuple[datetime | None, dict | None]],
              window: int = WINDOW_MIN) -> dict:
    """The response body from (departure, route summary) pairs."""
    departures = []
    for when, r in rows:
        travel = (r or {}).get("travel_s")
        departures.append({
            "depart_at": (when or now).astimezone(UTC).isoformat(timespec="minutes"),
            "now": when is None,
            "drive_min": round(travel / 60) if travel else None,
            "delay_min": (round(r["delay_s"] / 60)
                          if r and r.get("delay_s") is not None else None),
        })
    known = [d for d in departures if d["drive_min"] is not None]
    now_row = departures[0] if departures and departures[0]["drive_min"] is not None else None
    best = None
    if known and now_row:
        pick = min(known, key=lambda d: (d["drive_min"], d["depart_at"]))
        saving = now_row["drive_min"] - pick["drive_min"]
        if not pick["now"] and saving >= MIN_SAVING_MIN:
            best = {"depart_at": pick["depart_at"], "drive_min": pick["drive_min"],
                    "saving_min": saving}
    if best:
        reason = "Traffic should ease by then"
    elif now_row:
        span = "hour" if window == 60 else f"{window} minutes"
        reason = f"Leaving now is as quick as any time in the next {span}"
    else:
        reason = None
    return {
        "checked_at": now.astimezone(UTC).isoformat(timespec="seconds"),
        "departures": departures,
        "best": best,
        "reason": reason,
    }


async def plan(client, origin: tuple[float, float], destination: tuple[float, float],
               *, window: int = WINDOW_MIN, step: int = STEP_MIN,
               now: datetime | None = None) -> dict | None:
    """Drive times for each departure, or None when traffic routing is
    not available (no key, or the day's routing budget is spent)."""
    now = now or datetime.now(UTC)
    whens = slots(now, window, step)
    sem = asyncio.Semaphore(3)

    async def one(when):
        async with sem:
            return await tomtom_feed.route_times(
                client, origin, destination,
                when.isoformat(timespec="seconds") if when else None)

    results = await asyncio.gather(*(one(w) for w in whens))
    if not results or results[0] is None:
        return None
    return summarize(now, list(zip(whens, results, strict=True)), window)
