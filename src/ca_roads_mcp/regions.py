"""Curated regions for area-scale questions ("how is the Bay Area?").

Same philosophy as the corridor table: a small, hand-maintained list beats
trying to geocode arbitrary text. Each region is a bounding box plus the
Caltrans districts to fetch, with aliases for matching user phrasing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    aliases: tuple[str, ...]
    # (lat_min, lat_max, lon_min, lon_max)
    bbox: tuple[float, float, float, float]
    districts: tuple[int, ...]

    def contains(self, lat: float, lon: float) -> bool:
        lat_min, lat_max, lon_min, lon_max = self.bbox
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


REGIONS: tuple[Region, ...] = (
    Region(
        id="bay-area",
        name="San Francisco Bay Area",
        aliases=("bay area", "sf bay", "east bay", "south bay", "north bay",
                 "peninsula", "silicon valley"),
        # East edge stops short of the Central Valley so Sacramento and Elk
        # Grove don't count as Bay Area.
        bbox=(36.95, 38.65, -123.05, -121.52),
        districts=(4, 5),
    ),
    Region(
        id="sacramento",
        name="Sacramento metro",
        aliases=("sacramento area", "sacramento metro", "sac metro",
                 "greater sacramento"),
        bbox=(38.20, 39.10, -122.10, -120.80),
        districts=(3,),
    ),
    Region(
        id="tahoe-sierra",
        name="Tahoe / Sierra",
        aliases=("sierra", "the sierra", "tahoe area", "the mountains",
                 "high sierra", "sierra nevada", "gold country"),
        bbox=(38.30, 39.70, -120.90, -119.70),
        districts=(3, 9, 10),
    ),
    Region(
        id="central-valley",
        name="Central Valley",
        aliases=("central valley", "san joaquin valley", "the valley",
                 "fresno area", "bakersfield area"),
        bbox=(35.00, 38.10, -121.60, -118.60),
        districts=(6, 10),
    ),
    Region(
        id="socal",
        name="Southern California (LA basin and Inland Empire)",
        aliases=("socal", "southern california", "la area", "los angeles area",
                 "la basin", "inland empire", "orange county", "greater la"),
        # North edge includes the Grapevine and Tejon Pass.
        bbox=(33.40, 35.05, -119.50, -116.90),
        districts=(7, 8, 12),
    ),
    Region(
        id="san-diego",
        name="San Diego area",
        aliases=("san diego", "san diego area", "sd area"),
        bbox=(32.40, 33.50, -117.70, -116.00),
        districts=(11,),
    ),
    Region(
        id="central-coast",
        name="Central Coast",
        aliases=("central coast", "monterey area", "big sur area", "slo area",
                 "san luis obispo area", "santa barbara area"),
        bbox=(34.30, 37.00, -122.40, -119.50),
        districts=(5,),
    ),
    Region(
        id="north-state",
        name="North State (Shasta / North Coast)",
        aliases=("north state", "far north", "north coast", "shasta area",
                 "redding area", "northern california mountains"),
        bbox=(38.60, 42.05, -124.50, -121.30),
        districts=(1, 2),
    ),
)


def resolve_region(text: str) -> Region | None:
    needle = text.lower().strip().strip(".,?!")
    for region in REGIONS:
        for alias in region.aliases:
            if alias in needle or needle in alias:
                return region
    return None


def region_names() -> list[str]:
    return [f"{r.name} (say: {r.aliases[0]})" for r in REGIONS]
