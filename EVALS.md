# Eval results

Generated 2026-07-09T11:02:12+00:00 by `evals/run_evals.py` from `v1.3.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 16/28 (57%) | 21/28 (75%) |
| quiet-day | 20/30 (67%) | 19/30 (63%) |
| real-2026-07-07 | 2/6 (33%) | 5/6 (83%) |
| storm-day | 15/27 (56%) | 21/27 (78%) |
| **all** | 53/91 (58%) | 66/91 (73%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 1/4 (25%) | 1/4 (25%) |
| `check_route` | 13/18 (72%) | 13/18 (72%) |
| `get_chain_controls` | 15/20 (75%) | 17/20 (85%) |
| `get_incidents` | 9/15 (60%) | 11/15 (73%) |
| `get_lane_closures` | 9/19 (47%) | 9/19 (47%) |
| `get_wildfires` | 6/15 (40%) | 15/15 (100%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 30 | claude-haiku-4-5 / fire-i5-why: The assistant claims no closure exists when the VULCAN fire has fully closed I-5 in both directions. |
| hallucinated-event | 19 | claude-haiku-4-5 / fire-incidents-grapevine: Invented a full both-directions emergency closure not in the ground truth, which only reports a... |
| other | 8 | claude-haiku-4-5 / fire-route-la-sac: Says only northbound closed rather than both directions, and calls the alternate 'I-99' instead of... |
| bad-refusal | 4 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for clarification instead of reporting the known SR-99 lane closure at 7th... |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-place-davis: Claims closure feed errored statewide and result is uncertain, but ground truth shows a valid... |
| wrong-tool-or-no-tool | 1 | claude-sonnet-5 / storm-placerville-not-established: Claims a statewide feed outage and refuses to answer, when ground truth shows no active closure is... |

## Tool selection

24/173 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.93**
