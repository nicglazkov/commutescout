"""Recording mode: capture all raw feed responses into a scenario directory.

Usage:
    python evals/record.py <scenario-name>

Writes evals/fixtures/<scenario-name>/ with the raw bytes of every feed the
server uses (CHP statewide, LCS and chain controls for all 12 districts,
WFIGS query) plus a manifest with timestamps and HTTP statuses. Run this on
an interesting day (a Sierra storm, a fire closure) to bank a real scenario.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ca_roads.feeds import chains, chp, lcs, wildfire
from ca_roads.geo import ALL_DISTRICTS

FIXTURES = Path(__file__).parent / "fixtures"


def feed_urls() -> dict[str, str]:
    urls = {"chp.xml": chp.CHP_URL}
    for d in ALL_DISTRICTS:
        urls[f"lcs_d{d:02d}.xml"] = lcs.feed_url(d)
        urls[f"cc_d{d:02d}.xml"] = chains.feed_url(d)
    wfigs = httpx.URL(wildfire.QUERY_URL, params=wildfire.QUERY_PARAMS)
    urls["wfigs.json"] = str(wfigs)
    return urls


async def record(scenario: str) -> None:
    out = FIXTURES / scenario
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "scenario": scenario,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": {},
    }
    async with httpx.AsyncClient(
        headers={"User-Agent": "ca-roads-mcp fixture recorder"}, timeout=60
    ) as client:
        for filename, url in feed_urls().items():
            try:
                resp = await client.get(url)
                (out / filename).write_bytes(resp.content)
                manifest["files"][filename] = {
                    "url": url,
                    "status": resp.status_code,
                    "bytes": len(resp.content),
                }
                print(f"{filename}: {resp.status_code} ({len(resp.content)} bytes)")
            except httpx.HTTPError as exc:
                manifest["files"][filename] = {"url": url, "error": str(exc)}
                print(f"{filename}: FAILED {exc}")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nRecorded to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python evals/record.py <scenario-name>")
    asyncio.run(record(sys.argv[1]))
