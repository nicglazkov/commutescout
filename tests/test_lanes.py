"""lane_layout parsing, one fixture string per feed dialect."""

from __future__ import annotations

import pytest

from ca_roads import lanes


def closed(layout: dict) -> list[int]:
    return [ln["n"] for ln in layout["lanes"] if ln["state"] == "closed"]


def types(layout: dict) -> list[str]:
    return [ln["type"] for ln in layout["lanes"]]


# ---------------------------------------------------------------- target

@pytest.mark.parametrize(("total", "shut", "want"), [
    (4, {4}, 3),            # right lane closed: move one left
    (4, {1}, 2),            # fast lane closed
    (4, {1, 2}, 3),
    (4, {3, 4}, 2),
    (4, {2}, 3),            # tie: the side with more open lanes wins
    (5, {4}, 3),            # tie, larger run on the left
    (3, {2}, 3),            # equal runs: right
    (4, set(), None),       # nothing closed: no move
    (3, {1, 2, 3}, None),   # nothing open: no lane to be in
])
def test_target(total, shut, want):
    assert lanes.build(total, shut)["target"] == want


def test_target_prefers_general_over_hov():
    layout = lanes.build(4, {2}, types={1: "hov"})
    # Lane 1 is as close as lane 3, but it is the HOV lane.
    assert layout["target"] == 3


def test_build_rejects_undrawable_widths():
    assert lanes.build(0, set()) is None
    assert lanes.build(13, {1}) is None


def test_contract_shape():
    layout = lanes.build(4, {4}, shoulders={"right": "closed"})
    assert layout == {
        "total": 4,
        "lanes": [{"n": 1, "type": "general", "state": "open"},
                  {"n": 2, "type": "general", "state": "open"},
                  {"n": 3, "type": "general", "state": "open"},
                  {"n": 4, "type": "general", "state": "closed"}],
        "shoulder": {"right": "closed"},
        "target": 3,
        "basis": "feed",
    }


# ---------------------------------------------------------------- Caltrans LCS

@pytest.mark.parametrize(("text", "total", "want_closed", "want_types", "shoulder"), [
    ("1", 4, [1], None, None),
    ("3, 4", 4, [3, 4], None, None),
    ("1, 2, 3", 3, [1, 2, 3], None, None),
    ("All", 3, [1, 2, 3], None, None),
    ("2, RShoulder", 3, [2], None, {"right": "closed"}),
    ("LShoulder, 1", 4, [1], None, {"left": "closed"}),
    ("LShoulder, 1, 2, RShoulder", 2, [1, 2], None,
     {"left": "closed", "right": "closed"}),
    # HOV is the leftmost lane and counts inside totalExistingLanes.
    ("HOV, 1, 2", 4, [1, 2, 3], ["hov", "general", "general", "general"], None),
    ("Left HOV", 4, [1], ["hov", "general", "general", "general"], None),
    ("LShoulder, HOV, 1", 5, [1, 2], ["hov"] + ["general"] * 4, {"left": "closed"}),
    ("Express 1, Express 2", 5, [1, 2], ["express", "express"] + ["general"] * 3, None),
    # Right HOV beyond a two-lane count is an extra lane.
    ("LShoulder, 1, 2, Right HOV", 2, [1, 2, 3], ["general", "general", "hov"],
     {"left": "closed"}),
    # An auxiliary lane is added at the right.
    ("2, Auxiliary", 3, [2, 4], ["general", "general", "general", "aux"], None),
    # Turn pockets, bike lanes and the median are not travel lanes.
    ("1, Left Turn, Bike Lane, Median", 2, [1], None, None),
    # A lane number past the feed's own count widens the road.
    ("4", 3, [4], None, None),
])
def test_lcs(text, total, want_closed, want_types, shoulder):
    layout = lanes.from_lcs(text, total)
    assert layout["basis"] == "feed"
    assert closed(layout) == want_closed
    if want_types:
        assert types(layout) == want_types
    assert layout.get("shoulder") == shoulder


def test_lcs_shoulder_only_draws_no_merge():
    layout = lanes.from_lcs("RShoulder", 3)
    assert closed(layout) == []
    assert layout["shoulder"] == {"right": "closed"}
    assert layout["target"] is None


def test_lcs_without_count_uses_lookup_or_nothing():
    assert lanes.from_lcs("1, 2", None) is None
    layout = lanes.from_lcs("1, 2", None, lookup_total=4, lookup_types={1: "hov"})
    assert layout["basis"] == "lookup"
    # The map says lane 1 is HOV, so LCS lanes 1 and 2 are lanes 2 and 3.
    assert closed(layout) == [2, 3]
    assert layout["target"] == 4


def test_lcs_nothing_to_draw():
    assert lanes.from_lcs("", 4) is None
    assert lanes.from_lcs("Bike Lane, Sidewalk", 2) is None


# ---------------------------------------------------------------- CHP

def chp(*texts: str) -> list[tuple[str, str]]:
    """Details newest first, the way the feed lists them."""
    return [("Oct 29 2026 3:00PM", t) for t in reversed(texts)]


@pytest.mark.parametrize(("texts", "total", "want"), [
    (["[1] 2 VEHS BLKG #3 #4"], 4, [3, 4]),
    (["[2] BLKING #1 LN [Shared]"], 4, [1]),
    (["[11] 646-181 SB 51 JSO  EXPO BLKG 1/2 [Shared]"], 4, [1, 2]),
    (["[22] BLKG #3,4 LNS [Shared]"], 5, [3, 4]),
    (["[2] BLKNG LNS 3-4"], 4, [3, 4]),
    (["[2] BLKNG LN 3"], 4, [3]),
    (["[11] #  1  LN BLOCKED   [Shared]"], 3, [1]),
    (["[1] [1] RED TOYT CAM, HAZARD LIGHTS BLKNG #4 LN [Shared]"], 4, [4]),
    (["[6] B118-053 TRACY FSP 97 PARTLY BLKG LN #1  "], 3, [1]),
    (["[43] B118-064 FIRE HAS 2 LEFT LNS BLKD   [Shared]"], 4, [1, 2]),
    (["[4] PART BLKG SLO LANE "], 3, [3]),
    (["[3] ALL LNS BLKD"], 3, [1, 2, 3]),
    (["[5] SIGALERT ALL NB LANES BLOCKED"], 4, [1, 2, 3, 4]),
    # "In the #N" without a block word: the lane is taken.
    (["[10] [Appended, 15:20:37] [2] VEH IN #1 LN  [Shared]"], 4, [1]),
    (["[6] [Appended, 15:18:10] [1] PLE DODG STALLED IN #3 LN  [Shared]"], 3, [3]),
    (["[2] 1 LADDER IN THE #1 // OTHER LADDER IN THE #3"], 4, [1, 3]),
    # A count with no position goes from the right.
    (["[4] [4] BLKG 1 LN [Shared]"], 4, [4]),
])
def test_chp_lanes(texts, total, want):
    layout = lanes.from_chp(chp(*texts), total)
    assert closed(layout) == want


def test_chp_newest_comment_wins():
    details = chp("[11] 646-181 SB 51 JSO  EXPO BLKG 1/2 [Shared]",
                  "[19] 646-181 #2 LN CLR / CHP HAS #1 LN BLKG/ 181 IN TOW [Shared]")
    layout = lanes.from_chp(details, 4)
    assert closed(layout) == [1]
    assert layout["target"] == 2
    assert layout["basis"] == "lookup"


def test_chp_orders_by_sequence_number_not_list_position():
    # Listed oldest first this time: the [N] numbers still decide.
    details = [("t", "[1] BLKG #2 #3"), ("t", "[5] ALL LANES OPEN")]
    layout = lanes.from_chp(details, 3)
    assert closed(layout) == []


def test_chp_moved_to_shoulder():
    details = chp("[1] 2 VEHS BLKG #3 #4", "[13] B24-230 ALL VEHS TO RHS  [Shared]")
    layout = lanes.from_chp(details, 4)
    assert closed(layout) == []
    assert layout["shoulder"] == {"right": "closed"}
    assert layout["target"] is None


def test_chp_all_open_after_shoulder():
    layout = lanes.from_chp(chp("[3] BLKG #2", "[25] 78-146 ALL ON RS - ALL LANES OPEN [Shared]"),
                            3)
    assert closed(layout) == []
    assert layout["shoulder"] == {"right": "closed"}


def test_chp_center_divider_is_left_shoulder():
    layout = lanes.from_chp(chp("[20] VA-K5 RDWY OPEN 3 VEH IN CD"), 3)
    assert closed(layout) == []
    assert layout["shoulder"] == {"left": "closed"}


def test_chp_shoulder_words():
    layout = lanes.from_chp(chp("[2] RHS WILL BE CLOSED"), 4)
    assert closed(layout) == []
    assert layout["shoulder"] == {"right": "closed"}


def test_chp_hov_lane():
    layout = lanes.from_chp(chp("[23] GRY SCION TC BLOCKING HOV LN and FSP IS 97"), 5)
    assert closed(layout) == [1]
    assert types(layout)[0] == "hov"
    assert layout["target"] == 2


def test_chp_hov_from_lookup_shifts_numbers():
    # The map says lane 1 is the HOV lane; CHP's #1 is the lane after it.
    layout = lanes.from_chp(chp("[2] BLKING #1 LN"), 5, types={1: "hov"})
    assert closed(layout) == [2]
    assert types(layout)[0] == "hov"


@pytest.mark.parametrize("text", [
    "[27] BLK SMOKE  [Shared]",                 # BLK is black, not blocking
    "[1] DRK GRY POR BLK JEEP ON ITS SIDE",
    "[1] FARSI TRANS #43697",                   # case numbers are not lanes
    "[33] 1039 3A PRO STAR C#23265107 20 ET",
    "[5] NEG BLKG ",
    "[1] MUNI BUS BLKNG LN [Shared]",           # a lane, but which?
    "[3] DEBRI - BLKG RDWY ",
    "[14] RIDER DOWN IN LNS  [Shared]",
    "",
])
def test_chp_no_lane_information(text):
    assert lanes.from_chp(chp(text), 4) is None


def test_chp_needs_a_lane_count():
    assert lanes.from_chp(chp("[1] BLKG #2"), None) is None


def test_chp_duplicate_appended_copies_count_once():
    details = chp("[2] BLKNG LNS 3-4", "[26] [Appended, 13:51:04] [3] BLKG 3-4 ")
    assert closed(lanes.from_chp(details, 4)) == [3, 4]


# ---------------------------------------------------------------- free text

@pytest.mark.parametrize(("text", "total", "want", "basis"), [
    ("Right lane closed", 3, [3], "feed"),
    ("Left Lane Blocked", 3, [1], "feed"),
    ("2 Right Lanes Closed", 4, [3, 4], "feed"),
    ("Two left lanes", 3, [1, 2], "feed"),
    ("All Lanes Closed", 2, [1, 2], "feed"),
    ("One lane closed", 3, [3], "count_only"),
    ("Right Shoulder Closed", 2, [], "feed"),
])
def test_text(text, total, want, basis):
    layout = lanes.resolve(lanes.text_refs(text), total)
    assert closed(layout) == want
    assert layout["basis"] == basis


def test_text_without_lane_words():
    assert lanes.resolve(lanes.text_refs("Road work"), 3) is None


# ---------------------------------------------------------------- WZDx

def test_wzdx_v4_lanes():
    layout = lanes.from_wzdx([
        {"order": 1, "type": "shoulder", "status": "open"},
        {"order": 2, "type": "general", "status": "open"},
        {"order": 3, "type": "general", "status": "open"},
        {"order": 4, "type": "general", "status": "closed"},
        {"order": 5, "type": "shoulder", "status": "closed"},
    ])
    assert layout["total"] == 3
    assert closed(layout) == [3]
    assert layout["shoulder"] == {"left": "open", "right": "closed"}
    assert layout["target"] == 2
    assert layout["basis"] == "feed"


def test_wzdx_merge_and_types():
    layout = lanes.from_wzdx([
        {"order": 3, "type": "exit-lane", "status": "open"},
        {"order": 1, "type": "general", "status": "merge-right"},
        {"order": 2, "type": "general", "status": "open"},
        {"order": 4, "type": "bike-lane", "status": "closed"},
    ])
    assert types(layout) == ["general", "general", "exit"]
    assert closed(layout) == [1]
    assert layout["target"] == 2


def test_wzdx_v3_shoulder_names():
    layout = lanes.from_wzdx([
        {"order": 1, "type": "left-shoulder", "status": "closed"},
        {"order": 2, "type": "left-lane", "status": "closed"},
        {"order": 3, "type": "right-lane", "status": "open"},
    ])
    assert closed(layout) == [1]
    assert layout["shoulder"] == {"left": "closed"}


@pytest.mark.parametrize("raw", [
    None, [], "lanes", [{"order": "x"}],
    [{"order": 1, "type": "general", "status": "open"}],   # nothing closed
])
def test_wzdx_nothing(raw):
    assert lanes.from_wzdx(raw) is None


# ---------------------------------------------------------------- CDOT

def test_cdot_positions_from_words():
    layout = lanes.from_cdot([{"direction": "west", "laneCount": 3, "laneClosures": "1",
                               "closedLaneTypes": ["Right Lane"]}])
    assert closed(layout) == [3]
    assert layout["basis"] == "feed"


def test_cdot_count_only():
    layout = lanes.from_cdot([{"laneCount": 4, "laneClosures": "2",
                               "closedLaneTypes": ["Lane"]}])
    assert closed(layout) == [3, 4]
    assert layout["basis"] == "count_only"
    assert layout["target"] == 2


def test_cdot_all_and_shoulders():
    layout = lanes.from_cdot([{"laneCount": 2, "laneClosures": "2",
                               "closedLaneTypes": ["Left Lane", "Right Lane"]}])
    assert closed(layout) == [1, 2]
    layout = lanes.from_cdot([{"laneCount": 2, "laneClosures": "0",
                               "closedLaneTypes": ["Right Shoulder"]}])
    assert closed(layout) == []
    assert layout["shoulder"] == {"right": "closed"}


def test_cdot_skips_empty_impacts():
    assert lanes.from_cdot([{"laneCount": 2, "laneClosures": "0"}]) is None
    assert lanes.from_cdot([{"laneClosures": "1"}]) is None
    assert lanes.from_cdot(None) is None
    layout = lanes.from_cdot([{"laneCount": 2, "laneClosures": "0"},
                              {"laneCount": 3, "laneClosures": "1",
                               "closedLaneTypes": ["Left Lane"]}])
    assert closed(layout) == [1]


# ---------------------------------------------------------------- NE Compass

def nec(*rows):
    return [{"type": t, "status": s, "index": str(i)} for i, (t, s) in enumerate(rows)]


def test_nec_lane_details():
    layout = lanes.from_lane_details(nec(("Shoulder", "Cleared"), ("MainLane", "Cleared"),
                                         ("MainLane", "Blocked"), ("Shoulder", "Unknown")))
    assert layout["total"] == 2
    assert closed(layout) == [2]
    assert layout["shoulder"] == {"left": "open"}
    assert layout["target"] == 1


def test_nec_divider_picks_the_blocked_direction():
    layout = lanes.from_lane_details(nec(("MainLane", "Cleared"), ("Divider", "Cleared"),
                                         ("MainLane", "Blocked"), ("MainLane", "Cleared")))
    assert layout["total"] == 2
    assert closed(layout) == [1]


def test_nec_nothing_blocked():
    assert lanes.from_lane_details(nec(("MainLane", "Unknown"), ("MainLane", "Cleared"))) is None
    assert lanes.from_lane_details([]) is None
    assert lanes.from_lane_details([{"type": "MainLane", "status": "Blocked"}]) is None


@pytest.mark.parametrize(("texts", "total", "want"), [
    (["[17] B24-120 BLKG 2 3 4 LNS  [Shared]"], 4, [2, 3, 4]),
    (["[41] B32-012 1-2 ARE BLOCKED  [Shared]"], 4, [1, 2]),
    (["[20] B24-089 1 AND 2 TEMP BLKD 3 AND 4 OPEN  [Shared]"], 4, [1, 2]),
    (["[4] 16-S1 98 CT #2 LANE CLOSURE #1 LN OPEN"], 3, [2]),
    (["[3] GRAY CHAIR IN #1 AND #2 LANES"], 4, [1, 2]),
    (["[2] BLKG #2", "[8] [CHP] has closed their incident [261029OC0484]"], 3, [2]),
])
def test_chp_number_lists(texts, total, want):
    assert closed(lanes.from_chp(chp(*texts), total)) == want
