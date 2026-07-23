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
                     # Real CHART feeds ship the markup entity-escaped.
                     "msgHTML": "&lt;table class='dmsMsg'&gt;&lt;tr&gt;"
                                "&lt;td&gt;CRASH AHEAD&lt;/td&gt;&lt;/tr&gt;"
                                "&lt;tr&gt;&lt;td&gt;USE&amp;nbsp;CAUTION"
                                "&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;"},
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
        respx.get(url__regex=r".*WeatherInformation.*").mock(
            return_value=httpx.Response(200, json=[
                {"StationName": "S 144th St", "Latitude": 47.47,
                 "Longitude": -122.27, "TemperatureInFahrenheit": 59.0,
                 "WindGustSpeedInMPH": 12}]))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_wa(client)
    kinds = sorted(m["kind"] for m in out["markers"])
    assert kinds == ["camera", "chain_control", "incident", "lane_closure",
                     "rwis"]
    wx = next(m for m in out["markers"] if m["kind"] == "rwis")
    assert wx["air_c"] == 15.0 and wx["gust"] == 12
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


def test_wzdx_cap_limits_markers():
    payload = {"features": [
        _wz_feature(f"Job {i}", "2020-01-01T00:00:00Z",
                    "2030-01-01T00:00:00Z")
        for i in range(5)]}
    markers = states._parse_ia_wzdx(payload, src="City of Austin", cap=2)
    assert len(markers) == 2


def test_dms_lines_drop_placeholder_junk():
    # Idle boards park "." or "-" as the message; those are not messages.
    assert states._dms_lines("[jl3].") == []
    assert states._dms_lines(".[nl]-") == []
    assert states._dms_lines("CRASH AHEAD[nl].") == ["CRASH AHEAD"]


async def test_mo_signs_split_br_tags_and_drop_junk():
    import httpx
    import respx

    dms = [{"x": "-94.5", "y": "39.1", "dev": "DMS-1",
            "msg": "I-35 4 MIN<br />4 MILES AHEAD"},
           {"x": "-94.6", "y": "39.2", "dev": "DMS-2", "msg": "."}]
    with respx.mock:
        respx.get(url__regex=r".*MsgBrdV1.*").mock(
            return_value=httpx.Response(200, json=dms))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_mo_dms(client)
    live = out["markers"][0]
    assert live["lines"] == ["I-35 4 MIN", "4 MILES AHEAD"]
    assert "<br" not in live["message"]
    assert out["markers"][1].get("blank") is True


async def test_us_fires_attach_perimeters_by_name():
    import httpx
    import respx

    incidents = {"features": [
        {"geometry": {"x": -120.5, "y": 46.5},
         "attributes": {"IncidentName": "Moxee Orchard",
                        "IncidentSize": 5918, "PercentContained": 40,
                        "FireDiscoveryDateTime": 1752000000000}},
        {"geometry": {"x": -105.0, "y": 35.0},
         "attributes": {"IncidentName": "No Shape",
                        "IncidentSize": 12, "PercentContained": 0,
                        "FireDiscoveryDateTime": 1752000000000}},
    ]}
    perims = {"features": [
        {"attributes": {"poly_IncidentName": "Moxee Orchard Fire"},
         "geometry": {"rings": [[[-120.51, 46.49], [-120.49, 46.49],
                                 [-120.49, 46.51], [-120.51, 46.51]]]}},
    ]}
    with respx.mock:
        respx.get(url__regex=r".*Incident_Locations.*").mock(
            return_value=httpx.Response(200, json=incidents))
        respx.get(url__regex=r".*Perimeters.*").mock(
            return_value=httpx.Response(200, json=perims))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_us_fires(client)
    fires = {m["name"]: m for m in out["markers"]}
    # "Moxee Orchard" joins "Moxee Orchard Fire" via name normalization;
    # poly is a MultiPolygon (list of rings).
    assert fires["Moxee Orchard"]["poly"][0][0] == [46.49, -120.51]
    # Fires without a perimeter record honestly stay dots.
    assert "poly" not in fires["No Shape"]


def test_fire_rings_keep_lobes_separate_and_drop_holes():
    # Two burn lobes plus a hole (reverse winding) inside the first.
    lobe1 = [[-120.5, 46.5], [-120.4, 46.5], [-120.4, 46.6],
             [-120.5, 46.6], [-120.5, 46.5]]
    lobe2 = [[-120.2, 46.5], [-120.15, 46.5], [-120.15, 46.55],
             [-120.2, 46.55], [-120.2, 46.5]]
    hole = list(reversed([[-120.48, 46.52], [-120.44, 46.52],
                          [-120.44, 46.56], [-120.48, 46.56],
                          [-120.48, 46.52]]))
    shaped = states.fire_rings([lobe1, hole, lobe2])
    # Two separate polygons, no thread connecting them, hole dropped.
    assert len(shaped) == 2
    assert all(len(r) >= 4 for r in shaped)
    ring_starts = {tuple(r[0]) for r in shaped}
    assert (46.5, -120.5) in ring_starts and (46.5, -120.2) in ring_starts


async def test_mi_fetch_closures_carry_real_geometry():
    import httpx
    import respx

    con = [{"latitude": 42.23, "longitude": -83.43, "id": "ETX-1",
            "title": "SB I-275: Total Closure",
            "coordinatePoints": [[-83.44, 42.24], [-83.43, 42.23]]}]
    inc = [{"latitude": 42.35, "longitude": -83.05, "id": 7,
            "title": "Crash",
            "message": "<b>Location:</b> I-75 <b>Event:</b> Crash"}]
    with respx.mock:
        respx.get(url__regex=r".*construction/AllForMap.*").mock(
            return_value=httpx.Response(200, json=con))
        respx.get(url__regex=r".*incidents/AllForMap.*").mock(
            return_value=httpx.Response(200, json=inc))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_mi(client)
    clo = next(m for m in out["markers"] if m["kind"] == "lane_closure")
    assert clo["cls"] == "full-roadway"
    assert clo["path"][0] == [42.24, -83.44] and clo["end"] == [42.23, -83.43]
    i = next(m for m in out["markers"] if m["kind"] == "incident")
    assert "<b>" not in i["label"] and "I-75" in i["label"]


async def test_de_tmc_signs_advisories_weather():
    import httpx
    import respx

    adv = {"advisories": [
        {"type": {"code": "C", "name": "Construction"},
         "where": {"lat": 39.7, "lon": -75.68,
                   "location": "DE-2 WB RIGHT LANE CLOSED"}},
        {"type": {"code": "I", "name": "Incident"},
         "where": {"lat": 39.1, "lon": -75.5, "location": "CRASH ON US 13"}},
    ]}
    vms = {"signTypes": [{"signs": [
        {"lat": 38.97, "lon": -75.43, "enable": True,
         "title": "DE 1 @ THOMPSONVILLE",
         "message": "MOVE OVER<br/>OR<br/>SLOW DOWN<br/>---------<br/>FOR"},
    ]}]}
    wx = {"stations": [{"lat": 38.92, "lon": -75.56, "title": "US 13 @ DE 14"}]}
    with respx.mock:
        respx.get(url__regex=r".*advisory\.json.*").mock(
            return_value=httpx.Response(200, json=adv))
        respx.get(url__regex=r".*vmsg-vms\.json.*").mock(
            return_value=httpx.Response(200, json=vms))
        respx.get(url__regex=r".*weatherstation\.json.*").mock(
            return_value=httpx.Response(200, json=wx))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_de_tmc(client)
    kinds = sorted(m["kind"] for m in out["markers"])
    assert kinds == ["incident", "lane_closure", "rwis", "sign"]
    sign = next(m for m in out["markers"] if m["kind"] == "sign")
    # br tags split into lines; the dash separator row is not a line.
    assert sign["lines"] == ["MOVE OVER", "OR", "SLOW DOWN", "FOR"]


async def test_tn_events_filter_dates_and_classify():
    import time as _t

    import httpx
    import respx

    now = _t.time() * 1000
    feats = {"features": [
        {"geometry": {"x": -86.7, "y": 36.1},
         "attributes": {"CD_EVENT_TYPE": "work-zone",
                        "CD_ROAD_NAMES": "I-40", "CD_DIRECTION": "westbound",
                        "VEHICLE_IMPACT": "all-lanes-closed",
                        "START_DATE": now - 1000, "END_DATE": now + 100000}},
        {"geometry": {"x": -86.5, "y": 36.0},
         "attributes": {"CD_EVENT_TYPE": "obstruction",
                        "START_DATE": now - 1000, "END_DATE": now + 100000}},
        {"geometry": {"x": -86.4, "y": 35.9},
         "attributes": {"CD_EVENT_TYPE": "work-zone",
                        "START_DATE": now - 5000, "END_DATE": now - 1000}},
    ]}
    with respx.mock:
        respx.get(url__regex=r".*Smartway_Events.*").mock(
            return_value=httpx.Response(200, json=feats))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_tn(client)
    assert len(out["markers"]) == 2   # the lapsed one is dropped
    clo = next(m for m in out["markers"] if m["kind"] == "lane_closure")
    assert clo["cls"] == "full-roadway" and clo["route"] == "I-40"
    haz = next(m for m in out["markers"] if m["kind"] == "incident")
    assert haz["type"].startswith("Hazard")


async def test_ms_alerts_split_construction_and_incidents():
    import httpx
    import respx

    d = {"d": [
        {"lat": 34.9, "lon": -88.5, "tooltip": "US 72 between A and B",
         "icontype": "construction", "markergroup": "map-construction"},
        {"lat": 32.3, "lon": -90.2, "tooltip": "Crash on I-20",
         "icontype": "accident", "markergroup": "map-incident"},
    ]}
    with respx.mock:
        respx.post(url__regex=r".*LoadAlertData.*").mock(
            return_value=httpx.Response(200, json=d))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_ms(client)
    kinds = sorted(m["kind"] for m in out["markers"])
    assert kinds == ["incident", "lane_closure"]


async def test_ut_travel_iq_full_coverage(monkeypatch):
    import httpx
    import respx

    monkeypatch.setenv("UT511_API_KEY", "k")
    events = [{"ID": "1", "EventType": "accidentsAndIncidents",
               "EventSubType": "crash", "RoadwayName": "I-15",
               "Description": "Crash near 600 N", "LanesAffected": "1 Lane",
               "Latitude": "40.78", "Longitude": "-111.9"},
              {"ID": "2", "EventType": "roadwork", "RoadwayName": "SR-30",
               "Description": "Resurfacing",
               "LanesAffected": "All Lanes Closed",
               "Latitude": "41.75", "Longitude": "-111.98"}]
    cams = [{"Id": "9", "Location": "I-15 @ 600 N", "Roadway": "I-15",
             "Direction": "North", "Latitude": "40.78",
             "Longitude": "-111.91",
             "Views": [{"Id": 9, "Url":
                        "https://www.udottraffic.utah.gov/map/Cctv/9"}]}]
    signs = [{"Id": "s1", "Name": "I-80 EB @ Parleys",
              "Roadway": "I-80", "DirectionOfTravel": "Eastbound",
              "Messages": ["TIME TO\nDAN SUMMIT\t17min"],
              "Latitude": "40.7", "Longitude": "-111.8"},
             {"Id": "s2", "Name": "Idle board", "Roadway": "I-15",
              "Messages": ["NO_MESSAGE"],
              "Latitude": "40.6", "Longitude": "-111.9"}]
    wx = [{"Id": "w1", "StationName": "I-15 @ 6200 S",
           "AirTemperature": "99.2", "WindSpeedAvg": "9.28",
           "SurfaceStatus": "Dry", "Latitude": "40.63",
           "Longitude": "-111.9"}]
    with respx.mock:
        respx.get(url__regex=r".*get/event.*").mock(
            return_value=httpx.Response(200, json=events))
        respx.get(url__regex=r".*get/cameras.*").mock(
            return_value=httpx.Response(200, json=cams))
        respx.get(url__regex=r".*get/messagesigns.*").mock(
            return_value=httpx.Response(200, json=signs))
        respx.get(url__regex=r".*get/weatherstations.*").mock(
            return_value=httpx.Response(200, json=wx))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_ut(client)
    kinds = sorted(m["kind"] for m in out["markers"])
    assert kinds == ["camera", "incident", "lane_closure", "rwis",
                     "sign", "sign"]
    clo = next(m for m in out["markers"] if m["kind"] == "lane_closure")
    assert clo["cls"] == "full-roadway"
    live = next(m for m in out["markers"]
                if m["kind"] == "sign" and not m.get("blank"))
    # \n splits lines; the tab column flattens to a space.
    assert live["lines"] == ["TIME TO", "DAN SUMMIT 17min"]
    idle = next(m for m in out["markers"]
                if m["kind"] == "sign" and m.get("blank"))
    assert idle["message"] == ""
    wxm = next(m for m in out["markers"] if m["kind"] == "rwis")
    assert wxm["air_c"] == 37.3 and wxm["surface"] == "Dry"
    # The keyed feed supersedes the WZDx-only Utah feed.
    assert states._wzdx_superseded("ut") is True
    monkeypatch.delenv("UT511_API_KEY")
    assert states._wzdx_superseded("ut") is False


def test_source_status_covers_every_keyed_registry_entry(monkeypatch):
    # Prod-only crash regression: adding a KEYED_STATES entry without
    # its status label raised KeyError in coverage_summary, 500ing
    # /api/stats, but only when the key env var was actually set.
    for var in ("WSDOT_API_KEY", "TRIPCHECK_API_KEY", "OHGO_API_KEY",
                "UT511_API_KEY"):
        monkeypatch.setenv(var, "k")
    entries = states.source_status()
    named = {e["state"] for e in entries}
    for _code, (name, _b, _f, _r) in states.KEYED_STATES.items():
        assert name in named
    cov = states.coverage_summary()
    assert cov["states"] >= 30 and cov["sources"] >= 35


async def test_traveliq_registry_builds_keyed_states(monkeypatch):
    # One table drives all Travel-IQ states: entries exist, ready
    # checks read the right env vars, supersede maps hold.
    for code, (_st, _b, _host, env, _src) in states.TRAVELIQ.items():
        assert code in states.KEYED_STATES
        monkeypatch.delenv(env, raising=False)
        assert not states.KEYED_STATES[code][3]()
        monkeypatch.setenv(env, "k")
        assert states.KEYED_STATES[code][3]()
    assert states._wzdx_superseded("az") is True
    monkeypatch.delenv("AZ511_API_KEY")
    assert states._wzdx_superseded("az") is False


async def test_co_adapter_parses_all_kinds(monkeypatch):
    import httpx
    import respx

    monkeypatch.setenv("COTRIP_API_KEY", "k")
    inc = {"features": [{
        "geometry": {"type": "MultiPoint",
                     "coordinates": [[-104.6, 40.4]]},
        "properties": {"type": "Crash",
                       "travelerInformationMessage": "Crash on US-34"}}]}
    planned = {"features": [
        {"geometry": {"type": "MultiPoint",
                      "coordinates": [[-104.7, 38.3]]},
         "properties": {"startTime": "2020-01-01T00:00:00Z",
                        "clearTime": "2030-01-01T00:00:00Z",
                        "travelerInformationMessage": "All lanes closed",
                        "routeName": "CO-45N",
                        "laneImpacts": [{"direction": "north",
                                         "laneCount": 2,
                                         "laneClosures": "2",
                                         "closedLaneTypes": ["left lane",
                                                             "right lane"]}]}},
        {"geometry": {"type": "MultiPoint",
                      "coordinates": [[-105.0, 39.0]]},
         "properties": {"startTime": "2029-01-01T00:00:00Z",
                        "clearTime": "2030-01-01T00:00:00Z",
                        "travelerInformationMessage": "Future work"}}]}
    signs = {"features": [{
        "geometry": {"type": "Point", "coordinates": [-104.98, 39.87]},
        "properties": {"displayStatus": "on", "routeName": "I-25S",
                       "publicName": "I-25 at Thornton Pkwy",
                       "messageMarkup":
                       "[jp3][fo13]TOLL[nl3][fo13]LANE[nl3]CLOSED"}}]}
    wx = {"features": [{
        "geometry": {"type": "Point", "coordinates": [-106.9, 39.2]},
        "properties": {"publicName": "CO-82 at Snowmass",
                       "sensors": [{"type": "road surface status",
                                    "currentReading": "Dry"}]}}]}
    with respx.mock:
        respx.get(url__regex=r".*api/v1/incidents.*").mock(
            return_value=httpx.Response(200, json=inc))
        respx.get(url__regex=r".*api/v1/plannedEvents.*").mock(
            return_value=httpx.Response(200, json=planned))
        respx.get(url__regex=r".*api/v1/signs.*").mock(
            return_value=httpx.Response(200, json=signs))
        respx.get(url__regex=r".*api/v1/weatherStations.*").mock(
            return_value=httpx.Response(200, json=wx))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_co(client)
    kinds = sorted(m["kind"] for m in out["markers"])
    assert kinds == ["incident", "lane_closure", "rwis", "sign"]
    clo = next(m for m in out["markers"] if m["kind"] == "lane_closure")
    # Future-scheduled work filtered; both-lanes closure reads full.
    assert clo["cls"] == "full-roadway" and "All lanes" in clo["label"]
    sign = next(m for m in out["markers"] if m["kind"] == "sign")
    assert sign["lines"] == ["TOLL", "LANE", "CLOSED"]
    wxm = next(m for m in out["markers"] if m["kind"] == "rwis")
    assert wxm["surface"] == "Dry"


async def test_fl_divas_parses_events_cameras_signs():
    import httpx
    import respx

    ev = {"features": [
        {"geometry": {"x": -87.33, "y": 30.53},
         "attributes": {"status": "unresolved",
                        "eventtypesae": "Planned construction",
                        "descriptionen": "Roadwork on I-10 West",
                        "affectedlanes": "Right shoulder blocked",
                        "highway": "I-10"}},
        {"geometry": {"x": -80.2, "y": 26.1},
         "attributes": {"status": "unresolved", "eventtypesae": "Crash",
                        "descriptionen": "Crash on I-95 North",
                        "highway": "I-95"}},
        {"geometry": {"x": -81.0, "y": 27.0},
         "attributes": {"status": "resolved", "eventtypesae": "Crash",
                        "descriptionen": "Old crash"}},
    ]}
    cams = {"features": [
        {"geometry": {"x": -80.17, "y": 26.01},
         "attributes": {"description": "Hollywood Blvd at Park Road",
                        "highway": "Hollywood Blvd", "direction": "E",
                        "blockedimage": "False",
                        "imagefilename":
                        "https://images-dis.divas.cloud/DGI/c.jpg"}},
        {"geometry": {"x": -80.3, "y": 26.2},
         "attributes": {"description": "Blocked cam",
                        "blockedimage": "True",
                        "imagefilename":
                        "https://images-dis.divas.cloud/DGI/x.jpg"}},
    ]}
    dms = {"features": [
        {"geometry": {"x": -82.43, "y": 27.96},
         "attributes": {"description": "I-4 EB E of I-275",
                        "highway": "I-4", "direction": "e",
                        "message": "LEFT LANE BLOCKED\n9 MI AHEAD"}},
        {"geometry": {"x": -82.5, "y": 28.0},
         "attributes": {"description": "Idle board", "message": " "}},
    ]}
    with respx.mock:
        respx.get(url__regex=r".*DIVAS_GetEvent.*").mock(
            return_value=httpx.Response(200, json=ev))
        respx.get(url__regex=r".*DIVAS_Cameras.*").mock(
            return_value=httpx.Response(200, json=cams))
        respx.get(url__regex=r".*DIVAS_MessageBoard.*").mock(
            return_value=httpx.Response(200, json=dms))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_fl(client)
    kinds = sorted(m["kind"] for m in out["markers"])
    # Resolved events and blocked cameras are dropped.
    assert kinds == ["camera", "incident", "lane_closure", "sign", "sign"]
    live = next(m for m in out["markers"]
                if m["kind"] == "sign" and not m.get("blank"))
    assert live["lines"] == ["LEFT LANE BLOCKED", "9 MI AHEAD"]
    cam = next(m for m in out["markers"] if m["kind"] == "camera")
    assert cam["image"].endswith("c.jpg")


async def test_va_smarterroads_login_tokens_and_parsing(monkeypatch):
    import httpx
    import respx

    monkeypatch.setenv("SMARTERROADS_USER", "u")
    monkeypatch.setenv("SMARTERROADS_PASS", "p")
    states._sr_tokens.clear()
    inc = [{"orci:type_event": "Vehicle Accident",
            "orci:route_name": "I-95N",
            "orci:public_free_text": "Crash near exit 84",
            "orci:the_geom": {"gml:Point": {"gml:pos": "37.63 -77.35"}}},
           {"orci:type_event": "Closed", "orci:route_name": "Rt. 642N",
            "orci:template_511_text": "Road closed at Pole Green Rd",
            "orci:the_geom": {"gml:Point": {"gml:pos": "37.66 -77.30"}}}]
    wz = {"road_event_feed_info": {}, "type": "FeatureCollection",
          "features": [_wz_feature("I-64 work zone",
                                   "2020-01-01T00:00:00Z",
                                   "2030-01-01T00:00:00Z")]}
    # Unescaped ampersand on purpose: the live feed ships them.
    dms = ("<?xml version='1.0'?><wfs:FC xmlns:wfs='w' xmlns:orci='o'"
           " xmlns:gml='g'><gml:featureMembers>"
           "<orci:geoserver_dms_active>"
           "<orci:device_status>on</orci:device_status>"
           "<orci:current_message>[jl3]EXIT 126[nl][jl3]40 MILES & 34 MIN"
           "</orci:current_message>"
           "<orci:route_name>I-95N</orci:route_name>"
           "<orci:travel_direction>NORTH</orci:travel_direction>"
           "<orci:device_id>Sign-1</orci:device_id>"
           "<orci:the_geom><gml:Point><gml:pos>37.67 -77.44</gml:pos>"
           "</gml:Point></orci:the_geom>"
           "</orci:geoserver_dms_active></gml:featureMembers></wfs:FC>")
    wx = ("<?xml version='1.0'?><wfs:FC xmlns:wfs='w' xmlns:orci='o'"
          " xmlns:gml='g'><gml:featureMembers><orci:geoserver_ess>"
          "<orci:device_name>NRO-ESS-1</orci:device_name>"
          "<orci:air_temperature>22.1</orci:air_temperature>"
          "<orci:max_wind_gust_speed>5.0</orci:max_wind_gust_speed>"
          "<orci:the_geom><gml:Point><gml:pos>38.8 -77.1</gml:pos>"
          "</gml:Point></orci:the_geom>"
          "</orci:geoserver_ess></gml:featureMembers></wfs:FC>")
    with respx.mock:
        respx.get(url__regex=r".*services/auth/token").mock(
            return_value=httpx.Response(
                200, headers={"set-cookie": "XSRF-TOKEN=x"}))
        respx.post(url__regex=r".*services/auth/login").mock(
            return_value=httpx.Response(200, json={"user": {}}))
        respx.get(url__regex=r".*services/users/token/\d+").mock(
            return_value=httpx.Response(200, json={"data": "tok"}))
        respx.get(url__regex=r".*incidentFiltered_wfs\.json.*").mock(
            return_value=httpx.Response(200, json=inc))
        respx.get(url__regex=r".*workZone\.json.*").mock(
            return_value=httpx.Response(200, json=wz))
        respx.get(url__regex=r".*dms_active_wfs\.xml.*").mock(
            return_value=httpx.Response(200, content=dms.encode()))
        respx.get(url__regex=r".*rwis_wfs\.xml.*").mock(
            return_value=httpx.Response(200, content=wx.encode()))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_va(client)
    kinds = sorted(m["kind"] for m in out["markers"])
    assert kinds == ["incident", "lane_closure", "lane_closure",
                     "rwis", "sign"]
    closed = next(m for m in out["markers"]
                  if m["kind"] == "lane_closure" and m.get("cls"))
    assert closed["cls"] in ("full-roadway", "lane")
    sign = next(m for m in out["markers"] if m["kind"] == "sign")
    # Bare ampersand sanitized, DMS codes stripped into lines.
    assert sign["lines"] == ["EXIT 126", "40 MILES & 34 MIN"]
    wxm = next(m for m in out["markers"] if m["kind"] == "rwis")
    assert wxm["air_c"] == 22.1
    states._sr_tokens.clear()


async def test_wsdot_tolls_cents_and_sentinel(monkeypatch):
    import httpx
    import respx

    monkeypatch.setenv("WSDOT_API_KEY", "k")
    rates = [{"StateRoute": "405", "TravelDirection": "S",
              "StartLocationName": "NE 6th", "EndLocationName": "SR 527",
              "StartLatitude": 47.61, "StartLongitude": -122.18,
              "CurrentToll": 275, "CurrentMessage": "",
              "TimeUpdated": "/Date(1784800000000-0700)/"},
             {"StateRoute": "167", "TravelDirection": "N",
              "StartLocationName": "X", "EndLocationName": "Y",
              "StartLatitude": 47.3, "StartLongitude": -122.2,
              "CurrentToll": 0,
              "TimeUpdated": "/Date(-62135568000000-0800)/"}]
    with respx.mock:
        respx.get(url__regex=r".*GetTollRatesAsJson.*").mock(
            return_value=httpx.Response(200, json=rates))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_wsdot_tolls(client)
    live = out["markers"][0]
    # Cents to dollars; the uninitialized-date sentinel maps to None.
    assert live["price"] == 2.75 and live["pricing"] == "live"
    assert live["updated"] is not None
    assert out["markers"][1]["price"] is None
    assert out["markers"][1]["updated"] is None


async def test_bay_tolls_destinations(monkeypatch):
    import httpx
    import respx

    monkeypatch.setenv("BAY511_API_KEY", "k")
    body = {"toll-programs": [{
        "toll-authority-info": {"toll-program-name": "I-680 SB"},
        "toll-signs": [{
            "name": "Alcosta - 4",
            "geography": {"type": "Point",
                          "coordinates": [-121.96, 37.75]},
            "toll-destinations": [
                {"name": "Alcosta - 5",
                 "toll-rates": [{"toll-price": 4.25,
                                 "last-updated": "2026-07-22T10:57:31"}]},
                {"name": "SR-84",
                 "toll-rates": [{"toll-price": 7.5,
                                 "last-updated": "2026-07-22T10:57:31"}]},
            ]}]}]}
    import json as _json
    content = ("﻿" + _json.dumps(body)).encode("utf-8")
    with respx.mock:
        respx.get(url__regex=r".*toll/programs.*").mock(
            return_value=httpx.Response(200, content=content))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_bay_tolls(client)
    m = out["markers"][0]
    assert m["price"] == 4.25 and m["src"] == "511.org"
    assert m["lines"] == ["to Alcosta - 5: $4.25", "to SR-84: $7.50"]


async def test_ntta_join_and_python_side_filter():
    import httpx
    import respx

    g = {"features": [{"geometry": {"x": -96.9, "y": 33.0},
                       "attributes": {
                           "DBO.TCAL_RDWY_Gantry.Gantry": "KELBD",
                           "DBO.TCAL_RDWY_Gantry.NAME": "Kelly Blvd",
                           "DBO.TCAL_RDWY_Gantry.ROADWAY_DESC":
                               "PRESIDENT GEORGE BUSH TURNPIKE"}}]}
    r = {"features": [
        {"attributes": {"PlazaCode": "KELBD", "VehicleClass": "2",
                        "ScheduleType": "STANDARD", "TagFare": "0.81",
                        "StartEffectiveDate": 0,
                        "EndEffectiveDate": 253402214400000}},
        {"attributes": {"PlazaCode": "KELBD", "VehicleClass": "4",
                        "ScheduleType": "STANDARD", "TagFare": "3.24",
                        "StartEffectiveDate": 0,
                        "EndEffectiveDate": 253402214400000}}]}
    with respx.mock:
        respx.get(url__regex=r".*MapServer/0/query.*").mock(
            return_value=httpx.Response(200, json=g))
        respx.get(url__regex=r".*MapServer/1/query.*").mock(
            return_value=httpx.Response(200, json=r))
        async with httpx.AsyncClient() as client:
            out = await states._fetch_ntta_tolls(client)
    m = out["markers"][0]
    # Two-axle rate joined by plaza code; class-4 row ignored.
    assert m["price"] == 0.81 and m["pricing"] == "fixed"


def test_gpoly_decoder_reference_vector():
    # Google's documented example polyline.
    pts = states._decode_gpoly("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert pts == [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]]
    assert states._decode_gpoly("") == []
    assert states._decode_gpoly("garbage{{{") in ([], states._decode_gpoly("garbage{{{"))


def test_road_path_sanity_guard():
    pts = [[38.5, -120.2], [38.6, -120.3]]
    # Path near the marker passes; far-away garbage is refused.
    assert states._road_path(pts, 38.5, -120.2) is not None
    assert states._road_path(pts, 45.0, -90.0) is None
    assert states._road_path([[38.5, -120.2]], 38.5, -120.2) is None
