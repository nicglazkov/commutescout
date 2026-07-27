"""Toll price history logging: parsing, change detection, cache peek."""

import pytest

from ca_roads_demo import tollprices

BAY = {"kind": "toll", "src": "511.org", "pricing": "live",
       "name": "I-880 NB: I-880 NB - Whipple - 2",
       "price": 7.0,
       "lines": ["to Whipple - 3: $7.00", "to Hesperian/238 - 6: $15.00"]}
WSDOT = {"kind": "toll", "src": "WSDOT", "pricing": "live",
         "name": "099 S: SB S Portal to NB S Portal", "price": 1.25}
NTTA = {"kind": "toll", "src": "NTTA", "pricing": "fixed",
        "name": "SRT NB FROM N JOSEY LANE/MAIN STREET ON RAMP:"
                " Josey Lane - North (NJOLN)", "price": 0.89}
HCTRA = {"kind": "toll", "src": "HCTRA", "pricing": "fixed",
         "name": "Sam Houston: West Rd (Gantry Ramp-On)", "price": 0.81,
         "lines": []}


def test_corridor_and_entry_parsing():
    assert tollprices.corridor_key(BAY) == "I-880 NB"
    assert tollprices.entry_label(BAY) == "Whipple"
    assert tollprices.corridor_key(WSDOT) == "099 S"
    assert tollprices.entry_label(WSDOT) == "SB S Portal to NB S Portal"
    assert tollprices.corridor_key(NTTA) == "SRT NB"
    assert tollprices.entry_label(NTTA) == "Josey Lane - North"
    assert tollprices.corridor_key(HCTRA) == "Sam Houston"
    assert tollprices.entry_label(HCTRA) == "West Rd (Gantry Ramp-On)"


def test_price_rows_strip_sign_codes_and_fall_back_to_price():
    assert tollprices.price_rows(BAY) == [("Whipple", 7.0),
                                          ("Hesperian/238", 15.0)]
    assert tollprices.price_rows(WSDOT) == [("", 1.25)]
    assert tollprices.price_rows({"price": None}) == []


class FakeBQ:
    def __init__(self):
        self.rows = []

    def insert_rows_json(self, table, rows):
        self.rows.extend(rows)
        return []


@pytest.fixture
def bq(monkeypatch):
    fake = FakeBQ()
    monkeypatch.setattr(tollprices, "_bq", lambda: fake)
    monkeypatch.setattr(tollprices, "_last", {})
    return fake


def test_rows_written_once_and_only_on_change(bq):
    out = tollprices.observe_sync([BAY, WSDOT])
    assert out["archived"] == 3  # two Bay destinations + one WSDOT trip
    # Same prices next cycle: nothing new.
    out = tollprices.observe_sync([BAY, WSDOT])
    assert out["archived"] == 0
    # One destination moves: exactly one row.
    moved = dict(BAY, lines=["to Whipple - 3: $9.00",
                             "to Hesperian/238 - 6: $15.00"])
    out = tollprices.observe_sync([moved, WSDOT])
    assert out["archived"] == 1
    assert bq.rows[-1]["dest"] == "Whipple" and bq.rows[-1]["price"] == 9.0
    assert bq.rows[-1]["corridor"] == "I-880 NB"


def test_non_toll_markers_ignored(bq):
    out = tollprices.observe_sync([{"kind": "incident", "price": 4}])
    assert out["archived"] == 0


def test_cache_peek_never_fetches(monkeypatch):
    from ca_roads.cache import TTLCache
    from ca_roads_demo import states

    cache = TTLCache()
    monkeypatch.setattr(states, "_cache", cache)
    cache._entries["toll:bay"] = type(
        "E", (), {"value": {"markers": [BAY]}})()
    cache._entries["wzdx:ia"] = type(
        "E", (), {"value": {"markers": [{"kind": "incident"}]}})()
    out = tollprices.cached_toll_markers()
    assert out == [BAY]
