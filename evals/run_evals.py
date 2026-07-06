"""Eval harness: run Claude against the tools in fixture mode and grade it.

Usage:
    python evals/run_evals.py                       # full run, writes EVALS.md
    python evals/run_evals.py --limit 3             # smoke test
    python evals/run_evals.py --models claude-haiku-4-5

For every golden question, the model runs the same tool loop the demo uses,
but RoadData is served from the scenario's recorded fixtures instead of the
live feeds. Grading is two-layer:
- exact facts: case-insensitive substring checks from the golden YAML
  (contains / contains_any / not_contains);
- an LLM judge scores correctness against the ground-truth note, rates
  answer quality 1-5, and assigns a failure category.

A question passes when the facts pass AND the judge says correct.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import anthropic
import yaml

from ca_roads_demo.app import SYSTEM, TOOL_DEFS, TOOL_FUNCS
from ca_roads_mcp import server as tool_server
from evals.fixture_mode import fixture_road_data

GOLDEN_DIR = Path(__file__).parent / "golden"
RESULTS_DIR = Path(__file__).parent / "results"

DEFAULT_MODELS = ["claude-haiku-4-5", "claude-sonnet-5"]
JUDGE_MODEL = "claude-sonnet-5"
MAX_TOOL_TURNS = 6
CONCURRENCY = 4

FAILURE_CATEGORIES = [
    "missed-active-condition",  # e.g. missed an active chain control
    "hallucinated-event",  # invented a closure/incident the tools never returned
    "stale-data-trust",  # presented data as live/forecast without caveats
    "wrong-location",  # right kind of event, wrong place/district/route
    "wrong-tool-or-no-tool",  # answered from priors instead of the right tool
    "bad-refusal",  # refused or hedged when the data clearly answers
    "other",
]

JUDGE_PROMPT = """\
You are grading an AI road-conditions assistant. Compare its answer to the
ground truth and output ONLY a JSON object, no other text.

Question: {question}

Ground truth (what a correct answer must convey): {ground_truth}

Assistant's answer:
<answer>
{answer}
</answer>

Output exactly this JSON shape:
{{"correct": true/false, "quality": 1-5,
  "failure_category": <category or "none">, "note": "<one short sentence>"}}

- "correct": does the answer convey the ground truth without contradicting it
  or inventing conditions? Extra accurate detail is fine.
- "quality": 5 = clear, complete, driver-useful; 1 = wrong or useless.
- "failure_category": "none" if correct; otherwise one of {categories}.
"""


def load_golden() -> list[dict]:
    questions = []
    for path in sorted(GOLDEN_DIR.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        for q in doc["questions"]:
            q["scenario"] = doc["scenario"]
            questions.append(q)
    return questions


def check_facts(answer: str, expect: dict | None) -> tuple[bool, list[str]]:
    if not expect:
        return True, []
    lowered = answer.lower()
    failures = []
    for needle in expect.get("contains", []):
        if needle.lower() not in lowered:
            failures.append(f"missing required fact: {needle!r}")
    for group in expect.get("contains_any", []):
        if not any(n.lower() in lowered for n in group):
            failures.append(f"missing all of: {group!r}")
    for needle in expect.get("not_contains", []):
        if needle.lower() in lowered:
            failures.append(f"contains forbidden text: {needle!r}")
    return not failures, failures


async def answer_question(
    client: anthropic.AsyncAnthropic, model: str, question: str
) -> tuple[str, list[str]]:
    """Run the tool loop; returns (final text, tool names called)."""
    messages = [{"role": "user", "content": question}]
    tools_called: list[str] = []
    text_parts: list[str] = []
    for _ in range(MAX_TOOL_TURNS):
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM,
            tools=TOOL_DEFS,
            messages=messages,
        )
        text_parts.extend(b.text for b in response.content if b.type == "text")
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            tools_called.append(block.name)
            func = TOOL_FUNCS.get(block.name)
            try:
                result = await func(**block.input) if func else {"error": "unknown tool"}
                content = json.dumps(result, default=str)
                is_error = False
            except Exception as exc:  # noqa: BLE001
                content = f"tool failed: {type(exc).__name__}: {exc}"
                is_error = True
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": results})
    return "\n".join(t for t in text_parts if t.strip()), tools_called


async def judge(
    client: anthropic.AsyncAnthropic, question: dict, answer: str
) -> dict:
    prompt = JUDGE_PROMPT.format(
        question=question["question"],
        ground_truth=question["ground_truth"],
        answer=answer or "(no answer produced)",
        categories=FAILURE_CATEGORIES,
    )
    for _ in range(2):  # one retry on unparseable judge output
        response = await client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                verdict = json.loads(match.group(0))
                verdict.setdefault("failure_category", "none")
                return verdict
            except json.JSONDecodeError:
                pass
    return {"correct": False, "quality": 1,
            "failure_category": "other", "note": "judge output unparseable"}


async def run_model(
    client: anthropic.AsyncAnthropic,
    model: str,
    questions: list[dict],
) -> list[dict]:
    semaphore = asyncio.Semaphore(CONCURRENCY)
    results = []

    async def run_one(q: dict) -> dict:
        async with semaphore:
            try:
                answer, tools_called = await answer_question(
                    client, model, q["question"]
                )
            except anthropic.APIError as exc:
                return {
                    "id": q["id"], "scenario": q["scenario"], "tool": q["tool"],
                    "model": model, "passed": False, "error": str(exc),
                    "failure_category": "other",
                }
            facts_ok, fact_failures = check_facts(answer, q.get("expect"))
            verdict = await judge(client, q, answer)
            passed = facts_ok and bool(verdict.get("correct"))
            category = "none" if passed else (
                verdict.get("failure_category") or "other"
            )
            if passed:
                category = "none"
            elif category == "none":
                # facts failed but judge said correct - classify by fact type
                category = (
                    "hallucinated-event"
                    if any("forbidden" in f for f in fact_failures)
                    else "missed-active-condition"
                )
            return {
                "id": q["id"], "scenario": q["scenario"], "tool": q["tool"],
                "model": model, "passed": passed,
                "facts_ok": facts_ok, "fact_failures": fact_failures,
                "judge_correct": bool(verdict.get("correct")),
                "quality": verdict.get("quality"),
                "failure_category": category,
                "judge_note": verdict.get("note", ""),
                "tools_called": tools_called,
                "answer": answer,
            }

    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        by_scenario[q["scenario"]].append(q)

    for scenario, scenario_questions in by_scenario.items():
        # Point the shared tool layer at this scenario's fixtures.
        old = tool_server._road
        tool_server._road = fixture_road_data(scenario)
        try:
            results.extend(
                await asyncio.gather(*(run_one(q) for q in scenario_questions))
            )
        finally:
            await tool_server._road.aclose()
            tool_server._road = old
        done = len(results)
        print(f"  {model}: {scenario} done ({done}/{len(questions)})")
    return results


def rate(results: list[dict]) -> str:
    if not results:
        return "-"
    passed = sum(1 for r in results if r["passed"])
    return f"{passed}/{len(results)} ({100 * passed / len(results):.0f}%)"


def write_report(all_results: list[dict], models: list[str], path: Path) -> None:
    scenarios = sorted({r["scenario"] for r in all_results})
    tools = sorted({r["tool"] for r in all_results})
    lines = [
        "# Eval results",
        "",
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} by "
        "`evals/run_evals.py`. Models answer the golden questions using the "
        "MCP tool surface served from recorded fixtures; grading is exact-fact "
        "matching plus an LLM judge scored against ground truth. "
        f"Judge: `{JUDGE_MODEL}`.",
        "",
        "## Scorecard",
        "",
        "| Scenario | " + " | ".join(f"`{m}`" for m in models) + " |",
        "|---|" + "---|" * len(models),
    ]
    for scenario in scenarios:
        row = [scenario]
        for model in models:
            row.append(rate([
                r for r in all_results
                if r["scenario"] == scenario and r["model"] == model
            ]))
        lines.append("| " + " | ".join(row) + " |")
    total_row = ["**all**"]
    for model in models:
        total_row.append(rate([r for r in all_results if r["model"] == model]))
    lines.append("| " + " | ".join(total_row) + " |")

    lines += ["", "## Pass rate by tool", "",
              "| Tool | " + " | ".join(f"`{m}`" for m in models) + " |",
              "|---|" + "---|" * len(models)]
    for tool in tools:
        row = [f"`{tool}`"]
        for model in models:
            row.append(rate([
                r for r in all_results
                if r["tool"] == tool and r["model"] == model
            ]))
        lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## Failure taxonomy", ""]
    failures = [r for r in all_results if not r["passed"]]
    if not failures:
        lines.append("No failures.")
    else:
        lines += ["| Category | Count | Example |", "|---|---|---|"]
        by_category = defaultdict(list)
        for r in failures:
            by_category[r["failure_category"]].append(r)
        for category, rs in sorted(
            by_category.items(), key=lambda kv: -len(kv[1])
        ):
            example = rs[0]
            note = (example.get("judge_note") or "").replace("|", "/")[:100]
            lines.append(
                f"| {category} | {len(rs)} | {example['model']} / "
                f"{example['id']}: {note} |"
            )

    qualities = [r["quality"] for r in all_results if r.get("quality")]
    if qualities:
        lines += ["", f"Mean answer quality (judge, 1-5): "
                      f"**{sum(qualities) / len(qualities):.2f}**"]
    lines.append("")
    path.write_text("\n".join(lines))
    print(f"wrote {path}")


def write_badge(all_results: list[dict], path: Path) -> None:
    """Write both badge forms: shields endpoint JSON, and a rendered SVG the
    README embeds by relative path (works while the repo is private, where
    shields cannot read raw.githubusercontent.com)."""
    passed = sum(1 for r in all_results if r["passed"])
    total = len(all_results)
    pct = 100 * passed / total if total else 0
    color = "#4c1" if pct >= 90 else "#dfb317" if pct >= 75 else "#e05d44"
    message = f"{passed}/{total} pass"
    path.write_text(json.dumps({
        "schemaVersion": 1, "label": "evals", "message": message,
        "color": "brightgreen" if pct >= 90 else "yellow" if pct >= 75 else "red",
    }))
    label = "evals"
    char_w = 6.2
    label_w = round(len(label) * char_w + 12)
    msg_w = round(len(message) * char_w + 12)
    total_w = label_w + msg_w
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" role="img" aria-label="{label}: {message}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_w}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{msg_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{label_w / 2}" y="14">{label}</text>
    <text x="{label_w + msg_w / 2}" y="14">{message}</text>
  </g>
</svg>
"""
    path.with_suffix(".svg").write_text(svg)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--limit", type=int, help="questions per scenario")
    parser.add_argument("--report", default="EVALS.md")
    args = parser.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    questions = load_golden()
    if args.limit:
        trimmed, seen = [], Counter()
        for q in questions:
            if seen[q["scenario"]] < args.limit:
                trimmed.append(q)
                seen[q["scenario"]] += 1
        questions = trimmed
    print(f"{len(questions)} questions x {len(models)} models")

    client = anthropic.AsyncAnthropic()
    all_results = []
    for model in models:
        print(f"running {model}...")
        all_results.extend(await run_model(client, model, questions))

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    raw_path = RESULTS_DIR / f"results-{stamp}.json"
    raw_path.write_text(json.dumps(all_results, indent=1))
    print(f"wrote {raw_path}")

    write_report(all_results, models, Path(args.report))
    write_badge(all_results, RESULTS_DIR / "badge.json")
    for model in models:
        print(model, rate([r for r in all_results if r["model"] == model]))


if __name__ == "__main__":
    asyncio.run(main())
