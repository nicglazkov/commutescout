"""Detect new Claude models so the demo/eval model choice gets re-reviewed.

Compares the live Models API against the checked-in snapshot. When new model
IDs appear, prints them (one per line, prefixed NEW:) and rewrites the
snapshot. The model-watch workflow turns that output into a GitHub issue -
the review itself stays a human decision.

Usage: python scripts/check_models.py  (needs ANTHROPIC_API_KEY)
Exit codes: 0 = no change, 3 = new models found.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anthropic

SNAPSHOT = Path(__file__).parent / "known_models.json"


def main() -> int:
    client = anthropic.Anthropic()
    live = sorted(m.id for m in client.models.list())
    known = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else []
    new = [m for m in live if m not in known]
    retired = [m for m in known if m not in live]
    if not new and not retired:
        print("no model catalog changes")
        return 0
    for model in new:
        print(f"NEW: {model}")
    for model in retired:
        print(f"RETIRED: {model}")
    SNAPSHOT.write_text(json.dumps(live, indent=1) + "\n")
    return 3 if new else 0


if __name__ == "__main__":
    sys.exit(main())
