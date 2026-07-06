"""Salvaging XML record iteration.

The CHP feed is truncated mid-record by its server when statewide incident
volume is high, and the Caltrans CWWP feeds occasionally ship malformed bytes.
A strict parse would drop every record exactly when the roads are busiest, so
parsing salvages every complete record seen before the first error instead of
failing the whole document.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET


def iter_complete_records(data: bytes, record_tag: str) -> tuple[list[ET.Element], bool]:
    """Parse ``data`` and return (complete <record_tag> elements, truncated).

    ``truncated`` is True when the document was cut off or malformed and only
    the records completed before the error were salvaged.
    """
    parser = ET.XMLPullParser(events=("end",))
    records: list[ET.Element] = []
    truncated = False
    try:
        parser.feed(data)
        for _, elem in parser.read_events():
            if elem.tag == record_tag:
                records.append(elem)
        parser.close()
    except ET.ParseError:
        truncated = True
        # Collect any records that completed before the error.
        for _, elem in parser.read_events():
            if elem.tag == record_tag:
                records.append(elem)
    return records, truncated


def child_text(elem: ET.Element, tag: str) -> str:
    """Text of the first descendant named ``tag`` anywhere under ``elem``.

    The CWWP schemas nest fields in sections but keep tag names globally unique
    within a record (beginLatitude vs endLatitude, ...), so a subtree search is
    unambiguous and immune to section reshuffles.
    """
    node = elem.find(f".//{tag}")
    if node is None or node.text is None:
        return ""
    return node.text.strip()
