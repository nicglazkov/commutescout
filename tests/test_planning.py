"""The nationwide trip tools: resolution, the best-time sweep, trip
assembly, history summaries, and the snapshot reader. Every upstream is
faked; nothing here touches the network."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from ca_roads.feeds import nws as nws_feed
from ca_roads.feeds import tomtom as tomtom_feed
from ca_roads_mcp import history as hist
from ca_roads_mcp import planning, snapshots

SJ = (37.3382, -121.8863)
SF = (37.7955, -122.3937)


# ── Pure helpers ─────────────────────────────────────────────────────────────

def test_parse_hhmm_and_day():
    assert planning.parse_hhmm("7am") == (7, 0)
    assert planning.parse_hhmm("5:30 PM") == (17, 30)
    assert planning.parse_hhmm("12am") == (0, 0)
    assert planning.parse_hhmm("25:00") is None
    today = date(2026, 10, 29)  # a Thursday
    assert planning.parse_day("tomorrow", today) == date(2026, 10, 30)
    assert planning.parse_day("saturday", today) == date(2026, 10, 31)
    assert planning.parse_day("thursday", today) == date(2026, 11, 5)
    assert planning.parse_day("2026-11-02", today) == date(2026, 11, 2)
    assert planning.parse_day("someday", today) is None


def test_parse_local_reads_the_forms_models_send():
    tz = ZoneInfo("America/Los_Angeles")
    now = datetime(2026, 10, 29, 20, 0, tzinfo=tz)
    assert planning.parse_local("now", tz, now) == now
    assert planning.parse_local("tomorrow 8am", tz, now) == datetime(
        2026, 10, 30, 8, 0, tzinfo=tz)
    # "8am" said in the evening means tomorrow morning.
    assert planning.parse_local("8am", tz, now).date() == date(2026, 10, 30)
    assert planning.parse_local("2026-11-02T08:00", tz, now).hour == 8
    assert planning.parse_local("whenever", tz, now) is None


def test_clock_and_zone_guess():
    assert planning.clock(datetime(2026, 1, 1, 0, 5)) == "12:05 AM"
    assert planning.clock(datetime(2026, 1, 1, 17, 30)) == "5:30 PM"
    assert planning.guess_zone(40.71, -74.0) == "America/New_York"
    assert planning.guess_zone(41.88, -87.63) == "America/Chicago"
    assert planning.guess_zone(39.74, -104.99) == "America/Denver"
    assert planning.guess_zone(33.45, -112.07) == "America/Phoenix"
    assert planning.guess_zone(47.61, -122.33) == "America/Los_Angeles"
    assert planning.guess_zone(21.3, -157.8) == "Pacific/Honolulu"


def test_locate_on_line_measures_along_and_rejects_far_points():
    line = [(37.0, -122.0 + i * 0.001) for i in range(200)]
    cum = planning.cumulative_m(line)
    along = planning.locate_on_line(37.0001, -121.95, line, cum, 250)
    assert along is not None and 4_000 < along < 4_600
    assert planning.locate_on_line(37.05, -121.95, line, cum, 250) is None


def test_tidy_and_lodging_filter():
    assert planning._tidy("Springfield, Springfield, MO, USA") == "Springfield, MO, USA"
    assert planning._LODGING.search("Radisson Jfk Airport")
    assert planning._LODGING.search("Holiday Inn LAX International Airport")
    assert not planning._LODGING.search("John F. Kennedy International Airport")
    assert not planning._LODGING.search("Pinnacle Peak Park")


# ── Resolution ───────────────────────────────────────────────────────────────

def _fake_places(monkeypatch, suggest_rows, search_rows=()):
    async def suggest(client, q, lat, lon, limit=6, scope="us"):
        return list(suggest_rows(lat) if callable(suggest_rows) else suggest_rows)

    async def search(client, q, limit=5, near=None, scope="us"):
        return list(search_rows)

    monkeypatch.setattr(planning, "stadia_suggest", suggest)
    monkeypatch.setattr(planning, "geocode_candidates", search)


async def test_ambiguous_town_asks_instead_of_guessing(monkeypatch):
    _fake_places(monkeypatch, [
        {"name": "Springfield, Springfield, MO", "lat": 37.2, "lon": -93.3},
        {"name": "Springfield, IL", "lat": 39.8, "lon": -89.65},
    ])
    out = await planning.resolve(None, "Springfield", None, None, "origin")
    assert out["needs_clarification"] is True
    assert out["options"][0] == "Springfield, MO, USA"


async def test_famous_venue_wins_and_names_its_namesakes(monkeypatch):
    _fake_places(monkeypatch, [
        {"name": "Disneyland, Anaheim, CA", "lat": 33.81, "lon": -117.92},
        {"name": "Disneyland, Gardiner, NY", "lat": 41.73, "lon": -74.19},
    ])
    out = await planning.resolve(None, "Disneyland", None, None, "destination")
    assert out["name"].startswith("Disneyland, Anaheim")
    assert out["other_matches"] == ["Disneyland, Gardiner, NY, USA"]


async def test_lookalikes_far_away_do_not_trigger_a_question(monkeypatch):
    _fake_places(monkeypatch, [
        {"name": "Pike Place Market, Seattle, WA", "lat": 47.6096, "lon": -122.342},
        {"name": "Stafford Market Place, VA", "lat": 38.42, "lon": -77.4},
    ])
    out = await planning.resolve(None, "Pike Place Market", None, None, "origin")
    assert out["lat"] == 47.6096 and "other_matches" not in out


async def test_landmark_beats_a_nearer_namesake_and_hotels_sink(monkeypatch):
    def rows(lat):
        if lat is None:  # unbiased: popularity
            return [{"name": "San Francisco International Airport, San Francisco, CA",
                     "lat": 37.623, "lon": -122.385}]
        return [{"name": "SFOcloud, San Jose, CA", "lat": 37.33, "lon": -121.89},
                {"name": "Grand Hyatt at SFO, San Francisco, CA",
                 "lat": 37.61, "lon": -122.39}]
    _fake_places(monkeypatch, rows)
    out = await planning.resolve(None, "SFO", None, SJ, "destination")
    assert out["name"].startswith("San Francisco International Airport")
    cands = await planning.place_candidates(None, "SFO", SJ, limit=4)
    assert "Hyatt" in cands[-1][2]


async def test_coords_win_and_bad_coords_explain(monkeypatch):
    out = await planning.resolve(None, "home", "37.1,-122.2", None, "origin")
    assert (out["lat"], out["lon"], out["name"]) == (37.1, -122.2, "home")
    bad = await planning.resolve(None, None, "north", None, "origin")
    assert "origin_coords" in bad["error"]


# ── Best time to go ──────────────────────────────────────────────────────────

def _fake_ends(monkeypatch):
    async def resolve(client, place, coords, near, which):
        lat, lon = SJ if which == "origin" else SF
        return {"lat": lat, "lon": lon, "name": which}

    async def point_info(client, lat, lon):
        return {"time_zone": "America/Los_Angeles"}

    async def forecast(client, lat, lon, hours=48):
        start = datetime.now(UTC).astimezone(ZoneInfo("America/Los_Angeles")).replace(
            minute=0, second=0, microsecond=0)
        return [{"start": (start + timedelta(hours=h)).isoformat(), "temp_f": 55,
                 "precip_pct": 0, "wind_mph": 5, "forecast": "Sunny",
                 "daytime": True} for h in range(160)]

    async def alerts(client, points):
        return []

    monkeypatch.setattr(planning, "resolve", resolve)
    monkeypatch.setattr(nws_feed, "point_info", point_info)
    monkeypatch.setattr(nws_feed, "hourly_forecast", forecast)
    monkeypatch.setattr(nws_feed, "alerts_at_points", alerts)


async def test_best_time_picks_the_quiet_hour_and_names_the_rush(monkeypatch):
    _fake_ends(monkeypatch)
    monkeypatch.setattr(tomtom_feed, "api_key", lambda: "k")

    async def route_times(client, a, b, depart_at=None, *, with_points=False):
        if depart_at is None:
            return {"travel_s": 3300, "no_traffic_s": 3300, "length_m": 77_000,
                    "points": [SJ, SF] if with_points else None}
        hour = datetime.fromisoformat(depart_at).hour
        rush = {7: 4500, 8: 4800, 16: 5000, 17: 4900}
        return {"travel_s": rush.get(hour, 3600), "no_traffic_s": 3300}

    async def history(points, meters, days, tz):
        return hist.unavailable("not in tests")

    monkeypatch.setattr(tomtom_feed, "route_times", route_times)
    monkeypatch.setattr(hist, "history", history)
    out = await planning.best_time_to_go(None, "a", "b", day="tomorrow",
                                         earliest="6am", latest="8pm",
                                         step_minutes=60)
    assert out["recommended"]["minutes"] == 60
    assert out["slowest"]["leave"] == "4:00 PM"
    assert "4:00 PM" not in out["good_departures"]
    assert "Traffic is heaviest leaving" in out["summary"]
    assert len(out["departures"]) == 15
    assert out["time_zone"] == "America/Los_Angeles"


async def test_arrive_by_returns_the_latest_safe_departure(monkeypatch):
    _fake_ends(monkeypatch)
    monkeypatch.setattr(tomtom_feed, "api_key", lambda: "k")

    async def route_times(client, a, b, depart_at=None, *, with_points=False):
        return {"travel_s": 3600, "no_traffic_s": 3000, "length_m": 77_000,
                "points": [SJ, SF]}

    async def history(points, meters, days, tz):
        return hist.unavailable("not in tests")

    monkeypatch.setattr(tomtom_feed, "route_times", route_times)
    monkeypatch.setattr(hist, "history", history)
    out = await planning.best_time_to_go(None, "a", "b", arrive_by="tomorrow 9am")
    leave = datetime.fromisoformat(out["recommended"]["leave_local"])
    assert leave + timedelta(minutes=65) <= leave.replace(hour=9, minute=0)
    assert out["summary"].startswith("To arrive by 9:00 AM")


async def test_best_time_without_traffic_key_says_so(monkeypatch):
    _fake_ends(monkeypatch)
    monkeypatch.setattr(tomtom_feed, "api_key", lambda: None)
    out = await planning.best_time_to_go(None, "a", "b")
    assert "not configured" in out["error"]


# ── Plan trip ────────────────────────────────────────────────────────────────

async def test_plan_trip_orders_events_by_mile_and_keeps_plugins_out(monkeypatch):
    _fake_ends(monkeypatch)
    planning._plan_cache.clear()
    line = [(SJ[0] + (SF[0] - SJ[0]) * i / 100, SJ[1] + (SF[1] - SJ[1]) * i / 100)
            for i in range(101)]
    mid, near_end = line[50], line[90]

    async def markers(client, box, kinds):
        return [
            {"kind": "incident", "lat": near_end[0], "lon": near_end[1],
             "type": "Crash", "location": "US 101 N"},
            {"kind": "lane_closure", "lat": mid[0], "lon": mid[1],
             "label": "Right lane closed", "cls": "lane"},
            {"kind": "plugin", "source_id": "someone-elses-plugin",
             "lat": mid[0], "lon": mid[1], "label": "private"},
            {"kind": "incident", "lat": 36.0, "lon": -120.0, "type": "Far away"},
        ], []

    async def stadia(client, ms, a, b, preference):
        return None

    async def route_times(client, a, b, depart_at=None, *, with_points=False):
        return {"travel_s": 4200, "historic_s": 4000, "no_traffic_s": 3300,
                "length_m": 77_000, "points": line}

    monkeypatch.setattr(planning, "live_markers", markers)
    monkeypatch.setattr(planning, "_stadia_plan", stadia)
    monkeypatch.setattr(tomtom_feed, "route_times", route_times)
    out = await planning.plan_trip(None, "a", "b")
    assert out["traffic"]["minutes_with_traffic"] == 70
    assert out["traffic"]["traffic_delay_minutes"] == 15
    assert [e["kind"] for e in out["on_route"]["closures"]] == ["lane_closure"]
    assert out["on_route"]["incidents"][0]["summary"] == "Crash: US 101 N"
    assert out["on_route"]["closures"][0]["mile"] < out["on_route"]["incidents"][0]["mile"]
    assert "private" not in str(out)
    assert any("TomTom" in n for n in out["notes"])
    assert "1 closure, 1 incident" in out["summary"]


async def test_plan_trip_refuses_past_and_huge_trips(monkeypatch):
    _fake_ends(monkeypatch)
    planning._plan_cache.clear()
    out = await planning.plan_trip(None, "a", "b", depart_at="2020-01-01T08:00")
    assert "past" in out["error"]

    async def far(client, place, coords, near, which):
        return {"lat": 25.77, "lon": -80.19, "name": "Miami"} if which == "origin" \
            else {"lat": 47.6, "lon": -122.3, "name": "Seattle"}
    monkeypatch.setattr(planning, "resolve", far)
    out = await planning.plan_trip(None, "a", "b")
    assert "legs" in out["error"]


# ── History summary ──────────────────────────────────────────────────────────

def test_history_summary_rates_and_busiest_hours():
    rows = ([{"kind": "incident", "title": "Crash", "dow": 3, "hr": 17, "minutes": 40}] * 6
            + [{"kind": "incident", "title": "Hazard", "dow": 7, "hr": 10, "minutes": 20}] * 2
            + [{"kind": "closure", "title": "Roadwork", "dow": 2, "hr": 22, "minutes": 300}])
    out = hist.summarize(rows, 14)
    assert out["incidents"] == 8 and out["closures_started"] == 1
    assert out["busiest_hours"][0] == 17
    assert out["weekday_rate_by_hour"][17] == 0.6   # 6 over 2 weeks x 5 days
    assert out["weekend_rate_by_hour"][10] == 0.5   # 2 over 2 weeks x 2 days
    assert out["common_incident_types"][0] == {"type": "Crash", "count": 6}
    assert out["median_incident_minutes"] == 40


async def test_history_failure_is_soft(monkeypatch):
    hist._cache.clear()

    def boom(*a):
        raise RuntimeError("no credentials")
    monkeypatch.setattr(hist, "_run", boom)
    out = await hist.history([SJ], 500, 30, "America/Los_Angeles")
    assert out["available"] is False


# ── Snapshot reader ──────────────────────────────────────────────────────────

def _payload(published, markers):
    return {"schema": 1, "published": published, "markers": markers}


@respx.mock
async def test_snapshot_filters_box_and_kinds_and_only_public_plugins(monkeypatch):
    monkeypatch.setenv("MCP_SNAPSHOT_BASE", "https://snap.test")
    snapshots._state.clear()
    now = datetime.now(UTC).isoformat(timespec="seconds")
    respx.get("https://snap.test/live.json.gz").mock(return_value=httpx.Response(
        200, json=_payload(now, [
            {"kind": "incident", "lat": 47.6, "lon": -122.3, "src": "WSDOT"},
            {"kind": "incident", "lat": 40.0, "lon": -83.0, "src": "OHGO"},
            {"kind": "plugin", "source_id": "osm-cameras", "lat": 47.61, "lon": -122.31},
            {"kind": "plugin", "source_id": "waze", "lat": 47.61, "lon": -122.31},
        ]), headers={"etag": '"a"'}))
    async with httpx.AsyncClient() as c:
        got = await snapshots.markers(c, (47, -123, 48, -122), {"incident", "enforcement"})
    assert got is not None
    kinds = sorted((m["kind"], m.get("source_id")) for m in got[0])
    assert kinds == [("incident", None), ("plugin", "osm-cameras")]


@respx.mock
async def test_stale_snapshot_falls_back(monkeypatch):
    monkeypatch.setenv("MCP_SNAPSHOT_BASE", "https://snap.test")
    snapshots._state.clear()
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat(timespec="seconds")
    respx.get("https://snap.test/live.json.gz").mock(
        return_value=httpx.Response(200, json=_payload(old, [])))
    async with httpx.AsyncClient() as c:
        assert await snapshots.markers(c, (0, 0, 1, 1), {"incident"}) is None


async def test_snapshots_off_when_base_empty():
    async with httpx.AsyncClient() as c:
        assert await snapshots.markers(c, (0, 0, 1, 1), {"incident"}) is None


@pytest.mark.parametrize("period,hazard", [
    ({"forecast": "Chance Light Snow"}, "snow"),
    ({"forecast": "Patchy Fog"}, "fog"),
    ({"forecast": "Sunny", "wind_mph": 35}, "wind"),
    ({"forecast": "Sunny", "wind_mph": 10}, None),
])
def test_driving_hazard(period, hazard):
    assert nws_feed.driving_hazard(period) == hazard
