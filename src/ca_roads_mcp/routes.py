"""Route-name normalization and matching.

Caltrans feeds spell routes "I-80" / "US-50" / "SR-89". Users (and CHP
location strings) write "80", "hwy 50", "I80 E", "Highway 17", "CA-1", ...
Everything is normalized to the Caltrans spelling.
"""

from __future__ import annotations

import re

# Numbers that are interstates or US routes in California; everything else
# defaults to a state route.
_INTERSTATES = {5, 8, 10, 15, 40, 80, 105, 110, 205, 210, 215, 238, 280, 380,
                405, 505, 580, 605, 680, 705, 710, 780, 805, 880, 905, 980}
_US_ROUTES = {6, 50, 95, 97, 101, 199, 395}

_ROUTE_RE = re.compile(
    r"^\s*(?:(i|interstate|us|u\.s\.|sr|ca|state\s+route|route|rt|rte|hwy|highway)"
    r"[\s.-]*)?(\d{1,3})\s*$",
    re.IGNORECASE,
)


def normalize_route(raw: str | None) -> str | None:
    """'17', 'hwy 50', 'I80', 'CA-1' -> 'SR-17', 'US-50', 'I-80', 'SR-1'.

    Returns None when the input doesn't look like a route designation.
    """
    if not raw:
        return None
    m = _ROUTE_RE.match(raw)
    if not m:
        return None
    prefix = (m.group(1) or "").lower().rstrip(".")
    number = int(m.group(2))
    if prefix in ("i", "interstate"):
        kind = "I"
    elif prefix in ("us", "u.s"):
        kind = "US"
    elif prefix in ("sr", "ca", "state route"):
        kind = "SR"
    elif number in _INTERSTATES:
        kind = "I"
    elif number in _US_ROUTES:
        kind = "US"
    else:
        kind = "SR"
    return f"{kind}-{number}"


# Route mentions inside CHP location strings: "I80 E", "US50", "Sr17",
# "Hwy 4", "SB 101" style prefixes on plain numbers are NOT matched (too
# ambiguous); explicit class prefixes are.
_MENTION_RE = re.compile(
    r"\b(I|US|SR|CA|HWY|RT|RTE)\s*-?\s*(\d{1,3})\b", re.IGNORECASE
)


def routes_mentioned(text: str) -> set[str]:
    """Canonical routes explicitly mentioned in a free-text location string."""
    out = set()
    for m in _MENTION_RE.finditer(text or ""):
        prefix = m.group(1).lower()
        number = int(m.group(2))
        if prefix == "i":
            out.add(f"I-{number}")
        elif prefix == "us":
            out.add(f"US-{number}")
        elif prefix in ("sr", "ca"):
            out.add(f"SR-{number}")
        else:  # hwy / rt / rte — class unknown, infer from number
            normalized = normalize_route(str(number))
            if normalized:
                out.add(normalized)
    return out


def matches_route(text: str, canonical: str) -> bool:
    """True when a free-text location string mentions the given route."""
    return canonical in routes_mentioned(text)
