"""One-command usage report from Cloud Logging.

Usage: python scripts/usage_report.py [days]   (default 7; needs gcloud auth)

Aggregates the structured telemetry events the demo emits: daily unique
visitors, questions asked (and what they were), tool usage, feedback, and
spend. No analytics service involved; the logs are the database.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter, defaultdict

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def fetch() -> list[dict]:
    cmd = [
        "gcloud", "logging", "read",
        'jsonPayload.log_type="ca_roads_event"',
        "--project", "ca-roads-mcp",
        f"--freshness={DAYS}d",
        "--format=json", "--limit=5000",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if out.returncode != 0:
        sys.exit(f"gcloud logging read failed: {out.stderr[:300]}")
    return json.loads(out.stdout or "[]")


def main() -> None:
    entries = fetch()
    events = []
    for e in entries:
        p = e.get("jsonPayload") or {}
        p["_day"] = e.get("timestamp", "")[:10]
        events.append(p)
    if not events:
        print("No telemetry events found in the window.")
        return

    by_day_visitors: dict[str, set] = defaultdict(set)
    by_day_questions = Counter()
    event_counts = Counter()
    tool_counts = Counter()
    questions = []
    cost = 0.0
    feedback = Counter()
    for p in events:
        event_counts[p.get("event")] += 1
        day = p["_day"]
        if p.get("visitor"):
            by_day_visitors[day].add(p["visitor"])
        if p.get("event") == "question":
            by_day_questions[day] += 1
            cost += p.get("est_cost_usd") or 0
            questions.append(p)
            for t in p.get("tools") or []:
                tool_counts[t.get("tool")] += 1
        if str(p.get("event", "")).startswith("feedback"):
            feedback[p["event"]] += 1

    print(f"=== CA Roads usage, last {DAYS} day(s) ===\n")
    print("Day         Uniques  Questions")
    for day in sorted(by_day_visitors):
        print(f"{day}  {len(by_day_visitors[day]):7}  {by_day_questions[day]:9}")
    print(f"\nEvents: {dict(event_counts)}")
    print(f"Tool calls: {dict(tool_counts.most_common())}")
    up, down = feedback.get("feedback_up", 0), feedback.get("feedback_down", 0)
    if up or down:
        print(f"Feedback: {up} up / {down} down")
    print(f"Model spend (est): ${cost:.2f}")

    print(f"\nLast {min(len(questions), 15)} questions:")
    for q in questions[:15]:
        tools = ",".join(t.get("tool", "?") for t in q.get("tools") or [])
        mark = "" if q.get("completed", True) else " [capped]"
        print(f"  [{q['_day']}] {q.get('question', '')[:70]}  "
              f"({tools or 'no tools'}, {q.get('duration_ms', 0)}ms){mark}")


if __name__ == "__main__":
    main()
