"""Who the Waze relay believes, and how much.

The relay is listed publicly with no authentication and what it serves is
drawn on a map people drive by, so the interesting cases here are the ones
where a caller is lying: inventing voters to hide an alert, inventing a
forwarded address to get a fresh rate-limit bucket, or guessing a token one
byte at a time.
"""

from __future__ import annotations

import time

import clientip
import httpx
import pytest
import server as relay
from store import Store, Votes
from waze.cache import AlertQueryResult, WazeAlert
from waze.source import WazeSource

LA = (34.05, -118.25)


def _no_network(_: httpx.Request) -> httpx.Response:
    raise AssertionError("a unit test must never call out")


def _alert(uuid="abc-123") -> WazeAlert:
    return WazeAlert(uuid, 42, "POLICE", "POLICE_VISIBLE", LA[1], LA[0], 270,
                     int((time.time() - 60) * 1000), 3, "I-110 N", "Los Angeles")


def _store() -> Store:
    source = WazeSource(httpx.AsyncClient(transport=httpx.MockTransport(_no_network)))
    source.cache.submit(AlertQueryResult([_alert()], []))
    store = Store(source, bbox=relay.BBOX, refresh_s=60)
    source.last_ok = store._now()
    return store


def _client(store) -> httpx.AsyncClient:
    relay.store = store
    relay._buckets.clear()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=relay.app),
                             base_url="http://localhost")


async def _vote(client, *, address, reporter, vote="gone", token=None):
    headers = {"x-forwarded-for": f"10.0.0.1, {address}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return await client.post("/flare/v1/confirm", headers=headers,
                             json={"alert_id": "wz:abc-123", "vote": vote,
                                   "reporter": reporter})


# ------------------------------------------------- hiding an alert


async def test_invented_reporters_from_one_address_cannot_hide_an_alert():
    """The finding: three requests, three made-up strings, alert gone."""
    store = _store()
    async with _client(store) as client:
        for i in range(6):
            response = await _vote(client, address="203.0.113.7", reporter=f"made-up-{i}")
            assert response.status_code == 200
    assert store.records(), "an unsigned caller must not be able to hide an alert"
    assert not store.votes.hidden("wz:abc-123")


async def test_three_distinct_addresses_still_hide_an_alert():
    store = _store()
    async with _client(store) as client:
        for i, address in enumerate(("203.0.113.7", "198.51.100.4", "192.0.2.9")):
            assert store.records(), "not hidden before the third"
            await _vote(client, address=address, reporter=f"someone-{i}")
    assert store.votes.hidden("wz:abc-123")
    assert store.records() == []


async def test_one_address_rotating_the_low_bits_of_an_ipv6_counts_once():
    store = _store()
    async with _client(store) as client:
        for i in range(5):
            await _vote(client, address=f"2001:db8:1:2::{i + 1}", reporter=f"r-{i}")
    assert not store.votes.hidden("wz:abc-123"), "a /64 is one voter"


async def test_a_trusted_caller_is_believed_about_who_is_voting(monkeypatch):
    """A mediated backend is one address forwarding many people's votes, so
    once it has shown its token its reporter strings count separately."""
    monkeypatch.setattr(relay, "CONFIRM_TOKEN", "confirm-secret")
    store = _store()
    async with _client(store) as client:
        for i in range(3):
            await _vote(client, address="203.0.113.7", reporter=f"r:person-{i}",
                        token="confirm-secret")
    assert store.votes.hidden("wz:abc-123")


async def test_the_wrong_token_buys_nothing(monkeypatch):
    monkeypatch.setattr(relay, "CONFIRM_TOKEN", "confirm-secret")
    store = _store()
    async with _client(store) as client:
        for i in range(4):
            await _vote(client, address="203.0.113.7", reporter=f"r:person-{i}",
                        token="confirm-secre")          # one byte short
    assert not store.votes.hidden("wz:abc-123")


# ------------------------------------- manufacturing a confirmed alert


async def test_invented_reporters_cannot_run_up_the_confirmation_count():
    """n_confirmations is not decoration. A router downstream reads it and
    may send every driver around a well confirmed closure, so an anonymous
    caller that could inflate it could close a road."""
    store = _store()
    async with _client(store) as client:
        for i in range(8):
            await _vote(client, address="203.0.113.7", reporter=f"made-up-{i}", vote="up")
    record = store.records()[0]
    assert record["n_confirmations"] == 3, "the upstream count, and only that"
    assert record["reliability"] == pytest.approx(0.8)


async def test_many_addresses_cannot_run_up_the_confirmation_count_either():
    store = _store()
    async with _client(store) as client:
        for i in range(8):
            await _vote(client, address=f"203.0.113.{i}", reporter=f"r-{i}", vote="up")
    assert store.records()[0]["n_confirmations"] == 3


async def test_an_up_vote_from_nobody_cannot_keep_a_cleared_alert_alive():
    """The alert's life is anchored on confirm_ts, so a caller that could
    move it would hold a cleared report on the map indefinitely."""
    store = _store()
    async with _client(store) as client:
        for i in range(5):
            await _vote(client, address=f"203.0.113.{i}", reporter=f"r-{i}", vote="up")
    assert "confirm_ts" not in store.records()[0]
    assert store.votes.confirmed_at("wz:abc-123") is None


async def test_a_trusted_voter_may_confirm_and_prolong(monkeypatch):
    monkeypatch.setattr(relay, "CONFIRM_TOKEN", "confirm-secret")
    store = _store()
    async with _client(store) as client:
        for i in range(2):
            await _vote(client, address="203.0.113.7", reporter=f"r:person-{i}",
                        vote="up", token="confirm-secret")
    record = store.records()[0]
    assert record["n_confirmations"] == 5, "three upstream plus two trusted"
    assert "confirm_ts" in record


def test_a_trusted_voter_and_an_untrusted_one_cannot_collide():
    trusted = Votes.voter("someone", "203.0.113.7", trusted=True)
    spoofed = Votes.voter("t:someone", "203.0.113.7", trusted=False)
    assert trusted != spoofed
    assert trusted == "t:someone"
    assert spoofed == "a:203.0.113.7"


def test_up_votes_still_count_per_reporter_for_a_trusted_caller():
    votes = Votes()
    for i in range(3):
        votes.add("wz:1", "up", Votes.voter(f"r:person-{i}", "203.0.113.7", trusted=True))
    assert votes.ups("wz:1") == 3
    assert votes.confirmed_at("wz:1") is not None


def test_anonymous_votes_may_weaken_an_alert_but_never_strengthen_it():
    """The asymmetry the trust split buys, stated as one rule."""
    votes = Votes()
    for i, address in enumerate(("203.0.113.7", "198.51.100.4", "192.0.2.9")):
        votes.add("wz:1", "up", Votes.voter(f"r-{i}", address, trusted=False))
        votes.add("wz:2", "gone", Votes.voter(f"r-{i}", address, trusted=False))
    assert votes.ups("wz:1") == 0, "anonymous callers cannot manufacture confidence"
    assert votes.confirmed_at("wz:1") is None
    assert votes.hidden("wz:2"), "but they can still say something is not there"


async def test_votes_are_rate_limited_harder_than_reads(monkeypatch):
    monkeypatch.setattr(relay, "CONFIRM_PER_MIN", 3)
    store = _store()
    async with _client(store) as client:
        codes = [(await _vote(client, address="203.0.113.7", reporter=f"r-{i}",
                              vote="up")).status_code for i in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]


# ------------------------------------------------- which address counts


def test_the_last_forwarded_entry_is_the_one_infrastructure_vouched_for():
    # Cloud Run appends what it saw, so a caller's own header is a prefix.
    assert clientip.trusted_client_ip("1.2.3.4, 203.0.113.7", "10.0.0.1") == "203.0.113.7"
    assert clientip.trusted_client_ip("203.0.113.7", "10.0.0.1") == "203.0.113.7"
    assert clientip.trusted_client_ip(None, "10.0.0.1") == "10.0.0.1"
    assert clientip.trusted_client_ip("", None) == "unknown"
    assert clientip.trusted_client_ip("  1.2.3.4 ,  203.0.113.7 ", None) == "203.0.113.7"


def test_a_spoofed_forwarded_header_does_not_buy_a_fresh_bucket():
    spoofed = [clientip.trusted_client_ip(f"{i}.{i}.{i}.{i}, 203.0.113.7", "10.0.0.1")
               for i in range(1, 6)]
    assert set(spoofed) == {"203.0.113.7"}, "one caller, one bucket"


def test_ipv6_is_folded_to_its_allocation_and_ipv4_is_not():
    assert clientip.limiter_key("2001:db8:1:2::1") == "2001:db8:1:2::/64"
    assert clientip.limiter_key("2001:db8:1:2::ffff") == "2001:db8:1:2::/64"
    assert clientip.limiter_key("2001:db8:1:3::1") == "2001:db8:1:3::/64"
    assert clientip.limiter_key("203.0.113.7") == "203.0.113.7"
    assert clientip.limiter_key("::ffff:203.0.113.7") == "203.0.113.7"
    assert clientip.limiter_key("unknown") == "unknown"


async def test_the_limit_is_per_caller_not_one_bucket_for_the_whole_proxy(monkeypatch):
    monkeypatch.setattr(relay, "RATE_PER_MIN", 2)
    store = _store()
    async with _client(store) as client:
        async def read(address):
            return (await client.get(
                "/flare/v1/alerts", headers={"x-forwarded-for": f"10.0.0.1, {address}"},
                params={"lat": LA[0], "lon": LA[1], "r": 25_000})).status_code

        assert [await read("203.0.113.7") for _ in range(3)] == [200, 200, 429]
        # A different caller behind the same proxy is not punished for it.
        assert await read("198.51.100.4") == 200


async def test_quiet_addresses_are_pruned_so_the_map_cannot_grow_forever():
    store = _store()
    async with _client(store) as client:
        for i in range(50):
            await client.get("/flare/v1/alerts",
                             headers={"x-forwarded-for": f"10.0.0.1, 203.0.113.{i}"},
                             params={"lat": LA[0], "lon": LA[1], "r": 25_000})
        assert len(relay._buckets) == 50
        # Everything ages out after a minute of quiet.
        relay._pruned_at = time.monotonic() - 61
        for key in relay._buckets:
            relay._buckets[key] = [time.monotonic() - 61]
        relay._prune_buckets(time.monotonic())
    assert relay._buckets == {}


# ------------------------------------------------- token comparison


def test_a_token_is_compared_whole_not_byte_by_byte(monkeypatch):
    monkeypatch.setattr(relay, "TOKEN", "sixteen-byte-key")
    assert relay._matches("Bearer sixteen-byte-key", relay.TOKEN)
    assert not relay._matches("Bearer sixteen-byte-ke", relay.TOKEN)
    assert not relay._matches("Bearer s", relay.TOKEN)
    assert not relay._matches("sixteen-byte-key", relay.TOKEN)
    assert not relay._matches(None, relay.TOKEN)
    assert not relay._matches("Bearer anything", None), "no secret trusts nobody"


def test_the_comparison_is_the_constant_time_one():
    """Pin the mechanism, because the bug it prevents is invisible in the
    output: a timing leak and a correct answer look identical from here."""
    names = relay._matches.__code__.co_names
    assert "compare_digest" in names
    # A plain == on the secret compiles to a COMPARE_OP against the header.
    import dis

    compares = [i.argrepr for i in dis.get_instructions(relay._matches)
                if i.opname == "COMPARE_OP"]
    assert compares == [], f"the secret must not be compared with {compares}"


@pytest.fixture(autouse=True)
def _restore_module_state():
    before = (relay.store, relay.TOKEN, relay.CONFIRM_TOKEN,
              relay.RATE_PER_MIN, relay.CONFIRM_PER_MIN)
    yield
    (relay.store, relay.TOKEN, relay.CONFIRM_TOKEN,
     relay.RATE_PER_MIN, relay.CONFIRM_PER_MIN) = before
    relay._buckets.clear()
