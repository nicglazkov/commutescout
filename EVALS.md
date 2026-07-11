# Eval results

Generated 2026-07-11T10:00:01+00:00 by `evals/run_evals.py` from `v2.7.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 16/28 (57%) | 24/28 (86%) |
| quiet-day | 20/30 (67%) | 22/30 (73%) |
| real-2026-07-07 | 2/6 (33%) | 4/6 (67%) |
| storm-day | 17/27 (63%) | 18/27 (67%) |
| **all** | 55/91 (60%) | 68/91 (75%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 1/4 (25%) | 3/4 (75%) |
| `check_route` | 14/18 (78%) | 12/18 (67%) |
| `get_chain_controls` | 15/20 (75%) | 16/20 (80%) |
| `get_incidents` | 9/15 (60%) | 11/15 (73%) |
| `get_lane_closures` | 8/19 (42%) | 11/19 (58%) |
| `get_wildfires` | 8/15 (53%) | 15/15 (100%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 30 | claude-haiku-4-5 / fire-i5-open: Claims I-5 is passable southbound from LA, but ground truth says it's fully closed in both... |
| hallucinated-event | 18 | claude-haiku-4-5 / quiet-101-closures: Invented a second closure (northbound on-ramp at Story Rd) not in the ground truth. |
| other | 6 | claude-haiku-4-5 / fire-route-la-sac: Says only northbound closed (ground truth: both directions) and recommends US-395 detour instead of... |
| bad-refusal | 3 | claude-haiku-4-5 / fire-sr17: The assistant asked for a starting location instead of stating that SR-17 is unaffected. |
| stale-data-trust | 2 | claude-haiku-4-5 / quiet-place-davis: Claims the lane closure feed is unavailable when ground truth shows a shoulder-only closure record... |

## Tool selection

27/176 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **4.05**
