"""Cross-source deduplication.

Different sources can report the same real-world event (a CHP closure and a
Caltrans LCS closure on the same segment). Two events are duplicates when
they come from DIFFERENT sources, share a family, and are within 120 m; the
higher-trust source wins (CHP > LCS > WFIGS > chains).

Two events from the SAME source are never merged: two co-located same-family
reports may be genuinely distinct incidents and must not be silently dropped.
"""

from __future__ import annotations

from ca_roads.geo import haversine_meters
from ca_roads.models import RoadEvent

DEDUPE_METERS = 120.0

_PRIORITY = {"chp": 4, "lcs": 3, "wfigs": 2, "chains": 1}


def dedupe(events: list[RoadEvent]) -> list[RoadEvent]:
    survivors: list[RoadEvent] = []
    for event in events:
        merged = False
        for i, kept in enumerate(survivors):
            if event.source == kept.source:
                continue
            if event.family != kept.family:
                continue
            if haversine_meters(event.lat, event.lon, kept.lat, kept.lon) > DEDUPE_METERS:
                continue
            if _PRIORITY.get(event.source, 0) > _PRIORITY.get(kept.source, 0):
                survivors[i] = event
            merged = True
            break
        if not merged:
            survivors.append(event)
    return survivors
