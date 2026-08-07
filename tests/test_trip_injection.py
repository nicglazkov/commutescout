"""Trip share pages must not be turnable into an XSS vector.

The template is filled from attacker-supplied names. Chained .replace()
calls re-scan inserted text, so a name of literally "__TRIP_JSON__"
survived escaping (escaping leaves underscores alone), landed inside the
og:title attribute, and was replaced by the next call in the chain. The
JSON starts with '{"', which closed content=" and let the rest be parsed
as markup. Unauthenticated to plant, fires for every visitor.
"""
import re
from html.parser import HTMLParser

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import trips
from ca_roads_demo import watch as watch_mod

# The exact payload: a name that is itself a placeholder, plus a second
# name carrying the markup that the leaked JSON would make live.
PLACEHOLDER_NAME = "__TRIP_JSON__"
MARKUP_NAME = "><img src=x onerror=alert(1)>"


class _Store:
    def __init__(self, trip):
        self._trip = trip

    async def get_trip(self, tid):
        return self._trip


@pytest.fixture()
def hostile_page(monkeypatch):
    trip = {
        "from_name": PLACEHOLDER_NAME,
        "to_name": MARKUP_NAME,
        "miles": 12.0,
        "minutes": 30,
        "polyline": "",
        "steps": [],
        "created": 0,
    }
    monkeypatch.setattr(watch_mod, "get_store", lambda: _Store(trip))
    r = TestClient(demo_app.app).get("/trip/abc123")
    assert r.status_code == 200
    return r.text


def test_attacker_name_cannot_break_out_of_the_og_title_attribute(
        hostile_page):
    line = re.search(r'<meta property="og:title"[^\n]*', hostile_page)
    assert line, "og:title meta tag missing"
    # The signature of the break-out: the attribute value starting a JSON
    # object, which ends the attribute on its first quote.
    assert 'content="{"' not in line.group(0)


def test_no_live_markup_outside_the_json_island(hostile_page):
    """The payload may appear inside the JSON script island, where it is
    an inert string (json.dumps escapes "</" so it cannot close the tag,
    and trip.html renders every name with textContent, not innerHTML).
    What must never happen is the same text reaching HTML context."""
    # Parsed, not regexed. A regex over the raw text cannot tell a live
    # tag from the correctly escaped "&lt;img src=x onerror=...&gt;" that
    # appears as inert content inside the og:title attribute: "[^>]*"
    # walks straight past an escaped &gt;. The parser only reports tags
    # the browser would actually build, and attribute values are already
    # entity-decoded, so escaped text can never surface as an element.
    class Handlers(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.found = []

        def handle_starttag(self, tag, attrs):
            for name, value in attrs:
                if name.lower().startswith("on"):
                    self.found.append((tag, name, value))

    p = Handlers()
    p.feed(re.sub(r"<script.*?</script>", "", hostile_page, flags=re.S))
    assert not p.found, f"live event handler(s) in HTML: {p.found}"


def test_a_placeholder_named_trip_is_not_substituted_twice(hostile_page):
    """The give-away that a value got re-scanned as a placeholder."""
    head = hostile_page.split("</head>")[0]
    # The JSON belongs in the script body, never in the head's meta tags.
    assert '"from_name"' not in head


def test_the_real_trip_data_still_renders(monkeypatch):
    """The fix must not break ordinary trips."""
    trip = {"from_name": "San Jose", "to_name": "South Lake Tahoe",
            "miles": 205.0, "minutes": 220, "polyline": "", "steps": [],
            "created": 0}
    monkeypatch.setattr(watch_mod, "get_store", lambda: _Store(trip))
    text = TestClient(demo_app.app).get("/trip/abc123").text
    assert "San Jose" in text and "South Lake Tahoe" in text
    assert '"from_name": "San Jose"' in text          # the JSON island
    assert "__TRIP_JSON__" not in text                # placeholder consumed
    assert "__TITLE__" not in text


def test_every_template_placeholder_is_covered_by_the_pattern():
    """A new placeholder that the regex does not know would survive into
    the served page verbatim."""
    template = trips._TEMPLATE_PATH.read_text(encoding="utf-8")
    found = set(re.findall(r"__[A-Z_]+__", template))
    known = {m.group(0) for m in
             re.finditer(r"__(?:TITLE|OG_IMAGE|OG_URL|TRIP_JSON)__",
                         " ".join(found))}
    assert found == known, f"template has unhandled placeholders: {found - known}"
