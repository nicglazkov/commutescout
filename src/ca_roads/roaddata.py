"""Facade over all feed sources sharing one HTTP client.

This is the intended entry point for consumers (the MCP server, evals, and
later projects): construct one RoadData, call its async methods, close it on
shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib
import time

import httpx

from ca_roads.feeds import calfire as calfire_feed
from ca_roads.feeds import chains as chains_feed
from ca_roads.feeds import chp as chp_feed
from ca_roads.feeds import lcs as lcs_feed
from ca_roads.feeds import portal as portal_feed
from ca_roads.feeds import wildfire as wildfire_feed
from ca_roads.models import FeedResult


def _new_client() -> httpx.AsyncClient:
    """Shared-pool client with explicit limits. The pool timeout is the
    tell for a poisoned pool (leaked connections starve it and every
    fetch dies with PoolTimeout); reset_client() is the cure."""
    return httpx.AsyncClient(
        follow_redirects=True,
        limits=httpx.Limits(max_connections=200,
                            max_keepalive_connections=20,
                            keepalive_expiry=30.0),
        timeout=httpx.Timeout(30.0, connect=10.0, pool=15.0),
    )


class RoadData:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = client is None
        self._client = client or _new_client()
        self.chp = chp_feed.ChpSource(self._client)
        self.lcs = lcs_feed.LcsSource(self._client)
        self.chains = chains_feed.ChainSource(self._client)
        self.wildfires_source = wildfire_feed.WildfireSource(self._client)
        self.calfire_source = calfire_feed.CalFireSource(self._client)
        self.cms = portal_feed.PortalSource(
            self._client, "cms", portal_feed.parse_cms, "cms")
        self.cctv = portal_feed.PortalSource(
            self._client, "cctv", portal_feed.parse_cctv, "cctv")
        self.rwis = portal_feed.PortalSource(
            self._client, "rwis", portal_feed.parse_rwis, "rwis")

    @property
    def client(self) -> httpx.AsyncClient:
        """The shared HTTP client, for consumers that make adjacent calls
        (e.g. geocoding) on the same connection pool."""
        return self._client

    def reset_client(self) -> httpx.AsyncClient:
        """Swap in a fresh connection pool after the old one is starved
        (observed in production: leaked connections turned every fetch
        into PoolTimeout for hours, and the map served only feedless
        static data). Every feed source moves to the new pool at once;
        the old client closes in the background."""
        old = self._client
        self._client = _new_client()
        self._owns_client = True
        for src in (self.chp, self.lcs, self.chains, self.wildfires_source,
                    self.calfire_source, self.cms, self.cctv, self.rwis):
            src._client = self._client
        with contextlib.suppress(Exception):
            asyncio.get_running_loop().create_task(old.aclose())
        return self._client

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def incidents(self) -> FeedResult:
        """Live CHP incidents statewide (memory-cached, background-refreshed)."""
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

    async def message_signs(
        self, districts: tuple[int, ...] | list[int] | None = None
    ) -> FeedResult:
        """CMS signs currently displaying a message (blank signs filtered)."""
        return await self.cms.get(districts)

    async def cameras(
        self, districts: tuple[int, ...] | list[int] | None = None
    ) -> FeedResult:
        """In-service roadside cameras with snapshot URLs."""
        return await self.cctv.get(districts)

    async def road_weather(
        self, districts: tuple[int, ...] | list[int] | None = None
    ) -> FeedResult:
        """Road-weather station observations (RWIS)."""
        return await self.rwis.get(districts)

    async def wildfires(self) -> FeedResult:
        """Active California wildfires: WFIGS base plus CAL FIRE
        incidents WFIGS does not list yet (both on 5-minute caches,
        deduplicated by name and distance)."""
        wfigs, calfire = await asyncio.gather(
            self.wildfires_source.get(), self.calfire_source.get())
        return calfire_feed.merge_with_wfigs(wfigs, calfire)
