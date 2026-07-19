"""Expansion-state adapters: NE Compass (ME/NH/VT) and Iowa WZDx."""

import base64

from ca_roads_demo import states

NS = 'xmlns="http://its.gov/c2c_icd"'

NEC_BUNDLE = f"""<?xml version="1.0"?>
<status {NS}><incidentData><net id="Maine" name="Maine">
<incident id="ME26-1" netId="Maine" {NS}>
  <desc>Crash on I-95 northbound near Bangor</desc>
  <startLocation><state>Maine</state><county>Penobscot</county>
    <city>Bangor</city><roadway>I-95</roadway><direction>North</direction>
    <lat>44801200</lat><lon>-68777800</lon></startLocation>
  <status>Verified</status><severity>Medium</severity>
  <eventType>Crash</eventType>
  <confirmedDate>7/19/2026</confirmedDate><confirmedTime>08:15:00</confirmedTime>
</incident></net></incidentData>
<laneClosureData><net id="Maine" name="Maine">
<laneClosure id="ME26-2" netId="Maine" {NS}>
  <desc>Bridge work, single lane</desc>
  <startLocation><county>Sagadahoc</county><roadway>US-201</roadway>
    <direction>North</direction><lat>43920586</lat><lon>-69965958</lon></startLocation>
  <endLocation><lat>43930000</lat><lon>-69970000</lon></endLocation>
  <midpoints><point><order>0</order><lat>43925000</lat><lon>-69967000</lon></point></midpoints>
  <affectedLanesDetail>
    <laneDetails type="MainLane" status="Blocked" index="0" />
    <laneDetails type="MainLane" status="Cleared" index="1" />
  </affectedLanesDetail>
</laneClosure></net></laneClosureData>
<dmsData><net id="Maine" name="Maine">
<dms id="I-295 Mile 02 NB" netId="Maine" {NS}>
  <name>I-295 Mile 02 NB</name><lat>43633380</lat><lon>-70305809</lon>
  <status>Device Online</status>
  <message>[jl3]CRASH AHEAD[nl]USE CAUTION[np]EXPECT DELAYS</message>
  <equipLoc><roadway>I-295</roadway><direction>North</direction>
    <locationDescription>I-295 Mile 02 NB</locationDescription></equipLoc>
</dms>
<dms id="OFFLINE-1" netId="Maine" {NS}>
  <name>Offline sign</name><lat>43700000</lat><lon>-70300000</lon>
  <status>Device Offline</status><message>OLD</message>
</dms></net></dmsData>
<essData><net id="Maine" name="Maine">
<ess id="77" netId="Maine" {NS}>
  <name>RWIS Soucey</name><lat>46915150</lat><lon>-68516280</lon>
  <status>Device Online</status><visibility>1290</visibility>
  <windSpeed>18</windSpeed><airTemp>158</airTemp><pavementTemp>160</pavementTemp>
  <equipLoc><roadway>ME-11</roadway></equipLoc>
</ess></net></essData>
<cctvStatusData><net id="Maine" name="Maine">
<cctvStatus id="I-95 NB at MM 25 Kennebunk" netId="Maine" {NS}>
  <name>I-95 NB at MM 25 Kennebunk</name>
  <lat>43391000</lat><lon>-70543000</lon><status>Device Online</status>
</cctvStatus></net></cctvStatusData></status>""".encode()

JPEG = b"\xff\xd8\xff\xe0fakejpegbytes"
NEC_CAMS = f"""<?xml version="1.0"?>
<status {NS}><cctvSnapshotData><net id="Maine" name="Maine">
<cctvSnapshot id="I-95 NB at MM 25 Kennebunk" netId="Maine" {NS}>
  <name>I-95 NB at MM 25 Kennebunk</name><status>Unknown</status>
  <fileType>JPG</fileType><size>14</size>
  <snippet>{base64.b64encode(JPEG).decode()}</snippet>
</cctvSnapshot>
<cctvSnapshot id="NO-LOCATION-CAM" netId="Maine" {NS}>
  <name>Mystery cam</name><size>14</size>
  <snippet>{base64.b64encode(JPEG).decode()}</snippet>
</cctvSnapshot></net></cctvSnapshotData></status>""".encode()


def test_nec_bundle_parses_all_kinds():
    states._cam_locs.clear()
    markers = states._parse_nec_bundle(NEC_BUNDLE, "me", "MaineDOT")
    kinds = sorted(m["kind"] for m in markers)
    assert kinds == ["incident", "lane_closure", "rwis", "sign"]

    inc = next(m for m in markers if m["kind"] == "incident")
    assert inc["lat"] == 44.8012 and inc["lon"] == -68.7778
    assert inc["type"] == "Crash" and inc["src"] == "MaineDOT"
    assert inc["reported"].startswith("2026-07-19T08:15:00")

    clo = next(m for m in markers if m["kind"] == "lane_closure")
    assert clo["cls"] == "lane"          # one blocked of two lanes
    assert clo["end"] == [43.93, -69.97]
    assert [43.925, -69.967] in clo["path"]   # midpoint made it into the path

    sign = next(m for m in markers if m["kind"] == "sign")
    assert sign["lines"] == ["CRASH AHEAD", "USE CAUTION", "EXPECT DELAYS"]
    assert "OLD" not in (sign["message"] or "")   # offline sign filtered

    wx = next(m for m in markers if m["kind"] == "rwis")
    assert wx["air_c"] == 15.8 and wx["pave_c"] == 16.0

    # Camera location captured for the snapshot join.
    assert states._cam_locs[("me", "I-95 NB at MM 25 Kennebunk")] == (43.391, -70.543)


def test_nec_cameras_join_on_location():
    states._cam_locs.clear()
    states._snapshots.clear()
    states._parse_nec_bundle(NEC_BUNDLE, "me", "MaineDOT")
    markers = states._parse_nec_cameras(NEC_CAMS, "me", "MaineDOT")
    # Only the camera with known coordinates is mapped.
    assert len(markers) == 1
    cam = markers[0]
    assert cam["lat"] == 43.391
    assert cam["image"].startswith("/api/stcam/me/")
    assert states.snapshot("me", "I-95 NB at MM 25 Kennebunk") == JPEG
    assert states.snapshot("me", "NO-LOCATION-CAM") is None


def _wz_feature(desc, start, end):
    return {
        "type": "Feature",
        "properties": {
            "core_details": {"event_type": "work-zone",
                             "road_names": ["I-80"],
                             "description": desc},
            "vehicle_impact": "some-lanes-closed",
            "start_date": start, "end_date": end,
        },
        "geometry": {"type": "LineString",
                     "coordinates": [[-93.6, 41.6], [-93.5, 41.61]]},
    }


def test_wzdx_parses_active_and_filters_planned():
    payload = {"features": [
        _wz_feature("Active now", "2020-01-01T00:00:00Z", "2030-01-01T00:00:00Z"),
        _wz_feature("Planned for later", "2029-01-01T00:00:00Z", "2030-01-01T00:00:00Z"),
        _wz_feature("Already done", "2020-01-01T00:00:00Z", "2020-06-01T00:00:00Z"),
    ]}
    markers = states._parse_ia_wzdx(payload, src="NCDOT")
    # Only work that is in place right now ships to the map.
    assert len(markers) == 1
    m = markers[0]
    assert m["label"] == "Active now"
    assert m["kind"] == "lane_closure" and m["cls"] == "lane"
    assert m["route"] == "I-80" and m["src"] == "NCDOT"
    assert m["path"][0] == [41.6, -93.6]


def test_md_chart_parses_events_signs_weather():
    class FakeResp:
        def __init__(self, data):
            self._d = data

        def json(self):
            return self._d

    class FakeClient:
        async def get(self, url, **kw):
            if "getEventMapDataJSON" in url:
                return FakeResp({"data": [
                    {"lat": "39.2", "lon": "-76.6", "closed": "False",
                     "incidentType": "Collision", "direction": "East",
                     "description": "US 50 at MD 70"},
                    {"lat": "39.3", "lon": "-76.7", "closed": "True",
                     "incidentType": "Stale", "description": "old"},
                ]})
            if "getDMSMapDataJSON" in url:
                return FakeResp({"data": [
                    {"lat": "38.9", "lon": "-76.2", "commMode": "ONLINE",
                     "description": "US 50 WEST",
                     "msgHTML": "<table><tr><td>CRASH AHEAD</td></tr>"
                                "<tr><td>USE CAUTION</td></tr></table>"},
                ]})
            return FakeResp({"data": [
                {"lat": "39.19", "lon": "-76.0", "description": "MD 20",
                 "airTemp": "73F", "surfaceTemp": "88F",
                 "windSpeed": "5 MPH", "gustSpeed": "9 MPH"},
            ]})

    import asyncio
    out = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        states._fetch_md(FakeClient()))
    kinds = sorted(m["kind"] for m in out["markers"])
    assert kinds == ["incident", "rwis", "sign"]   # closed event filtered
    sign = next(m for m in out["markers"] if m["kind"] == "sign")
    assert "CRASH AHEAD" in sign["lines"]
    wx = next(m for m in out["markers"] if m["kind"] == "rwis")
    assert wx["air_c"] == 22.8 and wx["gust"] == 9.0


async def test_wa_fetch_maps_alerts_cameras_passes(monkeypatch):
    import httpx
    import respx

    monkeypatch.setenv("WSDOT_API_KEY", "k")
    alerts = [{"AlertID": 1, "EventCategory": "Collision",
               "HeadlineDescription": "Two-car collision blocking right lane",
               "County": "King",
               "StartRoadwayLocation": {"Latitude": 47.6, "Longitude": -122.3,
                                        "RoadName": "I-5", "Direction": "N",
                                        "Description": "at Mercer St"}},
              {"AlertID": 2, "EventCategory": "Closure",
               "HeadlineDescription": "Full closure for repaving",
               "County": "Pierce",
               "StartRoadwayLocation": {"Latitude": 47.2, "Longitude": -122.4,
                                        "RoadName": "SR-16"},
               "EndRoadwayLocation": {"Latitude": 47.25, "Longitude": -122.5}}]
    cams = [{"CameraID": 9, "IsActive": True, "Title": "I-5 at Mercer",
             "ImageURL": "https://images.wsdot.wa.gov/nw/005vc.jpg",
             "DisplayLatitude": 47.61, "DisplayLongitude": -122.33,
             "CameraLocation": {"RoadName": "I-5", "Description": "Mercer"}}]
    passes = [{"MountainPassName": "Snoqualmie Pass",
               "Latitude": 47.42, "Longitude": -121.4,
               "RestrictionOne": {"RestrictionText": "Chains required"},
               "RestrictionTwo": {"RestrictionText": "No restrictions"}}]
    with respx.mock:
        respx.get(url__regex=r".*HighwayAlerts.*").mock(
            return_value=httpx.Response(200, json=alerts))
        respx.get(url__regex=r".*HighwayCameras.*").mock(
            return_value=httpx.Response(200, json=cams))
        respx.get(url__regex=r".*MountainPassConditions.*").mock(
            return_value=httpx.Response(200, json=passes))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_wa(client)
    kinds = sorted(m["kind"] for m in out["markers"])
    assert kinds == ["camera", "chain_control", "incident", "lane_closure"]
    clo = next(m for m in out["markers"] if m["kind"] == "lane_closure")
    assert clo["cls"] == "full-roadway"
    # No road geometry from WSDOT, so no stretch: a straight begin-to-end
    # line would cut through terrain (the "line in the forest" bug).
    assert "end" not in clo and "path" not in clo
    chain = next(m for m in out["markers"] if m["kind"] == "chain_control")
    assert "Chains required" in chain["label"]
    assert "No restrictions" not in chain["label"]


async def test_or_fetch_rewrites_http_camera_urls(monkeypatch):
    import httpx
    import respx

    monkeypatch.setenv("TRIPCHECK_API_KEY", "k")
    inc = {"incidents": [{"is-active": "true", "event-type-id": "RW",
                          "headline": "Nighttime closures of I-205",
                          "impact-desc": "Delay under 20 minutes",
                          "location": {"route-id": "I205",
                                       "location-name": "EAST PORTLAND FWY",
                                       "start-location": {"start-lat": 45.36,
                                                          "start-long": -122.61},
                                       "end-location": {"end-lat": 45.37,
                                                        "end-long": -122.60}}}]}
    cams = {"CCTVInventoryRequest": [{"device-id": "277",
                                      "latitude": "46.18", "longitude": "-123.85",
                                      "route-id": "US101",
                                      "cctv-other": "US101 at Astoria",
                                      "cctv-url": "http://www.TripCheck.com/roadcams/a.jpg"}]}
    with respx.mock:
        respx.get(url__regex=r".*tripcheck/Incidents").mock(
            return_value=httpx.Response(200, json=inc))
        respx.get(url__regex=r".*tripcheck/Cctv/Inventory").mock(
            return_value=httpx.Response(200, json=cams))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_or(client)
    cam = next(m for m in out["markers"] if m["kind"] == "camera")
    assert cam["image"].startswith("https://")   # mixed-content rewrite
    clo = next(m for m in out["markers"] if m["kind"] == "lane_closure")
    assert clo["route"] == "I205"
    assert "end" not in clo and "path" not in clo   # dot only, no fake line


async def test_wzdx_fetch_labels_source(monkeypatch):
    import httpx
    import respx

    payload = {"features": [
        _wz_feature("Live work", None, None)]}   # no dates = assumed active
    with respx.mock:
        respx.get(states.NC_WZDX_URL).mock(
            return_value=httpx.Response(200, json=payload))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_wzdx(client, states.NC_WZDX_URL, "NCDOT")
    assert out["markers"][0]["src"] == "NCDOT"


def test_bbox_gating():
    ca_box = (32.0, -125.0, 42.5, -113.5)
    me_bounds = states.NEC_STATES["me"][2]
    assert not states._overlaps(ca_box, me_bounds)
    maine_box = (43.0, -71.0, 46.0, -67.0)
    assert states._overlaps(maine_box, me_bounds)
    assert not states._overlaps(maine_box, states.IA_BOUNDS)
