import httpx
import pytest
import respx

from ca_roads_demo import analytics


@respx.mock
async def test_fetch_aggregates_with_sampling(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_SITE_TAG", "site")
    cf = {"data": {"viewer": {"accounts": [{
        "byDay": [
            {"count": 10, "sum": {"visits": 4}, "avg": {"sampleInterval": 1},
             "dimensions": {"date": "2026-07-15"}},
            {"count": 5, "sum": {"visits": 2}, "avg": {"sampleInterval": 2},
             "dimensions": {"date": "2026-07-16"}},
        ],
        "topPages": [{"count": 8, "avg": {"sampleInterval": 1},
                      "dimensions": {"requestPath": "/"}}],
        "topReferers": [{"count": 3, "avg": {"sampleInterval": 1},
                         "dimensions": {"refererHost": "google.com"}}],
        "topCountries": [{"count": 9, "avg": {"sampleInterval": 1},
                          "dimensions": {"countryName": "United States"}}],
    }]}}, "errors": None}
    route = respx.post(analytics.CF_GRAPHQL).mock(
        return_value=httpx.Response(200, json=cf))

    data = await analytics._fetch("7d")
    assert data["ok"]
    # sampleInterval is applied per group: 10*1 + 5*2 pageviews, 4*1 + 2*2 visits
    assert data["pageviews"] == 20
    assert data["visitors"] == 8
    assert len(data["series"]) == 2
    assert data["top_pages"][0] == {"name": "/", "views": 8}
    assert data["top_referrers"][0]["name"] == "google.com"
    assert data["top_countries"][0] == {"name": "United States", "views": 9}
    body = route.calls.last.request.content.decode()
    assert "site" in body and "acct" in body  # filtered by our site tag + account


async def test_fetch_unconfigured_returns_error(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_SITE_TAG", raising=False)
    data = await analytics._fetch("7d")
    assert not data["ok"]
    assert "not configured" in data["error"]


@respx.mock
async def test_fetch_raises_on_graphql_error(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_SITE_TAG", "site")
    respx.post(analytics.CF_GRAPHQL).mock(
        return_value=httpx.Response(200, json={"data": None,
                                               "errors": [{"message": "bad"}]}))
    with pytest.raises(RuntimeError):
        await analytics._fetch("7d")
