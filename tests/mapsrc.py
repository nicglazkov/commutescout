"""The map page's source, for tests that scan it: the HTML plus the
stylesheet and the two scripts it links (split out of the file on
2026-09-17)."""

import pathlib

_STATIC = pathlib.Path("src/ca_roads_demo/static")
MAP_FILES = ("map.html", "map.css", "map-assistant.js", "map-app.js")


def map_source() -> str:
    return "\n".join((_STATIC / n).read_text(encoding="utf-8") for n in MAP_FILES)
