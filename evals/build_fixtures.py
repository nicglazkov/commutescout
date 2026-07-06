"""Build the three synthetic eval scenarios.

Usage: python evals/build_fixtures.py

The storm scenario has to be synthetic until winter (the brief is written in
July); the other two are synthesized as well so every golden answer is
derivable from a controlled, stable fixture. Formats copy the real feeds
byte-for-byte in structure (captured 2026-07-05); evals/record.py exists to
bank real scenario recordings when interesting days happen.

Closure end epochs are far in the future so "in place now" stays true no
matter when the evals run.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

FAR_FUTURE_EPOCH = 1_900_000_000  # 2030: keeps synthetic closures active
PAST_EPOCH = 1_783_000_000


def latlon_chp(lat: float, lon: float) -> str:
    return f"{int(round(lat * 1e6))}:{int(round(abs(lon) * 1e6))}"


def chp_log(id_, logtime, logtype, location, area, lat, lon):
    return f"""
\t\t<Log ID = "{id_}">
\t\t\t<LogTime>"{logtime}"</LogTime>
\t\t\t<LogType>"{logtype}"</LogType>
\t\t\t<Location>"{location}"</Location>
\t\t\t<LocationDesc>""</LocationDesc>
\t\t\t<Area>"{area}"</Area>
\t\t\t<ThomasBrothers>""</ThomasBrothers>
\t\t\t<LATLON>"{latlon_chp(lat, lon)}"</LATLON>
\t\t\t<LogDetails></LogDetails></Log>
"""


def chp_doc(logs: list[str]) -> str:
    body = "".join(logs)
    return (
        '<?xml version="1.0" ?>\n<State><Center ID = "SAHB">\n'
        f'<Dispatch ID = "SACC">\n{body}</Dispatch>\n</Center>\n</State>\n'
    )


def lcs_record(
    index, district, route, county, direction, loc, place, lat, lon,
    end_lat, end_lon, closure_type, work, lanes, is_1097,
    indefinite=False, end_epoch=FAR_FUTURE_EPOCH, facility="Mainline",
    total_lanes=2, delay="Not Reported",
):
    return f"""
\t<lcs>
\t\t<index>{index}</index>
\t\t<location>
\t\t\t<travelFlowDirection>{direction}</travelFlowDirection>
\t\t\t<begin>
\t\t\t\t<beginDistrict>{district}</beginDistrict>
\t\t\t\t<beginLocationName>{loc}</beginLocationName>
\t\t\t\t<beginNearbyPlace>{place}</beginNearbyPlace>
\t\t\t\t<beginLongitude>{lon}</beginLongitude>
\t\t\t\t<beginLatitude>{lat}</beginLatitude>
\t\t\t\t<beginCounty>{county}</beginCounty>
\t\t\t\t<beginRoute>{route}</beginRoute>
\t\t\t\t<beginMilepost>10.0</beginMilepost>
\t\t\t</begin>
\t\t\t<end>
\t\t\t\t<endLongitude>{end_lon}</endLongitude>
\t\t\t\t<endLatitude>{end_lat}</endLatitude>
\t\t\t\t<endRoute>{route}</endRoute>
\t\t\t\t<endMilepost>14.0</endMilepost>
\t\t\t</end>
\t\t</location>
\t\t<closure>
\t\t\t<closureID>{index.split("-")[0]}</closureID>
\t\t\t<closureTimestamp>
\t\t\t\t<closureStartEpoch>{PAST_EPOCH}</closureStartEpoch>
\t\t\t\t<closureEndEpoch>{end_epoch}</closureEndEpoch>
\t\t\t\t<isClosureEndIndefinite>{str(indefinite).lower()}</isClosureEndIndefinite>
\t\t\t</closureTimestamp>
\t\t\t<facility>{facility}</facility>
\t\t\t<typeOfClosure>{closure_type}</typeOfClosure>
\t\t\t<typeOfWork>{work}</typeOfWork>
\t\t\t<durationOfClosure>Standard</durationOfClosure>
\t\t\t<estimatedDelay>{delay}</estimatedDelay>
\t\t\t<lanesClosed>{lanes}</lanesClosed>
\t\t\t<totalExistingLanes>{total_lanes}</totalExistingLanes>
\t\t\t<code1097>
\t\t\t\t<isCode1097>{str(is_1097).lower()}</isCode1097>
\t\t\t\t<code1097Timestamp>
\t\t\t\t\t<code1097Epoch>{PAST_EPOCH if is_1097 else ""}</code1097Epoch>
\t\t\t\t</code1097Timestamp>
\t\t\t</code1097>
\t\t\t<code1098>
\t\t\t\t<isCode1098>false</isCode1098>
\t\t\t</code1098>
\t\t\t<code1022>
\t\t\t\t<isCode1022>false</isCode1022>
\t\t\t</code1022>
\t\t</closure>
\t</lcs>
"""


def cc_record(index, district, route, county, direction, loc, place, lat, lon,
              status, description):
    return f"""
\t<cc>
\t\t<index>{index}</index>
\t\t<location>
\t\t\t<district>{district}</district>
\t\t\t<locationName>{loc}</locationName>
\t\t\t<nearbyPlace>{place}</nearbyPlace>
\t\t\t<longitude>{lon}</longitude>
\t\t\t<latitude>{lat}</latitude>
\t\t\t<direction>{direction}</direction>
\t\t\t<county>{county}</county>
\t\t\t<route>{route}</route>
\t\t</location>
\t\t<inService>true</inService>
\t\t<statusData>
\t\t\t<statusTimestamp>
\t\t\t\t<statusDate>2026-07-05</statusDate>
\t\t\t\t<statusTime>06:15:00</statusTime>
\t\t\t</statusTimestamp>
\t\t\t<status>{status}</status>
\t\t\t<statusDescription>{description}</statusDescription>
\t\t</statusData>
\t</cc>
"""


def cwwp_doc(records: list[str]) -> str:
    return (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n<data>'
        + "".join(records)
        + "\n</data>\n"
    )


def wfigs_doc(fires: list[dict]) -> str:
    features = [
        {
            "attributes": {
                "IncidentName": f["name"],
                "IncidentSize": f["acres"],
                "PercentContained": f["contained"],
                "FireDiscoveryDateTime": 1783000000000,
                "UniqueFireIdentifier": f["id"],
                "IncidentTypeCategory": "WF",
            },
            "geometry": {"x": f["lon"], "y": f["lat"]},
        }
        for f in fires
    ]
    return json.dumps({"objectIdFieldName": "OBJECTID", "features": features}, indent=1)


def cc_from_point(point, district, status, description):
    index, route, county, direction, loc, place, lat, lon = point
    return cc_record(index, district, route, county, direction, loc, place,
                     lat, lon, status, description)


R0_DESC = "No chain controls are in effect at this time."
R1_DESC = "Chains or snow tires with M+S rating required."
R2_DESC = (
    "Chains are required on all vehicles except four wheel drive vehicles "
    "with snow tires on all four wheels."
)

# Chain checkpoints reused across scenarios (status varies).
CC_POINTS_D3 = [
    # (index, route, county, direction, location, place, lat, lon)
    ("3-ED-50-25.4-E-110", "US-50", "El Dorado", "East", "Pollock Pines", "Pollock Pines", 38.761, -120.586),
    ("3-ED-50-33.2-E-101", "US-50", "El Dorado", "East", "Twin Bridges", "Twin Bridges", 38.809, -120.117),
    ("3-ED-50-45.0-W-102", "US-50", "El Dorado", "West", "Meyers", "Meyers", 38.857, -119.983),
    ("3-PLA-80-30.5-E-120", "I-80", "Placer", "East", "Baxter", "Alta", 39.200, -120.780),
    ("3-NEV-80-40.2-E-121", "I-80", "Nevada", "East", "Kingvale", "Kingvale", 39.316, -120.443),
    ("3-NEV-80-48.0-W-122", "I-80", "Nevada", "West", "Donner Lake Interchange", "Truckee", 39.324, -120.270),
    ("3-PLA-89-5.0-S-130", "SR-89", "Placer", "South", "Tahoe City Wye", "Tahoe City", 39.170, -120.145),
]
CC_POINTS_D10 = [
    ("10-ALP-88-5.0-E-201", "SR-88", "Alpine", "East", "Carson Pass", "Kirkwood", 38.694, -119.989),
    ("10-AMA-88-40.0-E-202", "SR-88", "Amador", "East", "Kirkwood Meadows", "Kirkwood", 38.700, -120.070),
]


def build_quiet_day(out: Path) -> None:
    chp = chp_doc([
        chp_log("260705QD0001", "Jul  5 2026  9:10AM", "1125-Traffic Hazard",
                "US101 S / Cesar Chavez St", "SF Bay", 37.750, -122.404),
        chp_log("260705QD0002", "Jul  5 2026  9:40AM", "1182-Trfc Collision-No Inj",
                "I80 W / University Ave", "Golden Gate", 37.870, -122.300),
        chp_log("260705QD0003", "Jul  5 2026 10:05AM", "1125-Traffic Hazard",
                "Jackson Rd / Mayhew Rd", "East Sac", 38.531, -121.344),
        chp_log("260705QD0004", "Jul  5 2026 10:20AM", "1183-Trfc Collision-Unkn Inj",
                "SR99 N / Ming Ave", "Bakersfield", 35.340, -119.020),
    ])
    (out / "chp.xml").write_text(chp)

    (out / "lcs_d04.xml").write_text(cwwp_doc([
        lcs_record("Q1AB-0001-quiet", 4, "US-101", "Santa Clara", "South",
                   "Trimble Rd", "San Jose", 37.387, -121.925, 37.370, -121.918,
                   "Lane", "Pavement Repair", "1, RShoulder", is_1097=True,
                   total_lanes=4, delay="5"),
        # Full closure of an ON-RAMP: must never be reported as a closed
        # highway.
        lcs_record("Q4GH-0004-quiet", 4, "US-101", "Santa Clara", "North",
                   "Story Rd", "San Jose", 37.330, -121.855, 37.332, -121.853,
                   "Full", "Bridge Work", "All", is_1097=True,
                   facility="On Ramp", total_lanes=1),
        # One-way traffic control on a two-lane mountain road: passable.
        lcs_record("Q5IJ-0005-quiet", 4, "SR-84", "San Mateo", "West",
                   "La Honda", "La Honda", 37.319, -122.274, 37.315, -122.290,
                   "One-Way Traffic", "Tree Work", "1", is_1097=True,
                   facility="Conventional Hwy", total_lanes=2, delay="10"),
    ]))
    (out / "lcs_d03.xml").write_text(cwwp_doc([
        # Shoulder-only: must not be reported.
        lcs_record("Q2CD-0002-quiet", 3, "I-80", "Yolo", "East",
                   "Chiles Rd", "Davis", 38.545, -121.700, 38.550, -121.690,
                   "Lane", "Litter Removal", "RShoulder", is_1097=True),
        # Scheduled but not established: must not be reported.
        lcs_record("Q3EF-0003-quiet", 3, "US-50", "Sacramento", "East",
                   "Watt Ave", "Sacramento", 38.560, -121.380, 38.562, -121.360,
                   "Lane", "Electrical Work", "2", is_1097=False),
    ]))
    (out / "cc_d03.xml").write_text(cwwp_doc([
        cc_from_point(p, 3, "R-0", R0_DESC) for p in CC_POINTS_D3
    ]))
    (out / "cc_d10.xml").write_text(cwwp_doc([
        cc_from_point(p, 10, "R-0", R0_DESC) for p in CC_POINTS_D10
    ]))
    (out / "wfigs.json").write_text(wfigs_doc([
        {"name": "LOST", "id": "2026-CAKRN-025007", "acres": 7834,
         "contained": 100, "lat": 36.50, "lon": -118.90},
    ]))


def build_storm_day(out: Path) -> None:
    chp = chp_doc([
        chp_log("260115SD0001", "Jul  5 2026  7:12AM", "1183-Trfc Collision-Unkn Inj",
                "I80 W / Donner Pass Rd", "Truckee", 39.324, -120.235),
        chp_log("260115SD0002", "Jul  5 2026  7:30AM", "1125-Traffic Hazard",
                "I80 E / Kingvale", "Truckee", 39.316, -120.440),
        chp_log("260115SD0003", "Jul  5 2026  7:41AM", "1182-Trfc Collision-No Inj",
                "US50 E / Echo Summit", "South Lake Tahoe", 38.812, -120.031),
        chp_log("260115SD0004", "Jul  5 2026  8:02AM", "1125-Traffic Hazard",
                "SR89 S / Emerald Bay Rd", "South Lake Tahoe", 38.955, -120.110),
        chp_log("260115SD0005", "Jul  5 2026  8:15AM", "1125-Traffic Hazard",
                "Jackson Rd / Mayhew Rd", "East Sac", 38.531, -121.344),
        chp_log("260115SD0006", "Jul  5 2026  8:22AM", "1182-Trfc Collision-No Inj",
                "I80 E / Douglas Blvd", "North Sac", 38.751, -121.281),
    ])
    (out / "chp.xml").write_text(chp)

    statuses_d3 = {
        "3-ED-50-25.4-E-110": ("R-1", R1_DESC),
        "3-ED-50-33.2-E-101": ("R-2", R2_DESC),
        "3-ED-50-45.0-W-102": ("R-2", R2_DESC),
        "3-PLA-80-30.5-E-120": ("R-1", R1_DESC),
        "3-NEV-80-40.2-E-121": ("R-2", R2_DESC),
        "3-NEV-80-48.0-W-122": ("R-2", R2_DESC),
        "3-PLA-89-5.0-S-130": ("R-2", R2_DESC),
    }
    (out / "cc_d03.xml").write_text(cwwp_doc([
        cc_from_point(p, 3, *statuses_d3[p[0]]) for p in CC_POINTS_D3
    ]))
    (out / "cc_d10.xml").write_text(cwwp_doc([
        cc_from_point(p, 10, "R-2", R2_DESC) for p in CC_POINTS_D10
    ]))

    (out / "lcs_d03.xml").write_text(cwwp_doc([
        # Avalanche control: SR-89 fully closed at Emerald Bay.
        lcs_record("S1AB-0001-storm", 3, "SR-89", "El Dorado", "South",
                   "Emerald Bay", "South Lake Tahoe", 38.952, -120.110,
                   38.940, -120.080, "Full", "Emergency Work", "All",
                   is_1097=True, indefinite=True),
        # Chain-control staging lane closure on I-80.
        lcs_record("S2CD-0002-storm", 3, "I-80", "Placer", "East",
                   "Baxter", "Alta", 39.200, -120.780, 39.230, -120.700,
                   "Lane", "Winter Operations", "1", is_1097=True),
        # Scheduled US-50 work that never got established in the storm.
        lcs_record("S3EF-0003-storm", 3, "US-50", "El Dorado", "East",
                   "Placerville", "Placerville", 38.730, -120.800,
                   38.740, -120.750, "Lane", "Tree Work", "1", is_1097=False),
    ]))
    (out / "wfigs.json").write_text(wfigs_doc([]))


def build_fire_day(out: Path) -> None:
    chp = chp_doc([
        chp_log("260705FD0001", "Jul  5 2026  2:12PM", "1125-Traffic Hazard",
                "I5 N / Grapevine Rd", "Fort Tejon", 34.930, -118.920),
        chp_log("260705FD0002", "Jul  5 2026  2:30PM", "CLOSURE of a Road",
                "I5 S / Frazier Mountain Park Rd", "Fort Tejon", 34.844, -118.860),
        chp_log("260705FD0003", "Jul  5 2026  2:45PM", "1183-Trfc Collision-Unkn Inj",
                "SR99 S / Ming Ave", "Bakersfield", 35.340, -119.020),
        chp_log("260705FD0004", "Jul  5 2026  3:01PM", "1125-Traffic Hazard",
                "US101 N / Vermont Ave", "Central LA", 34.062, -118.290),
    ])
    (out / "chp.xml").write_text(chp)

    (out / "lcs_d07.xml").write_text(cwwp_doc([
        lcs_record("F1AB-0001-fire", 7, "I-5", "Los Angeles", "North",
                   "Grapevine", "Lebec", 34.930, -118.920, 34.980, -118.940,
                   "Full", "Emergency Work", "All", is_1097=True, indefinite=True),
        lcs_record("F2CD-0002-fire", 7, "I-5", "Los Angeles", "South",
                   "Frazier Mountain Park Rd", "Lebec", 34.844, -118.860,
                   34.820, -118.850, "Full", "Emergency Work", "All",
                   is_1097=True, indefinite=True),
    ]))
    (out / "lcs_d06.xml").write_text(cwwp_doc([
        lcs_record("F3EF-0003-fire", 6, "SR-99", "Kern", "North",
                   "7th Standard Rd", "Bakersfield", 35.440, -119.050,
                   35.460, -119.060, "Lane", "Pavement Repair", "2",
                   is_1097=True),
    ]))
    (out / "cc_d03.xml").write_text(cwwp_doc([
        cc_from_point(p, 3, "R-0", R0_DESC) for p in CC_POINTS_D3
    ]))
    (out / "wfigs.json").write_text(wfigs_doc([
        {"name": "VULCAN", "id": "2026-CAKRN-031001", "acres": 48213,
         "contained": 15, "lat": 34.955, "lon": -118.960},
        {"name": "CREEK", "id": "2026-CAFKU-031002", "acres": 3200,
         "contained": 85, "lat": 36.780, "lon": -119.750},
        {"name": "REMOTE", "id": "2026-CASNF-031003", "acres": 12000,
         "contained": 40, "lat": 37.000, "lon": -118.500},
    ]))


def write_manifest(out: Path, scenario: str, description: str) -> None:
    (out / "manifest.json").write_text(json.dumps({
        "scenario": scenario,
        "synthetic": True,
        "description": description,
        "built_by": "evals/build_fixtures.py",
    }, indent=2))


def main() -> None:
    scenarios = {
        "quiet-day": (build_quiet_day,
                      "Summer day: no chains, one US-101 lane closure, minor "
                      "incidents, one fully contained fire far from highways."),
        "storm-day": (build_storm_day,
                      "Sierra storm: R-2 US-50 Twin Bridges to Meyers, R-1/R-2 "
                      "I-80, R-2 SR-88/SR-89, SR-89 full closure at Emerald "
                      "Bay, spinout incidents."),
        "fire-day": (build_fire_day,
                     "Fire closure: VULCAN fire (48,213 ac, 15%) near I-5 "
                     "Grapevine, I-5 fully closed both directions, SR-99 open "
                     "with one lane closure."),
    }
    for name, (builder, description) in scenarios.items():
        out = FIXTURES / name
        out.mkdir(parents=True, exist_ok=True)
        builder(out)
        write_manifest(out, name, description)
        print(f"built {name}")


if __name__ == "__main__":
    main()
