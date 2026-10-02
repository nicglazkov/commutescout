"""Rebuild cameras.json from OpenStreetMap.

One Overpass query for the United States: every ``highway=speed_camera``
node, and the device of every ``type=enforcement`` relation that enforces
a speed limit or a traffic signal. The result is the small file the
plugin serves from, so the running service never depends on Overpass.

    python refresh.py            # writes cameras.json beside this file
    python refresh.py saved.json # from a saved Overpass response instead

Run it when the map files are refreshed (monthly). The data is
(c) OpenStreetMap contributors, under the ODbL.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="US"][admin_level=2]->.us;
(
  node["highway"="speed_camera"](area.us);
  relation["type"="enforcement"]["enforcement"~"^(maxspeed|traffic_signals)$"](area.us);
);
out body;
node(r:"device");
out skel;
"""
OUT = Path(__file__).with_name("cameras.json")
# A refresh that comes back this much smaller than the file it replaces
# is an Overpass hiccup, not a real change.
MIN_KEEP = 0.8


def limit_mph(value: str | None) -> int | None:
    """``35 mph`` or ``35`` (US tagging means mph either way); None for
    anything else, such as ``signals`` or a km/h value."""
    if not value:
        return None
    text = value.strip().lower()
    if text.endswith("mph"):
        text = text[:-3].strip()
    if not text.isdigit():
        return None
    mph = int(text)
    return mph if 5 <= mph <= 90 else None


def _record(node: dict, kind: str, maxspeed: str | None) -> dict:
    rec = {"id": node["id"], "kind": kind,
           "lat": round(node["lat"], 6), "lon": round(node["lon"], 6)}
    mph = limit_mph(maxspeed)
    if mph and kind == "CAMERA_SPEED":
        rec["mph"] = mph
    return rec


def cameras(overpass: dict) -> list[dict]:
    """The records the plugin serves, from one Overpass response."""
    nodes: dict[int, dict] = {}
    relations = []
    for el in overpass.get("elements", []):
        if el.get("type") == "node" and "lat" in el:
            # A device comes back twice, with and without its tags.
            nodes.setdefault(el["id"], {}).update(el)
        elif el.get("type") == "relation":
            relations.append(el)
    out: dict[int, dict] = {}
    for node in nodes.values():
        tags = node.get("tags") or {}
        if tags.get("highway") != "speed_camera":
            continue
        red = (tags.get("enforcement") == "traffic_signals"
               or tags.get("speed_camera") == "red_light")
        out[node["id"]] = _record(node, "CAMERA_RED_LIGHT" if red else "CAMERA_SPEED",
                                  tags.get("maxspeed"))
    # A relation says what its device enforces more exactly than the
    # node's own tags do, so it wins.
    for rel in relations:
        tags = rel.get("tags") or {}
        kind = ("CAMERA_RED_LIGHT" if tags.get("enforcement") == "traffic_signals"
                else "CAMERA_SPEED")
        for member in rel.get("members", []):
            node = nodes.get(member.get("ref")) if member.get("type") == "node" else None
            if member.get("role") == "device" and node:
                out[node["id"]] = _record(node, kind, tags.get("maxspeed"))
    return sorted(out.values(), key=lambda r: r["id"])


def fetch() -> dict:
    req = urllib.request.Request(  # noqa: S310 (a fixed https URL)
        OVERPASS, data=urllib.parse.urlencode({"data": QUERY}).encode(),
        headers={"User-Agent": "CommuteScout osm-cameras plugin (https://commutescout.com/contact)"})
    with urllib.request.urlopen(req, timeout=240) as r:  # noqa: S310
        return json.load(r)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    overpass = json.loads(Path(args[0]).read_text(encoding="utf-8")) if args else fetch()
    found = cameras(overpass)
    if OUT.exists():
        had = len(json.loads(OUT.read_text(encoding="utf-8"))["cameras"])
        if len(found) < had * MIN_KEEP:
            print(f"refusing: {len(found)} cameras, the file has {had}", file=sys.stderr)
            return 1
    as_of = (overpass.get("osm3s") or {}).get("timestamp_osm_base")
    OUT.write_text(json.dumps({"as_of": as_of, "cameras": found}, separators=(",", ":")) + "\n",
                   encoding="utf-8")
    print(f"{len(found)} cameras as of {as_of}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
