import json

import httpx
import pytest
import respx

from ca_roads.feeds import portal

CMS_PAYLOAD = {
    "data": [
        {"cms": {
            "index": "1", "inService": "true",
            "location": {"district": "3", "route": "I-80", "county": "Placer",
                         "nearbyPlace": "Applegate", "direction": "East",
                         "latitude": "39.0", "longitude": "-120.99"},
            "message": {"display": "1 Page (Normal)",
                        "phase1": {"phase1Line1": "CHAINS REQUIRED",
                                   "phase1Line2": "10 MI AHEAD",
                                   "phase1Line3": ""},
                        "phase2": {"phase2Line1": "", "phase2Line2": "",
                                   "phase2Line3": ""}},
        }},
        {"cms": {  # blank sign: filtered
            "index": "2", "inService": "true",
            "location": {"district": "3", "route": "I-80"},
            "message": {"display": "Blank", "phase1": {}, "phase2": {}},
        }},
        {"cms": {  # out of service: filtered
            "index": "3", "inService": "false",
            "location": {"district": "3", "route": "I-80"},
            "message": {"display": "1 Page (Normal)",
                        "phase1": {"phase1Line1": "TEST"}, "phase2": {}},
        }},
    ]
}


def test_cms_keeps_blank_signs_with_empty_text():
    signs = portal.parse_cms(json.dumps(CMS_PAYLOAD).encode(), 3)
    # displaying sign + blank sign; the out-of-service one stays filtered
    assert len(signs) == 2
    displaying = [s for s in signs if s.text]
    blanks = [s for s in signs if not s.text]
    assert displaying[0].text == "CHAINS REQUIRED / 10 MI AHEAD"
    assert displaying[0].route == "I-80"
    assert len(blanks) == 1


def test_cctv_requires_service_and_image():
    payload = {"data": [
        {"cctv": {"index": "1", "inService": "true",
                  "location": {"district": "3", "route": "I-80",
                               "locationName": "Hwy 80 at Donner Lake",
                               "latitude": "39.32", "longitude": "-120.26"},
                  "imageData": {"streamingVideoURL": "",
                                "static": {"currentImageURL": "https://x/d.jpg"}}}},
        {"cctv": {"index": "2", "inService": "false",
                  "location": {"district": "3"},
                  "imageData": {"static": {"currentImageURL": "https://x/e.jpg"}}}},
        {"cctv": {"index": "3", "inService": "true",
                  "location": {"district": "3"},
                  "imageData": {"static": {"currentImageURL": ""}}}},
    ]}
    cams = portal.parse_cctv(json.dumps(payload).encode(), 3)
    assert len(cams) == 1
    assert cams[0].image_url == "https://x/d.jpg"


def test_rwis_converts_ntcip_units_and_sentinels():
    payload = {"data": [{"rwis": {
        "index": "1", "inService": "true",
        "location": {"district": "3", "route": "I-80",
                     "locationName": "Hwy 80 at Blue Canyon",
                     "latitude": "39.28", "longitude": "-120.70"},
        "rwisData": {
            "temperatureData": {"essTemperatureSensorTable": [
                {"essTemperatureSensorEntry": {"essAirTemperature": "246"}}]},
            "windData": {"essAvgWindSpeed": "50", "essMaxWindGustSpeed": "65535"},
            "visibilityData": {"essVisibility": "38565"},
            "humidityPrecipData": {"essPrecipRate": "0"},
        },
    }}]}
    stations = portal.parse_rwis(json.dumps(payload).encode(), 3)
    w = stations[0]
    assert w.air_temp_c == 24.6           # tenths of a degree C
    assert w.wind_avg_mph == 11.2         # tenths of m/s -> mph
    assert w.wind_gust_mph is None        # 65535 sentinel dropped
    assert w.visibility_m == 3856.5       # decimeters -> meters


@pytest.mark.anyio
@respx.mock
async def test_missing_district_is_empty_not_error():
    for d in range(1, 13):
        respx.get(portal.feed_url("cms", d)).mock(
            return_value=httpx.Response(
                200, json=CMS_PAYLOAD if d == 3 else {"data": []})
            if d != 12 else httpx.Response(404)
        )
    async with httpx.AsyncClient() as client:
        source = portal.PortalSource(client, "cms", portal.parse_cms, "cms")
        result = await source.get()
    assert result.ok
    assert len(result.records) == 2  # displaying + blank from district 3


@pytest.mark.anyio
async def test_camera_liveness_filter():
    from ca_roads_mcp import server as srv

    class Cam:
        def __init__(self, url):
            self.image_url = url

    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    now = format_datetime(datetime.now(UTC))
    old_stamp = format_datetime(datetime.now(UTC) - timedelta(hours=6))
    # A small night frame with a fresh timestamp is live; a stale file is
    # a placeholder no matter its size.
    night_frame = b"\xff\xd8" + b"x" * 6_000
    stale_big = b"\xff\xd8" + b"x" * 30_000

    def handler(request):
        if "live" in str(request.url):
            return httpx.Response(200, content=night_frame,
                                  headers={"content-type": "image/jpeg",
                                           "last-modified": now})
        if "dead" in str(request.url):
            return httpx.Response(200, content=stale_big,
                                  headers={"content-type": "image/jpeg",
                                           "last-modified": old_stamp})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    road = srv.get_road()
    original = road._client
    road._client = httpx.AsyncClient(transport=transport)
    try:
        cams = [Cam("https://x/live1.jpg"), Cam("https://x/dead.jpg"),
                Cam("https://x/gone.jpg"), Cam("https://x/live2.jpg")]
        live, dropped = await srv._live_cameras(cams, limit=5)
    finally:
        await road._client.aclose()
        road._client = original
    assert [c.image_url for c in live] == ["https://x/live1.jpg", "https://x/live2.jpg"]
    assert dropped == 2
