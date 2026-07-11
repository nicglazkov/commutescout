# Eval results

Generated 2026-07-11T22:02:42+00:00 by `evals/run_evals.py` from `v2.9.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 14/28 (50%) | 20/28 (71%) |
| quiet-day | 22/30 (73%) | 19/30 (63%) |
| real-2026-07-07 | 1/6 (17%) | 3/6 (50%) |
| storm-day | 16/27 (59%) | 17/27 (63%) |
| **all** | 53/91 (58%) | 59/91 (65%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 1/4 (25%) |
| `check_route` | 9/18 (50%) | 10/18 (56%) |
| `get_chain_controls` | 15/20 (75%) | 14/20 (70%) |
| `get_incidents` | 11/15 (73%) | 10/15 (67%) |
| `get_lane_closures` | 9/19 (47%) | 10/19 (53%) |
| `get_wildfires` | 7/15 (47%) | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 31 | claude-haiku-4-5 / fire-i5-open: Incorrectly claims southbound is open when it is closed at Frazier Mountain Park Rd, missing half... |
| hallucinated-event | 23 | claude-haiku-4-5 / fire-when-reopen: The assistant claims the road is open with no closure, contradicting the actual indefinite closure. |
| other | 10 | claude-haiku-4-5 / real-fires-near-i5: Reports the correct count of active fires but fails to name any specific fire like BIG or WILDWOOD... |
| bad-refusal | 2 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for clarification instead of reporting the SR-99 lane closure at 7th Standard... |
| wrong-location | 2 | claude-haiku-4-5 / fire-freshness: VULCAN fire is near the Grapevine stretch, not the Los Angeles area as stated. |
| stale-data-trust | 1 | claude-haiku-4-5 / quiet-place-davis: Claims Caltrans closure feed unavailable and can't confirm construction, but ground truth shows the... |
| wrong-tool-or-no-tool | 1 | claude-sonnet-5 / storm-placerville-not-established: Claims data outage and refuses to answer, failing to convey that the closure is scheduled but not... |

## Tool selection

25/177 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.91**
