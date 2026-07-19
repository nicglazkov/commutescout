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


def test_iowa_wzdx_parses_closures():
    payload = {
        "features": [{
            "id": "OpenTMS-1", "type": "Feature",
            "properties": {
                "core_details": {
                    "event_type": "work-zone",
                    "road_names": ["I-80"], "direction": "eastbound",
                    "description": "Lane closed for bridge work",
                },
                "vehicle_impact": "some-lanes-closed",
                "start_date": "2026-07-18T12:00:00Z",
                "end_date": "2026-07-20T12:00:00Z",
                "types_of_work": [{"type_name": "roadway-relocation"}],
            },
            "geometry": {"type": "LineString",
                         "coordinates": [[-93.6, 41.6], [-93.5, 41.61]]},
        }],
    }
    markers = states._parse_ia_wzdx(payload)
    assert len(markers) == 1
    m = markers[0]
    assert m["kind"] == "lane_closure" and m["cls"] == "lane"
    assert m["route"] == "I-80" and m["src"] == "Iowa DOT"
    assert m["since"] and m["until"] and m["until"] > m["since"]
    assert m["path"][0] == [41.6, -93.6]


def test_bbox_gating():
    ca_box = (32.0, -125.0, 42.5, -113.5)
    me_bounds = states.NEC_STATES["me"][2]
    assert not states._overlaps(ca_box, me_bounds)
    maine_box = (43.0, -71.0, 46.0, -67.0)
    assert states._overlaps(maine_box, me_bounds)
    assert not states._overlaps(maine_box, states.IA_BOUNDS)
