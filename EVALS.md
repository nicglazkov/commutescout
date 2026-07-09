# Eval results

Generated 2026-07-09T11:42:50+00:00 by `evals/run_evals.py` from `v1.5.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 15/28 (54%) | 21/28 (75%) |
| quiet-day | 20/30 (67%) | 21/30 (70%) |
| real-2026-07-07 | 2/6 (33%) | 5/6 (83%) |
| storm-day | 18/27 (67%) | 15/27 (56%) |
| **all** | 55/91 (60%) | 62/91 (68%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 1/4 (25%) |
| `check_route` | 13/18 (72%) | 12/18 (67%) |
| `get_chain_controls` | 15/20 (75%) | 16/20 (80%) |
| `get_incidents` | 11/15 (73%) | 10/15 (67%) |
| `get_lane_closures` | 7/19 (37%) | 10/19 (53%) |
| `get_wildfires` | 7/15 (47%) | 13/15 (87%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 29 | claude-haiku-4-5 / fire-i5-open: Presents closure as northbound-only when both directions are fully closed, and adds an unsupported... |
| hallucinated-event | 24 | claude-haiku-4-5 / quiet-closures-district4: Invented two additional closures (SR-84 La Honda and US-101 Story Rd ramp) not in the ground truth. |
| other | 6 | claude-haiku-4-5 / quiet-fires-statewide: judge output unparseable |
| wrong-tool-or-no-tool | 3 | claude-haiku-4-5 / fire-all-fires: The assistant refused to list the fires and deferred to external sources instead of reporting the... |
| bad-refusal | 2 | claude-haiku-4-5 / fire-sr17: Assistant asked for clarification instead of stating that SR-17 is clear. |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-place-davis: Correctly reports no incidents/closures but claims LCS feed is down when ground truth shows a... |

## Tool selection

27/173 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **4.05**
