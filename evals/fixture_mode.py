"""Serve recorded fixtures instead of the live feeds.

``fixture_road_data(scenario)`` returns a RoadData whose HTTP client answers
every feed URL from evals/fixtures/<scenario>/. Missing files answer 404,
which the feed layer already treats as "district publishes no feed".
"""

from __future__ import annotations

from pathlib import Path

import httpx

from ca_roads.roaddata import RoadData
from evals.record import feed_urls

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_transport(scenario: str) -> httpx.MockTransport:
    scenario_dir = FIXTURES / scenario
    if not scenario_dir.is_dir():
        raise FileNotFoundError(f"no fixture scenario at {scenario_dir}")
    by_path: dict[str, Path] = {}
    for filename, url in feed_urls().items():
        parsed = httpx.URL(url)
        by_path[f"{parsed.host}{parsed.path}"] = scenario_dir / filename

    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.url.host}{request.url.path}"
        path = by_path.get(key)
        if path is None or not path.exists():
            return httpx.Response(404)
        content_type = (
            "application/json" if path.suffix == ".json" else "application/xml"
        )
        return httpx.Response(
            200, content=path.read_bytes(), headers={"content-type": content_type}
        )

    return httpx.MockTransport(handler)


def fixture_client(scenario: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=fixture_transport(scenario))


def fixture_road_data(scenario: str) -> RoadData:
    return RoadData(client=fixture_client(scenario))
