# Eval results

Generated 2026-07-09T22:07:36+00:00 by `evals/run_evals.py` from `v1.6.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 16/28 (57%) | 23/28 (82%) |
| quiet-day | 20/30 (67%) | 18/30 (60%) |
| real-2026-07-07 | 2/6 (33%) | 3/6 (50%) |
| storm-day | 17/27 (63%) | 20/27 (74%) |
| **all** | 55/91 (60%) | 64/91 (70%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 2/4 (50%) |
| `check_route` | 13/18 (72%) | 12/18 (67%) |
| `get_chain_controls` | 15/20 (75%) | 17/20 (85%) |
| `get_incidents` | 10/15 (67%) | 11/15 (73%) |
| `get_lane_closures` | 7/19 (37%) | 10/19 (53%) |
| `get_wildfires` | 8/15 (53%) | 12/15 (80%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 31 | claude-haiku-4-5 / fire-i5-open: Claims southbound is open, but ground truth says both directions are closed. |
| hallucinated-event | 20 | claude-haiku-4-5 / quiet-101-closures: Correctly reports the Trimble Rd closure but invents an additional Story Rd on-ramp closure not in... |
| bad-refusal | 5 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for clarification instead of reporting the SR-99 lane closure at 7th Standard... |
| other | 4 | claude-sonnet-5 / fire-sr17: judge output unparseable |
| stale-data-trust | 2 | claude-haiku-4-5 / quiet-place-davis: It claims a lane closure feed connectivity issue rather than reporting the shoulder-only litter... |
| wrong-location | 1 | claude-haiku-4-5 / storm-lowest-elevation-control: Answer cites Echo Summit as typical chain control start, not R-1 Pollock Pines and R-2 Twin Bridges... |

## Tool selection

22/173 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **4.01**
