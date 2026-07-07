"""Facade over all feed sources sharing one HTTP client.

This is the intended entry point for consumers (the MCP server, evals, and
later projects): construct one RoadData, call its async methods, close it on
shutdown.
"""

from __future__ import annotations

import time

import httpx

from ca_roads.feeds import chains as chains_feed
from ca_roads.feeds import chp as chp_feed
from ca_roads.feeds import lcs as lcs_feed
from ca_roads.feeds import wildfire as wildfire_feed
from ca_roads.models import FeedResult


class RoadData:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(follow_redirects=True)
        self.chp = chp_feed.ChpSource(self._client)
        self.lcs = lcs_feed.LcsSource(self._client)
        self.chains = chains_feed.ChainSource(self._client)
        self.wildfires_source = wildfire_feed.WildfireSource(self._client)

    @property
    def client(self) -> httpx.AsyncClient:
        """The shared HTTP client, for consumers that make adjacent calls
        (e.g. geocoding) on the same connection pool."""
        return self._client

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def incidents(self) -> FeedResult:
        """Live CHP incidents statewide (fetched per request)."""
        return await self.chp.get()

    async def lane_closures(
        self,
        districts: tuple[int, ...] | list[int] | None = None,
        active_only: bool = True,
    ) -> FeedResult:
        """Caltrans LCS closures; by default only those physically in place now."""
        result = await self.lcs.get(districts)
        if active_only:
            now = int(time.time())
            result.records = [c for c in result.records if lcs_feed.is_active(c, now)]
        return result

    async def chain_controls(
        self,
        districts: tuple[int, ...] | list[int] | None = None,
        active_only: bool = True,
    ) -> FeedResult:
        """Chain-control checkpoints; by default only those above R-0."""
        result = await self.chains.get(districts)
        if active_only:
            result.records = [c for c in result.records if chains_feed.is_active(c)]
        return result

    async def wildfires(self) -> FeedResult:
        """Active California wildfires (5-minute cache)."""
        return await self.wildfires_source.get()
