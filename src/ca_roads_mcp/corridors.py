"""Curated corridor table for check_route.

This is deliberately NOT a router: each corridor is a hand-drawn polyline of
waypoints along a major California highway, with place-name aliases for its
endpoints and towns along the way. check_route matches the user's from/to
places against these aliases, then reports every active event within the
corridor buffer, ordered by distance along the polyline.

Waypoint coordinates are coarse (town centers and passes); the buffer absorbs
the imprecision.
"""

from __future__ import annotations

from dataclasses import dataclass

from ca_roads.geo import districts_for, haversine_meters
from ca_roads.models import RoadEvent
from ca_roads_mcp.routes import routes_mentioned

DEFAULT_BUFFER_METERS = 8_000.0
FIRE_BUFFER_METERS = 16_000.0  # ~10 miles: fires flagged near a route


@dataclass(frozen=True)
class Corridor:
    id: str
    name: str
    routes: tuple[str, ...]  # canonical routes the corridor follows
    waypoints: tuple[tuple[float, float], ...]  # (lat, lon), ordered A -> B
    # alias -> normalized place names; index 0 side is the A end
    aliases_a: tuple[str, ...]
    aliases_b: tuple[str, ...]
    aliases_mid: tuple[str, ...] = ()
    buffer_meters: float = DEFAULT_BUFFER_METERS

    def all_aliases(self) -> tuple[str, ...]:
        return self.aliases_a + self.aliases_b + self.aliases_mid


CORRIDORS: tuple[Corridor, ...] = (
    Corridor(
        id="i80-sac-reno",
        name="I-80: Sacramento to Reno (Donner Pass)",
        routes=("I-80",),
        waypoints=(
            (38.58, -121.49), (38.75, -121.28), (38.90, -121.07), (39.10, -120.95),
            (39.20, -120.78), (39.30, -120.67), (39.32, -120.38), (39.32, -120.33),
            (39.33, -120.18), (39.39, -120.02), (39.52, -119.99), (39.53, -119.81),
        ),
        aliases_a=("sacramento", "davis", "roseville"),
        aliases_b=("reno", "sparks"),
        aliases_mid=("auburn", "colfax", "emigrant gap", "soda springs",
                     "donner", "donner pass", "donner summit", "truckee"),
    ),
    Corridor(
        id="us50-sac-tahoe",
        name="US-50: Sacramento to South Lake Tahoe (Echo Summit)",
        routes=("US-50",),
        waypoints=(
            (38.58, -121.49), (38.66, -121.20), (38.69, -121.08), (38.73, -120.80),
            (38.76, -120.59), (38.77, -120.30), (38.81, -120.12), (38.81, -120.03),
            (38.86, -119.98), (38.94, -119.98),
        ),
        aliases_a=("sacramento", "folsom", "el dorado hills"),
        aliases_b=("south lake tahoe", "tahoe", "lake tahoe", "stateline",
                   "heavenly"),
        aliases_mid=("placerville", "pollock pines", "kyburz", "twin bridges",
                     "strawberry", "echo summit", "meyers", "sierra at tahoe"),
    ),
    Corridor(
        id="i5-north",
        name="I-5: Oregon border to Sacramento",
        routes=("I-5",),
        waypoints=(
            (41.96, -122.58), (41.73, -122.63), (41.42, -122.39), (41.31, -122.31),
            (41.23, -122.27), (40.90, -122.38), (40.59, -122.39), (40.18, -122.24),
            (39.93, -122.18), (39.52, -122.19), (39.15, -122.15), (38.68, -121.77),
            (38.58, -121.49),
        ),
        aliases_a=("oregon border", "hornbrook", "yreka"),
        aliases_b=("sacramento",),
        aliases_mid=("weed", "mount shasta", "mt shasta", "shasta", "dunsmuir",
                     "redding", "red bluff", "corning", "willows", "williams",
                     "woodland"),
    ),
    Corridor(
        id="i5-sac-la",
        name="I-5: Sacramento to Los Angeles (Central Valley / Grapevine)",
        routes=("I-5",),
        waypoints=(
            (38.58, -121.49), (38.25, -121.45), (37.95, -121.42), (37.48, -121.20),
            (37.10, -121.02), (36.60, -120.65), (36.25, -120.24), (36.01, -119.96),
            (35.40, -119.45), (34.99, -118.95), (34.93, -118.92), (34.84, -118.86),
            (34.42, -118.54), (34.05, -118.24),
        ),
        aliases_a=("sacramento", "stockton"),
        aliases_b=("los angeles", "la", "santa clarita"),
        aliases_mid=("santa nella", "coalinga", "harris ranch", "kettleman city",
                     "buttonwillow", "grapevine", "tejon", "tejon pass", "lebec",
                     "gorman", "castaic"),
    ),
    Corridor(
        id="us101-sf-la",
        name="US-101: San Francisco to Los Angeles",
        routes=("US-101",),
        waypoints=(
            (37.77, -122.42), (37.55, -122.30), (37.34, -121.89), (37.00, -121.57),
            (36.68, -121.64), (36.21, -121.13), (35.63, -120.69), (35.28, -120.66),
            (34.95, -120.43), (34.64, -120.19), (34.42, -119.70), (34.28, -119.29),
            (34.17, -118.83), (34.05, -118.24),
        ),
        aliases_a=("san francisco", "sf", "peninsula"),
        aliases_b=("los angeles", "la", "hollywood"),
        aliases_mid=("san jose", "gilroy", "salinas", "king city", "paso robles",
                     "san luis obispo", "slo", "santa maria", "buellton",
                     "santa barbara", "ventura", "oxnard", "thousand oaks"),
    ),
    Corridor(
        id="sr17",
        name="SR-17: San Jose to Santa Cruz",
        routes=("SR-17",),
        waypoints=(
            (37.32, -121.95), (37.23, -121.96), (37.15, -121.99), (37.05, -122.01),
            (36.97, -122.03),
        ),
        aliases_a=("san jose", "campbell", "los gatos"),
        aliases_b=("santa cruz", "scotts valley"),
        aliases_mid=("summit", "the summit", "17"),
        buffer_meters=5_000.0,
    ),
    Corridor(
        id="i15-barstow-vegas",
        name="I-15: Barstow to the Nevada state line (Las Vegas)",
        routes=("I-15",),
        waypoints=(
            (34.90, -117.02), (34.91, -116.82), (35.03, -116.38), (35.27, -116.07),
            (35.47, -115.55), (35.61, -115.39),
        ),
        aliases_a=("barstow", "san bernardino", "victorville"),
        aliases_b=("las vegas", "vegas", "primm", "stateline nevada"),
        aliases_mid=("yermo", "baker", "mountain pass", "halloran"),
    ),
    Corridor(
        id="sr99",
        name="SR-99: Sacramento to Bakersfield",
        routes=("SR-99",),
        waypoints=(
            (38.58, -121.49), (38.41, -121.38), (37.96, -121.29), (37.64, -120.99),
            (37.30, -120.48), (36.98, -120.06), (36.75, -119.77), (36.35, -119.42),
            (36.21, -119.34), (35.77, -119.25), (35.37, -119.02),
        ),
        aliases_a=("sacramento", "elk grove"),
        aliases_b=("bakersfield", "delano"),
        aliases_mid=("stockton", "modesto", "turlock", "merced", "madera",
                     "fresno", "visalia", "tulare"),
    ),
    Corridor(
        id="i880",
        name="I-880: Oakland to San Jose",
        routes=("I-880",),
        waypoints=(
            (37.80, -122.28), (37.72, -122.16), (37.64, -122.10), (37.53, -121.99),
            (37.43, -121.92), (37.34, -121.89),
        ),
        aliases_a=("oakland", "san leandro"),
        aliases_b=("san jose", "milpitas"),
        aliases_mid=("hayward", "union city", "fremont", "nimitz"),
        buffer_meters=5_000.0,
    ),
    Corridor(
        id="i680",
        name="I-680: Fairfield to San Jose",
        routes=("I-680",),
        waypoints=(
            (38.21, -122.14), (38.06, -122.13), (37.97, -122.03), (37.90, -122.06),
            (37.82, -121.99), (37.70, -121.92), (37.66, -121.87), (37.53, -121.92),
            (37.43, -121.90), (37.33, -121.88),
        ),
        aliases_a=("fairfield", "cordelia", "benicia"),
        aliases_b=("san jose",),
        aliases_mid=("concord", "walnut creek", "danville", "san ramon",
                     "dublin", "pleasanton", "sunol"),
        buffer_meters=5_000.0,
    ),
    Corridor(
        id="i280",
        name="I-280: San Francisco to San Jose",
        routes=("I-280",),
        waypoints=(
            (37.77, -122.42), (37.70, -122.47), (37.60, -122.40), (37.50, -122.33),
            (37.40, -122.26), (37.35, -122.12), (37.32, -122.06), (37.33, -121.92),
        ),
        aliases_a=("san francisco", "sf", "daly city"),
        aliases_b=("san jose", "cupertino"),
        aliases_mid=("hillsborough", "woodside", "los altos hills"),
        buffer_meters=5_000.0,
    ),
    Corridor(
        id="sr1-sf-santacruz",
        name="SR-1: San Francisco to Santa Cruz (coast)",
        routes=("SR-1",),
        waypoints=(
            (37.77, -122.47), (37.61, -122.49), (37.46, -122.43), (37.25, -122.41),
            (37.10, -122.28), (37.01, -122.19), (36.97, -122.03),
        ),
        aliases_a=("san francisco", "sf", "pacifica"),
        aliases_b=("santa cruz", "davenport"),
        aliases_mid=("half moon bay", "pescadero", "ano nuevo"),
        buffer_meters=5_000.0,
    ),
    Corridor(
        id="sr1-bigsur",
        name="SR-1: Monterey to San Simeon (Big Sur)",
        routes=("SR-1",),
        waypoints=(
            (36.60, -121.89), (36.55, -121.92), (36.43, -121.92), (36.27, -121.81),
            (36.02, -121.55), (35.91, -121.47), (35.78, -121.33), (35.64, -121.19),
        ),
        aliases_a=("monterey", "carmel"),
        aliases_b=("san simeon", "cambria", "hearst castle"),
        aliases_mid=("big sur", "lucia", "gorda", "ragged point"),
        buffer_meters=5_000.0,
    ),
    Corridor(
        id="sr88",
        name="SR-88: Jackson to Woodfords (Carson Pass)",
        routes=("SR-88",),
        waypoints=(
            (38.35, -120.77), (38.41, -120.66), (38.43, -120.57), (38.55, -120.35),
            (38.67, -120.12), (38.70, -120.07), (38.69, -119.99), (38.78, -119.82),
        ),
        aliases_a=("jackson", "pine grove"),
        aliases_b=("woodfords", "minden", "gardnerville"),
        aliases_mid=("kirkwood", "carson pass", "silver lake", "caples lake"),
        buffer_meters=5_000.0,
    ),
    Corridor(
        id="sr89-west-tahoe",
        name="SR-89: Truckee to South Lake Tahoe (west shore)",
        routes=("SR-89",),
        waypoints=(
            (39.33, -120.18), (39.20, -120.20), (39.17, -120.14), (39.06, -120.16),
            (38.95, -120.11), (38.93, -120.04), (38.94, -119.98),
        ),
        aliases_a=("truckee", "squaw valley", "olympic valley", "palisades"),
        aliases_b=("south lake tahoe", "camp richardson"),
        aliases_mid=("tahoe city", "homewood", "tahoma", "emerald bay"),
        buffer_meters=4_000.0,
    ),
    Corridor(
        id="sr267",
        name="SR-267: Truckee to Kings Beach",
        routes=("SR-267",),
        waypoints=((39.33, -120.18), (39.27, -120.12), (39.24, -120.03)),
        aliases_a=("truckee",),
        aliases_b=("kings beach", "north lake tahoe"),
        aliases_mid=("northstar", "brockway summit"),
        buffer_meters=4_000.0,
    ),
    Corridor(
        id="sr28",
        name="SR-28: Tahoe City to Crystal Bay (north shore)",
        routes=("SR-28",),
        waypoints=(
            (39.17, -120.14), (39.23, -120.08), (39.24, -120.03), (39.25, -119.95),
        ),
        aliases_a=("tahoe city",),
        aliases_b=("crystal bay", "incline village"),
        aliases_mid=("carnelian bay", "kings beach", "tahoe vista"),
        buffer_meters=4_000.0,
    ),
)


@dataclass
class CorridorMatch:
    corridor: Corridor
    reversed: bool  # True when from_place matched the B end


def _matches(place: str, aliases: tuple[str, ...]) -> bool:
    p = place.lower().strip().strip(".,")
    return any(a in p or p in a for a in aliases if a)


def resolve_corridor(from_place: str, to_place: str) -> CorridorMatch | None:
    """Find the corridor whose alias sets cover both places.

    Endpoint matches are preferred over mid-corridor matches so that e.g.
    Sacramento -> Reno picks I-80 rather than a corridor that merely passes
    near Sacramento.
    """
    best: CorridorMatch | None = None
    best_score = 0
    for c in CORRIDORS:
        from_a = _matches(from_place, c.aliases_a)
        from_b = _matches(from_place, c.aliases_b)
        from_mid = _matches(from_place, c.aliases_mid)
        to_a = _matches(to_place, c.aliases_a)
        to_b = _matches(to_place, c.aliases_b)
        to_mid = _matches(to_place, c.aliases_mid)
        if not ((from_a or from_b or from_mid) and (to_a or to_b or to_mid)):
            continue
        # Score: endpoint hits are worth more than mid-corridor hits.
        score = (2 * (from_a or from_b)) + from_mid + (2 * (to_a or to_b)) + to_mid
        if (from_a and to_a) or (from_b and to_b):
            score -= 2  # both places on the same end is a weak match
        if score > best_score:
            best_score = score
            best = CorridorMatch(corridor=c, reversed=from_b and not from_a)
    return best


def corridor_names() -> list[str]:
    return [c.name for c in CORRIDORS]


# ── Geometry along the polyline ──────────────────────────────────────────────


def _segment_lengths(waypoints: tuple[tuple[float, float], ...]) -> list[float]:
    return [
        haversine_meters(*waypoints[i], *waypoints[i + 1])
        for i in range(len(waypoints) - 1)
    ]


def distance_to_corridor(
    corridor: Corridor, lat: float, lon: float
) -> tuple[float, float]:
    """(distance from point to polyline, distance along polyline of the
    nearest point), both in meters. Approximates each segment by sampling —
    coarse but plenty for 4-8 km buffers."""
    best_dist = float("inf")
    best_along = 0.0
    along = 0.0
    wps = corridor.waypoints
    for i in range(len(wps) - 1):
        (lat1, lon1), (lat2, lon2) = wps[i], wps[i + 1]
        seg_len = haversine_meters(lat1, lon1, lat2, lon2)
        steps = max(2, int(seg_len // 2_000))
        for s in range(steps + 1):
            t = s / steps
            plat = lat1 + (lat2 - lat1) * t
            plon = lon1 + (lon2 - lon1) * t
            d = haversine_meters(lat, lon, plat, plon)
            if d < best_dist:
                best_dist = d
                best_along = along + seg_len * t
        along += seg_len
    return best_dist, best_along


def corridor_districts(corridor: Corridor) -> list[int]:
    """Caltrans districts the corridor passes through (for feed selection)."""
    out: set[int] = set()
    for lat, lon in corridor.waypoints:
        out.update(districts_for(lat, lon, corridor.buffer_meters))
    return sorted(out)


@dataclass
class PlacedEvent:
    event: RoadEvent
    distance_m: float  # from the corridor centerline
    along_m: float  # from the A end


def events_on_corridor(
    corridor: Corridor,
    events: list[RoadEvent],
    reversed_direction: bool = False,
) -> list[PlacedEvent]:
    """Events within the corridor buffer, ordered along the travel direction.

    Events carrying a route designation (LCS closures, chain controls) must be
    on one of the corridor's routes; geometry alone is not enough, because an
    8 km buffer through a city would sweep in parallel highways. CHP incidents
    (free-text location) are kept when the text mentions the route, or when
    they sit within 2 km of the centerline. Fires use a wider 10-mile buffer
    and no route test.
    """
    total = sum(_segment_lengths(corridor.waypoints))
    placed: list[PlacedEvent] = []
    for event in events:
        buffer = FIRE_BUFFER_METERS if event.family == "fire" else corridor.buffer_meters
        dist, along = distance_to_corridor(corridor, event.lat, event.lon)
        if dist > buffer:
            continue
        record_route = getattr(event.record, "route", None)
        if record_route:
            if record_route not in corridor.routes:
                continue
        elif event.source == "chp":
            mentioned = routes_mentioned(getattr(event.record, "location", ""))
            on_route = any(r in mentioned for r in corridor.routes)
            if mentioned and not on_route:
                continue  # explicitly on some other highway
            if not mentioned and dist > 2_000:
                continue
        if reversed_direction:
            along = total - along
        placed.append(PlacedEvent(event=event, distance_m=dist, along_m=along))
    placed.sort(key=lambda p: p.along_m)
    return placed
