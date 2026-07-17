"""Cloudflare Web Analytics (RUM) for the admin portal.

Reads the site's Real-User-Monitoring data through Cloudflare's GraphQL
Analytics API, server-side only: the API token lives in Secret Manager
(``CLOUDFLARE_API_TOKEN``) and never reaches the browser. Results are cached
briefly so opening the admin page doesn't hammer Cloudflare, and the endpoint
is admin-gated by the same check the rest of the admin API uses.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse

from ca_roads.cache import TTLCache
from ca_roads_demo.watch import _require_admin

CF_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
RANGES = {"24h": 1, "7d": 7, "30d": 30}

_cache = TTLCache()
_TTL_SECONDS = 300.0       # one Cloudflare fetch per range per 5 minutes
_MAX_SERVE_SECONDS = 3600.0

# One request, four groupings: a daily series plus the three top-N lists.
_QUERY = (
    "query($a:String!,$s:String!,$since:Time!,$until:Time!){viewer{accounts(filter:{accountTag:$a}){"
    "byDay:rumPageloadEventsAdaptiveGroups(filter:{siteTag:$s,datetime_geq:$since,datetime_leq:$until},"
    "limit:1000,orderBy:[date_ASC]){count sum{visits} avg{sampleInterval} dimensions{date}}"
    "topPages:rumPageloadEventsAdaptiveGroups(filter:{siteTag:$s,datetime_geq:$since,datetime_leq:$until},"
    "limit:10,orderBy:[count_DESC]){count avg{sampleInterval} dimensions{requestPath}}"
    "topReferers:rumPageloadEventsAdaptiveGroups(filter:{siteTag:$s,datetime_geq:$since,datetime_leq:$until},"
    "limit:10,orderBy:[count_DESC]){count avg{sampleInterval} dimensions{refererHost}}"
    "topCountries:rumPageloadEventsAdaptiveGroups(filter:{siteTag:$s,datetime_geq:$since,datetime_leq:$until},"
    "limit:10,orderBy:[count_DESC]){count avg{sampleInterval} dimensions{countryName}}"
    "}}}"
)


def _est(row: dict) -> tuple[int, int]:
    """Estimated (pageviews, visits) from one sampled RUM group.

    Cloudflare adaptively samples: each returned event stands in for
    ``sampleInterval`` real events, so multiply the raw counts by it.
    """
    interval = (row.get("avg") or {}).get("sampleInterval") or 1
    count = row.get("count") or 0
    visits = (row.get("sum") or {}).get("visits") or 0
    return round(count * interval), round(visits * interval)


def _top(rows: list | None, dim: str) -> list[dict]:
    out = []
    for r in rows or []:
        pv, _ = _est(r)
        out.append({"name": (r.get("dimensions") or {}).get(dim) or "(none)",
                    "views": pv})
    return out


async def _fetch(range_key: str) -> dict:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    site = os.environ.get("CLOUDFLARE_SITE_TAG", "")
    if not (token and account and site):
        return {"ok": False, "error": "analytics not configured"}
    until = datetime.now(UTC)
    since = until - timedelta(days=RANGES.get(range_key, 7))
    variables = {
        "a": account, "s": site,
        "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "until": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            CF_GRAPHQL,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"query": _QUERY, "variables": variables},
        )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(f"cloudflare graphql: {payload['errors'][:1]}")
    accounts = (((payload.get("data") or {}).get("viewer") or {}).get("accounts") or [])
    acct = accounts[0] if accounts else {}
    series: list[dict] = []
    total_pv = total_vis = 0
    for row in acct.get("byDay") or []:
        pv, vis = _est(row)
        total_pv += pv
        total_vis += vis
        series.append({"date": (row.get("dimensions") or {}).get("date"),
                       "views": pv, "visits": vis})
    return {
        "ok": True,
        "range": range_key,
        "pageviews": total_pv,
        "visitors": total_vis,
        "series": series,
        "top_pages": _top(acct.get("topPages"), "requestPath"),
        "top_referrers": _top(acct.get("topReferers"), "refererHost"),
        "top_countries": _top(acct.get("topCountries"), "countryName"),
    }


async def fetch_web_analytics(range_key: str) -> dict:
    """Cached analytics for a range. A failed live fetch serves the last good
    snapshot (via the TTL cache's stale-serve) rather than erroring."""
    if range_key not in RANGES:
        range_key = "7d"
    outcome = await _cache.get(
        range_key, _TTL_SECONDS, _MAX_SERVE_SECONDS, lambda: _fetch(range_key))
    if outcome.value is not None:
        return outcome.value
    return {"ok": False, "error": outcome.error or "analytics unavailable"}


async def api_admin_analytics(request: Request) -> JSONResponse:
    """Admin-only: Cloudflare Web Analytics for the site. The token is used
    server-side; the browser only ever sees aggregated numbers."""
    if not await _require_admin(request):
        return JSONResponse({"error": "admin only"}, status_code=403)
    return JSONResponse(await fetch_web_analytics(
        request.query_params.get("range") or "7d"))
