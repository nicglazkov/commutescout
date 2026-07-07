"""Serve recorded fixtures instead of the live feeds.

``fixture_road_data(scenario)`` returns a RoadData whose HTTP client answers
every feed URL from evals/fixtures/<scenario>/. Missing files answer 404,
which the feed layer already treats as "district publishes no feed".
"""

from __future__ import annotations

import gzip
import json
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
    statuses: dict[str, int] = {}
    manifest = scenario_dir / "manifest.json"
    if manifest.exists():
        recorded = json.loads(manifest.read_text()).get("files", {})
        statuses = {
            name: info["status"]
            for name, info in recorded.items()
            if isinstance(info, dict) and "status" in info
        }
    for filename, url in feed_urls().items():
        parsed = httpx.URL(url)
        by_path[f"{parsed.host}{parsed.path}"] = scenario_dir / filename

    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.url.host}{request.url.path}"
        path = by_path.get(key)
        if path is None:
            return httpx.Response(404)
        # Real recordings are committed gzipped (raw captures run ~36 MB).
        if path.exists():
            content = path.read_bytes()
        elif path.with_name(path.name + ".gz").exists():
            content = gzip.decompress(
                path.with_name(path.name + ".gz").read_bytes()
            )
        else:
            return httpx.Response(404)
        content_type = (
            "application/json" if path.suffix == ".json" else "application/xml"
        )
        # Real recordings replay the status the feed actually answered
        # (a district's 500 must stay a 500, not become a parseable 200).
        status = statuses.get(path.name, 200)
        return httpx.Response(
            status, content=content, headers={"content-type": content_type}
        )

    return httpx.MockTransport(handler)


def fixture_client(scenario: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=fixture_transport(scenario))


def fixture_road_data(scenario: str) -> RoadData:
    return RoadData(client=fixture_client(scenario))
