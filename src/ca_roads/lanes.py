"""Lane layouts: which lanes an event closes, as a drawing can use them.

Every feed says it differently. Caltrans LCS lists lanes as "1, 2",
"All", "LShoulder, HOV, 1"; CHP dispatchers type "2 VEHS BLKG #3 #4"
and "MOVED TO RHS"; WZDx feeds carry a ``lanes`` array; CDOT counts
closed lanes; NE Compass lists every lane with a status. This module
turns each into one shape, ``lane_layout``::

    {"total": 4,
     "lanes": [{"n": 1, "type": "general", "state": "open"}, ...],
     "shoulder": {"right": "closed"},
     "target": 3,
     "basis": "feed"}

Lanes run left to right in the direction of travel and ``n`` 1 is the
leftmost (CHP's "#1", the fast lane). ``type`` is general, hov,
express, exit or aux; ``state`` is open or closed. ``shoulder`` holds
only the sides a feed spoke about. ``target`` is the lane to be in:
the nearest open lane next to the closed ones, or None when no move is
needed or it is unclear. ``basis`` says how much of it the feed said:
"feed" (which lanes), "count_only" (how many lanes; the closed ones
are assumed from the right) or "lookup" (the feed named the lanes but
the lane count came from the map).

Parsing is in two steps so a feed without a lane count can still be
drawn once the count is known: each parser returns ``LaneRefs``
(lanes counted from the left or from the right, shoulders, "all"),
and ``resolve`` places them on a road of a known width.

Nothing here does I/O; the map lookup for a missing count lives with
the callers (``ca_roads_demo.lanecount``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

LANE_TYPES = ("general", "hov", "express", "exit", "aux")
MAX_LANES = 12
_WORDS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6,
          "SINGLE": 1, "BOTH": 2}


@dataclass
class LaneRefs:
    """What a feed said about lanes, before the road's width is known.

    ``left`` holds general lanes counted from the left (1 is the
    leftmost general lane, after any HOV or express lanes), ``right``
    lanes counted from the right (1 is the rightmost). ``count`` is a
    number of closed lanes with no position (placed from the right).
    """

    left: set[int] = field(default_factory=set)
    right: set[int] = field(default_factory=set)
    all_closed: bool = False
    count: int | None = None
    # Left-side special lanes the feed itself named: an HOV lane, and
    # express lanes counted from the left ({1, 2} for "Express 1, 2").
    hov_left: bool = False
    hov_left_closed: bool = False
    hov_right_closed: bool = False
    express_closed: set[int] = field(default_factory=set)
    aux_closed: bool = False
    shoulders: dict[str, str] = field(default_factory=dict)
    # The feed said every lane is open again (CHP "ALL LNS OPEN").
    all_open: bool = False

    def lanes_named(self) -> bool:
        return bool(self.left or self.right or self.all_closed or self.count
                    or self.hov_left_closed or self.hov_right_closed
                    or self.express_closed or self.aux_closed)

    def any(self) -> bool:
        return self.lanes_named() or bool(self.shoulders) or self.all_open

    def needs_total(self) -> bool:
        """True when the feed gave no lane count of its own."""
        return self.any()


def target_lane(lanes: list[dict]) -> int | None:
    """The lane to be in: the open lane nearest the closed ones.

    Ties go to a general lane over an HOV, exit or aux lane, then to the
    side with more open lanes in a row (the one traffic flows into),
    then to the right. None when nothing is closed or nothing is open.
    """
    closed = [ln["n"] for ln in lanes if ln["state"] == "closed"]
    open_ = [ln for ln in lanes if ln["state"] == "open"]
    if not closed or not open_:
        return None
    by_n = {ln["n"]: ln for ln in lanes}

    def run_len(n: int) -> int:
        size, k = 1, n - 1
        while k in by_n and by_n[k]["state"] == "open":
            size, k = size + 1, k - 1
        k = n + 1
        while k in by_n and by_n[k]["state"] == "open":
            size, k = size + 1, k + 1
        return size

    def score(ln: dict) -> tuple:
        dist = min(abs(ln["n"] - c) for c in closed)
        return (dist, ln["type"] != "general", -run_len(ln["n"]), -ln["n"])

    return min(open_, key=score)["n"]


def build(total: int, closed: set[int], *, types: dict[int, str] | None = None,
          shoulders: dict[str, str] | None = None, basis: str = "feed") -> dict | None:
    """A lane_layout for a road ``total`` lanes wide, or None when the
    width is not drawable."""
    if not isinstance(total, int) or not 1 <= total <= MAX_LANES:
        return None
    types = types or {}
    lanes = [{"n": n, "type": types.get(n, "general") if types.get(n) in LANE_TYPES
              else "general",
              "state": "closed" if n in closed else "open"}
             for n in range(1, total + 1)]
    out: dict = {"total": total, "lanes": lanes}
    sh = {k: v for k, v in (shoulders or {}).items()
          if k in ("left", "right") and v in ("open", "closed")}
    if sh:
        out["shoulder"] = sh
    out["target"] = target_lane(lanes)
    out["basis"] = basis
    return out


def resolve(refs: LaneRefs, total: int | None, *, types: dict[int, str] | None = None,
            basis: str = "feed") -> dict | None:
    """Place ``refs`` on a road ``total`` lanes wide (HOV and express
    lanes the feed named count inside ``total``; an auxiliary lane is
    added at the right). ``types`` comes from a map lookup and may mark
    lane 1 as an HOV lane, which shifts the feed's general-lane
    numbers right by one."""
    if not refs.any() or not total:
        return None
    types = dict(types or {})
    express = max(refs.express_closed) if refs.express_closed else 0
    hov_left = refs.hov_left or refs.hov_left_closed
    offset = express + (1 if hov_left else 0)
    if not hov_left and not express and types.get(1) == "hov":
        offset = 1
    width = total
    if refs.left:
        # A lane number past the stated width is the feed's count being
        # short (seen in LCS), not a lane to drop.
        width = min(MAX_LANES, max(width, max(refs.left) + offset))
    closed: set[int] = set()
    for k in range(1, express + 1):
        types[k] = "express"
        if k in refs.express_closed:
            closed.add(k)
    if hov_left:
        types[express + 1] = "hov"
        if refs.hov_left_closed:
            closed.add(express + 1)
    for k in refs.left:
        closed.add(k + offset)
    if refs.hov_right_closed:
        # "1, 2, Right HOV" on a 2-lane count: the HOV lane is extra.
        if refs.left and max(refs.left) + offset >= width:
            width += 1
        types[width] = "hov"
        closed.add(width)
    if refs.aux_closed:
        width += 1
        types[width] = "aux"
        closed.add(width)
    for k in refs.right:
        if 1 <= k <= width:
            closed.add(width - k + 1)
    if refs.count:
        # Only how many: place them from the right.
        closed.update(range(max(1, width - refs.count + 1), width + 1))
        basis = "count_only"
    if refs.all_closed:
        closed = set(range(1, width + 1))
    if refs.all_open:
        closed = set()
    return build(width, closed, types=types, shoulders=refs.shoulders, basis=basis)


# ---------------------------------------------------------------- Caltrans LCS

def lcs_refs(lanes_closed: str | None) -> LaneRefs:
    """Caltrans LCS ``lanesClosed``: "1, 2", "All", "HOV, 1, 2",
    "LShoulder, 1, RShoulder", "Express 1, Express 2", "1, Auxiliary".
    Turn pockets, bike lanes, sidewalks and the median are not travel
    lanes and are ignored."""
    refs = LaneRefs()
    for raw in (lanes_closed or "").split(","):
        tok = raw.strip().lower()
        if not tok:
            continue
        if tok == "all":
            refs.all_closed = True
        elif tok.isdigit():
            if 1 <= int(tok) <= MAX_LANES:
                refs.left.add(int(tok))
        elif tok.startswith("express"):
            digits = re.findall(r"\d+", tok)
            if digits and 1 <= int(digits[0]) <= 4:
                refs.express_closed.add(int(digits[0]))
        elif tok in ("hov", "left hov"):
            refs.hov_left = refs.hov_left_closed = True
        elif tok == "right hov":
            refs.hov_right_closed = True
        elif tok == "lshoulder":
            refs.shoulders["left"] = "closed"
        elif tok == "rshoulder":
            refs.shoulders["right"] = "closed"
        elif tok.startswith("aux"):
            refs.aux_closed = True
    return refs


def from_lcs(lanes_closed: str | None, total_lanes: int | None, *,
             lookup_total: int | None = None,
             lookup_types: dict[int, str] | None = None) -> dict | None:
    """lane_layout for one LCS record. The feed's ``totalExistingLanes``
    wins; a map lookup fills in only when the feed has none."""
    refs = lcs_refs(lanes_closed)
    if not refs.any():
        return None
    if total_lanes:
        return resolve(refs, total_lanes, basis="feed")
    if lookup_total:
        return resolve(refs, lookup_total, types=lookup_types, basis="lookup")
    return None


# ---------------------------------------------------------------- CHP

# Words that mean a lane is blocked. Bare "BLK" is not one: in CHP
# shorthand it is the color black ("BLK SMOKE", "BLK SUV").
_BLOCK = re.compile(r"\b(BLKG|BLKNG|BLKING|BLKD|BLOCK|BLOCKS|BLOCKING|BLOCKED|"
                    r"CLSD|CLOSED|CLOSING|CLOSE|SHUT|SHUTTING)\b")
_OPEN = re.compile(r"\b(OPEN|OPENED|OPN|REOPEN|REOPENED|CLR|CLRD|CLEAR|CLEARED)\b")
# "#3", "#3,4", "#3 #4", "#3 AND #4", "#  1", "#3-4".
# A digit followed by another digit is a case or unit number
# ("C#23265107", "TRANS #43697"), never a lane.
_HASH = re.compile(r"#\s*([1-9])(?!\d)((?:\s*(?:,|&|/|-|AND|\s)\s*#?\s*[1-9](?!\d))*)")
# "LN 3", "LNS 3-4", "LN #1", "LANE 2", "LANES 1/2".
_LN_NUM = re.compile(r"\bL(?:N|NS|ANE|ANES)\s*#?\s*([1-9])(?!\d)"
                     r"((?:\s*(?:,|&|/|-|AND)\s*#?\s*[1-9](?!\d))*)")
# "BLKG 1/2", "BLKG 3-4": numbers joined right after a block word.
_BLOCK_NUMS = re.compile(r"\b(?:BLKG|BLKNG|BLKING|BLKD|BLOCKING|BLOCKED)\s+([1-9])(?!\d)"
                         r"((?:\s*(?:/|-|,|&|AND|\s)\s*[1-9](?!\d))+)")
# "1-2 ARE BLOCKED", "1 AND 2 TEMP BLKD 3 AND 4 OPEN", "#2 LANE CLOSURE":
# a number list, then the word that says what happened to it.
_NUM_LIST = r"#?\s*[1-9](?!\d)(?:\s*(?:,|&|/|-|AND)\s*#?\s*[1-9](?!\d))*"
_NUMS_STATE = re.compile(
    rf"(?<![\w-])({_NUM_LIST})\s+(?:(?:LNS?|LANES?|ARE|IS|TEMP|STILL|NOW)\s+){{0,3}}"
    r"(BLKG|BLKNG|BLKING|BLKD|BLOCKED|BLOCKING|CLOSED|CLSD|CLOSURE|SHUT|"
    r"OPEN|OPN|OPENED|REOPENED|CLR|CLEAR|CLEARED)\b")
_OPEN_WORDS = {"OPEN", "OPN", "OPENED", "REOPENED", "CLR", "CLEAR", "CLEARED"}
# "2 LEFT LNS", "TWO RIGHT LANES", "RIGHT 2 LNS".
_SIDE_COUNT = re.compile(r"\b([1-6]|ONE|TWO|THREE|FOUR|FIVE|SIX|BOTH)\s+(LEFT|LT|RIGHT|RT)\s+"
                         r"(?:LNS|LANES|LN|LANE)\b|\b(LEFT|LT|RIGHT|RT)\s+([1-6])\s+(?:LNS|LANES)\b")
_SIDE_ONE = re.compile(r"\b(LEFT|LT|RIGHT|RT|SLOW|SLO|FAST)\s+(?:LN|LANE)\b")
_COUNT = re.compile(r"\b([1-6]|ONE|TWO|THREE|FOUR|FIVE|SIX)\s+(?:LNS|LANES|LN|LANE)\b")
_ALL = re.compile(r"\bALL\s+(?:[NSEW]B\s+)?(?:LNS|LANES|TRAFFIC|LN)\b|\bFULL\s+CLOSURE\b|"
                  r"\bHARD\s+CLOSURE\b|\bALL\s+DIRECTIONS\b")
_HOV = re.compile(r"\b(HOV|CARPOOL|DIAMOND)\s*(?:LN|LANE)?\b")
_RHS = re.compile(r"\b(RHS|RS|R/S|RT\s+SHOULDER|RIGHT\s+SHOULDER|SHOULDER)\b")
_LHS = re.compile(r"\b(LHS|LS|L/S|CD|CENTER\s+DIVIDER|MEDIAN|LT\s+SHOULDER|LEFT\s+SHOULDER)\b")
# Vehicles moved off the lanes: the lanes are clear, the shoulder is not.
_MOVED = re.compile(r"\b(MOVED|PUSHED|PULLED|TOWED|ALL|BOTH|VEHS?|NOW|OVER)\b[^/]*?"
                    r"\b(?:TO|ON|IN|ONTO)\s+(?:THE\s+)?(RHS|RS|R/S|RIGHT\s+SHOULDER|LHS|LS|CD|"
                    r"CENTER\s+DIVIDER|LEFT\s+SHOULDER|SHOULDER)\b")
# "VEH IN #1 LN", "STALLED IN THE #3", "1125 IN #2 LANE": a lane taken.
_IN_LANE = re.compile(r"\bIN\s+(?:THE\s+)?#\s*([1-9])(?!\d)")
_NOISE = re.compile(r"\[(?:Shared|Notification|Appended[^\]]*|[A-Z]+|\d+)\]", re.I)
_SEQ = re.compile(r"^\s*\[(\d+)\]")
_CLAUSE = re.compile(r"\s*//\s*|\s+/\s*|/\s+|;|\s+-\s+")


def _nums(first: str, rest: str) -> set[int]:
    """'3' + ',4' -> {3, 4}; '3' + '-5' -> {3, 4, 5}."""
    out = {int(first)}
    prev = int(first)
    for sep, d in re.findall(r"(,|&|/|-|AND|\s)\s*#?\s*([1-9])", rest):
        n = int(d)
        if sep == "-" and n > prev:
            out.update(range(prev, n + 1))
        else:
            out.add(n)
        prev = n
    return {n for n in out if 1 <= n <= MAX_LANES}


def _count(word: str) -> int:
    return int(word) if word.isdigit() else _WORDS.get(word, 0)


def _ordered(details) -> list[str]:
    """Detail texts oldest first. CHP lists newest first and numbers
    each comment "[N]"; the number wins when present."""
    rows = []
    for i, item in enumerate(details or ()):
        text = item[1] if isinstance(item, (tuple, list)) else str(item)
        m = _SEQ.match(text or "")
        rows.append((int(m.group(1)) if m else None, -i, text or ""))
    if any(r[0] is not None for r in rows):
        rows.sort(key=lambda r: (r[0] if r[0] is not None else 0, r[1]))
    else:
        rows.reverse()
    seen: set[str] = set()
    out = []
    for _, _, text in rows:
        clean = _NOISE.sub(" ", text).strip().strip('"').upper()
        clean = re.sub(r"\s+", " ", clean).strip()
        # "[Appended]" copies repeat a comment; one copy is enough.
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def _clear_lanes(refs: LaneRefs) -> None:
    refs.left.clear()
    refs.right.clear()
    refs.all_closed = False
    refs.count = None
    refs.hov_left_closed = False


def _apply_clause(refs: LaneRefs, clause: str) -> None:
    """Fold one clause of a comment into ``refs``."""
    if "THEIR INCIDENT" in clause:
        return  # "[CHP] has closed their incident": bookkeeping
    groups = []
    for m in _NUMS_STATE.finditer(clause):
        first = re.search(r"[1-9]", m.group(1))
        groups.append((_nums(first.group(0), m.group(1)[first.end():]),
                       m.group(2) in _OPEN_WORDS))
    if {g[1] for g in groups} == {True, False}:
        # Some lanes shut, others open, in one breath.
        for ns, is_open in groups:
            if is_open:
                refs.left -= ns
            else:
                refs.left |= ns
                refs.all_open = False
        return
    blocked = bool(_BLOCK.search(clause))
    opened = bool(_OPEN.search(clause)) and not blocked
    moved = _MOVED.search(clause)
    nums: set[int] = set()
    for ns, is_open in groups:
        if is_open == opened:
            nums |= ns
    for m in _HASH.finditer(clause):
        nums |= _nums(m.group(1), m.group(2) or "")
    for m in _LN_NUM.finditer(clause):
        nums |= _nums(m.group(1), m.group(2) or "")
    if blocked:
        for m in _BLOCK_NUMS.finditer(clause):
            nums |= _nums(m.group(1), m.group(2) or "")
    if moved and not nums:
        # Off the lanes and onto a shoulder: the lanes are clear, the
        # shoulder is not.
        _clear_lanes(refs)
        side = "left" if _LHS.fullmatch(moved.group(2)) else "right"
        refs.shoulders[side] = "closed"
        if not opened:
            return
    if opened:
        if nums:
            refs.left -= nums
        elif re.search(r"\b(ALL|LNS|LANES|RDWY|ROADWAY|HWY)\b", clause):
            _clear_lanes(refs)
            refs.all_open = True
        if re.search(r"\b(RHS|RS)\s+(?:IS\s+)?(OPEN|OPN|CLR|CLEAR)", clause):
            refs.shoulders.pop("right", None)
        return
    if not blocked:
        # "VEH IN #1 LN", "CHAIR IN #1 AND #2 LANES": the lane is taken.
        if _IN_LANE.search(clause):
            refs.left |= nums
            refs.all_open = False
        return
    refs.all_open = False
    if _ALL.search(clause):
        refs.all_closed = True
        return
    positioned = bool(nums)
    refs.left |= nums
    for m in _SIDE_COUNT.finditer(clause):
        n = _count(m.group(1) or m.group(4) or "")
        side = m.group(2) or m.group(3) or ""
        if n:
            (refs.left if side.startswith("L") else refs.right).update(range(1, n + 1))
            positioned = True
    if not positioned:
        for m in _SIDE_ONE.finditer(clause):
            (refs.left if m.group(1) in ("LEFT", "LT", "FAST") else refs.right).add(1)
            positioned = True
    if not positioned and _HOV.search(clause):
        refs.hov_left = refs.hov_left_closed = True
        positioned = True
    if not positioned:
        m = _COUNT.search(clause)
        if m and _count(m.group(1)):
            refs.count = max(refs.count or 0, _count(m.group(1)))
            positioned = True
    if not positioned:
        if _RHS.search(clause):
            refs.shoulders["right"] = "closed"
        if _LHS.search(clause):
            refs.shoulders["left"] = "closed"


def chp_refs(details) -> LaneRefs:
    """Lane state from a CHP incident's dispatcher comments, applied in
    order so the newest word wins ("#2 LN CLR" after "BLKG #1 #2")."""
    refs = LaneRefs()
    for text in _ordered(details):
        for clause in _CLAUSE.split(text):
            if clause.strip():
                _apply_clause(refs, clause.strip())
    return refs


def from_chp(details, total: int | None, *, types: dict[int, str] | None = None
             ) -> dict | None:
    """lane_layout for a CHP incident. CHP never says how wide the road
    is, so ``total`` comes from a map lookup (basis "lookup")."""
    refs = chp_refs(details)
    if not refs.any() or not total:
        return None
    return resolve(refs, total, types=types, basis="lookup")


# ---------------------------------------------------------------- free text

def text_refs(text: str | None) -> LaneRefs:
    """Lane words in an agency's plain sentence ("Right lane closed",
    "2 left lanes blocked", "All lanes closed", "Right shoulder closed",
    "Lanes 1, 2 closed"). The CHP grammar covers it; this is the same
    pass over one clause list."""
    refs = LaneRefs()
    upper = re.sub(r"\s+", " ", (text or "").upper())
    for clause in _CLAUSE.split(upper):
        clause = clause.strip()
        if not clause:
            continue
        # A sentence that names lanes is about blocking them unless it
        # says otherwise ("Right lane closed" has a verb; "Right lane"
        # in a LanesAffected field does not).
        if not _BLOCK.search(clause) and not _OPEN.search(clause):
            clause = clause + " BLOCKED"
        _apply_clause(refs, clause)
    return refs


# ---------------------------------------------------------------- WZDx

def _wzdx_type(raw: str) -> str | None:
    t = (raw or "").lower()
    if "shoulder" in t:
        return "shoulder"
    if "hov" in t:
        return "hov"
    if "express" in t or "reversible" in t:
        return "express"
    if "exit" in t:
        return "exit"
    if "entrance" in t or "aux" in t:
        return "aux"
    if t in ("general", "lane", "left-lane", "right-lane", "middle-lane",
             "center-lane", "through-lane", ""):
        return "general"
    return None  # ramps, sidewalks, bike lanes, parking, medians, turn lanes


def from_wzdx(lanes) -> dict | None:
    """WZDx ``lanes``: [{"order": 1, "status": "closed", "type": "general"}].
    ``order`` 1 is the leftmost lane, shoulders included, so a shoulder
    before the first travel lane is the left one."""
    if not isinstance(lanes, list) or not lanes:
        return None
    rows = []
    for ln in lanes:
        if not isinstance(ln, dict):
            continue
        try:
            order = int(ln.get("order"))
        except (TypeError, ValueError):
            continue
        kind = _wzdx_type(str(ln.get("type") or ""))
        if kind is None:
            continue
        status = str(ln.get("status") or "").lower()
        closed = status in ("closed", "merge-left", "merge-right", "blocked")
        raw_type = str(ln.get("type") or "").lower()
        rows.append((order, kind, closed, raw_type))
    rows.sort()
    travel = [r for r in rows if r[1] != "shoulder"]
    if not travel or len(travel) > MAX_LANES:
        return None
    first, last = travel[0][0], travel[-1][0]
    shoulders: dict[str, str] = {}
    for order, kind, closed, raw_type in rows:
        if kind != "shoulder":
            continue
        side = ("left" if "left" in raw_type else "right" if "right" in raw_type
                else "left" if order < first else "right" if order > last else None)
        if side:
            shoulders[side] = "closed" if closed else "open"
    types = {i + 1: r[1] for i, r in enumerate(travel)}
    closed_set = {i + 1 for i, r in enumerate(travel) if r[2]}
    if not closed_set and not any(v == "closed" for v in shoulders.values()):
        return None
    return build(len(travel), closed_set, types=types, shoulders=shoulders, basis="feed")


# ---------------------------------------------------------------- CDOT

def from_cdot(impacts) -> dict | None:
    """CDOT ``laneImpacts``: [{"direction", "laneCount", "laneClosures",
    "closedLaneTypes": ["Left Lane", "Right Shoulder", ...]}]. The
    first impact that closes something is used. Lane-type words place
    the closed lanes when they say left or right; otherwise the count
    is placed from the right (basis "count_only")."""
    for imp in impacts or []:
        if not isinstance(imp, dict):
            continue
        try:
            total = int(imp.get("laneCount") or 0)
            n_closed = int(str(imp.get("laneClosures") or "0"))
        except (TypeError, ValueError):
            continue
        words = [str(t).lower() for t in imp.get("closedLaneTypes") or []]
        if not total or (n_closed <= 0 and not words):
            continue
        refs = LaneRefs()
        placed = 0
        for w in words:
            if "shoulder" in w:
                refs.shoulders["left" if "left" in w else "right"] = "closed"
            elif "all" in w:
                refs.all_closed = True
            elif "left" in w:
                placed += 1
                refs.left.add(placed if not refs.left else max(refs.left) + 1)
            elif "right" in w:
                refs.right.add(len(refs.right) + 1)
                placed += 1
        if n_closed >= total:
            refs.all_closed = True
        elif n_closed > placed and not placed:
            refs.count = n_closed
        out = resolve(refs, total, basis="feed")
        if out:
            return out
    return None


# ---------------------------------------------------------------- NE Compass

def from_lane_details(details) -> dict | None:
    """NE Compass ``laneDetails``: [{"type": "MainLane"|"Shoulder"|
    "Divider", "status": "Blocked"|"Cleared"|"Unknown", "index": "0"}],
    indexed from the left. A divider splits the two directions; the
    side with blocked lanes is the one drawn."""
    rows = []
    for d in details or []:
        try:
            idx = int(d.get("index"))
        except (TypeError, ValueError, AttributeError):
            continue
        rows.append((idx, str(d.get("type") or "").lower(),
                     str(d.get("status") or "").lower()))
    rows.sort()
    groups: list[list[tuple]] = [[]]
    for row in rows:
        if row[1] == "divider":
            groups.append([])
        else:
            groups[-1].append(row)
    groups = [g for g in groups if any(r[1] == "mainlane" for r in g)]
    if not groups:
        return None
    pick = next((g for g in groups if any(r[2] in ("blocked", "closed") for r in g)), None)
    if pick is None:
        return None
    mains = [r for r in pick if r[1] == "mainlane"]
    if len(mains) > MAX_LANES:
        return None
    first, last = mains[0][0], mains[-1][0]
    shoulders: dict[str, str] = {}
    for idx, kind, status in pick:
        if kind == "shoulder" and status in ("blocked", "closed", "cleared", "open"):
            side = "left" if idx < first else "right" if idx > last else None
            if side:
                shoulders[side] = "closed" if status in ("blocked", "closed") else "open"
    closed = {i + 1 for i, r in enumerate(mains) if r[2] in ("blocked", "closed")}
    return build(len(mains), closed, shoulders=shoulders, basis="feed")
