"""Static map endpoint for alert emails, and the email map/deep-link
rendering that consumes it."""

import io

import pytest
import respx
from httpx import Response as HttpxResponse
from PIL import Image
from starlette.testclient import TestClient

from ca_roads_demo import watch
from ca_roads_demo.app import _STATICMAP_CACHE, app


@pytest.fixture
def client():
    _STATICMAP_CACHE.clear()
    return TestClient(app)


def fake_tile() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), (240, 238, 230)).save(buf, format="PNG")
    return buf.getvalue()


def test_staticmap_validates_inputs(client):
    assert client.get("/api/staticmap").status_code == 400
    assert client.get("/api/staticmap?lat=40.7&lon=-74.0").status_code == 404
    assert client.get("/api/staticmap?lat=37.3&lon=-121.9&z=22").status_code == 404


@respx.mock
def test_staticmap_composes_and_caches(client, monkeypatch):
    monkeypatch.setenv("STADIA_API_KEY", "test-key")
    tile_route = respx.get(
        url__regex=r"https://tiles\.stadiamaps\.com/tiles/alidade_smooth/.*"
    ).mock(return_value=HttpxResponse(200, content=fake_tile()))
    r = client.get("/api/staticmap?lat=37.3382&lon=-121.8863&z=11&k=incident")
    assert r.status_code == 200
    img = Image.open(io.BytesIO(r.content))
    assert img.size == (560, 300)
    # Marker drawn at the center in the incident color family.
    px = img.convert("RGB").getpixel((280, 150))
    assert px[0] > 150 and px[0] > px[2]  # warm marker, not basemap beige
    calls_first = tile_route.call_count
    assert calls_first > 0
    r2 = client.get("/api/staticmap?lat=37.3382&lon=-121.8863&z=11&k=incident")
    assert r2.status_code == 200
    assert tile_route.call_count == calls_first  # served from cache
    # The key travels as a query param, never a header.
    assert tile_route.calls[0].request.url.params["api_key"] == "test-key"


@respx.mock
def test_staticmap_without_key_skips_tiles(client, monkeypatch):
    """No STADIA_API_KEY: the map still renders (flat background plus
    marker) and no tile request leaves the process."""
    monkeypatch.delenv("STADIA_API_KEY", raising=False)
    tile_route = respx.get(
        url__regex=r"https://tiles\.stadiamaps\.com/.*"
    ).mock(return_value=HttpxResponse(200, content=fake_tile()))
    r = client.get("/api/staticmap?lat=37.3382&lon=-121.8863&z=11&k=incident")
    assert r.status_code == 200
    assert Image.open(io.BytesIO(r.content)).size == (560, 300)
    assert tile_route.call_count == 0


def test_email_cards_carry_maps_meta_and_focus_links():
    events = [{
        "kind": "incident", "lat": 37.3382, "lon": -121.8863,
        "title": "Collision", "body": "US-101 near San Jose",
        "meta": "CHP call logged 9:14 AM",
    }]
    subject, html, text = watch.render_alert_email("Home", events)
    assert "/api/staticmap?lat=37.3382" in html
    assert "focus=37.33820,-121.88630&amp;k=incident" in html
    assert "View on the live map" in html
    assert "CHP call logged 9:14 AM" in html
    assert "OpenStreetMap" in html  # maps credit
    assert "focus=37.33820,-121.88630&k=incident" in text


def test_email_caps_map_images_not_links():
    events = [{"kind": "fire", "lat": 38.0 + i / 100, "lon": -120.5,
               "title": f"Wildfire: F{i}", "body": "10 acres",
               "meta": "5% contained"} for i in range(6)]
    _, html, _ = watch.render_alert_email("Sierra", events)
    assert html.count("/api/staticmap") == 4  # images capped
    assert html.count("View on the live map") == 6  # links for all
