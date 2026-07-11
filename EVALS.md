# Eval results

Generated 2026-07-11T01:46:14+00:00 by `evals/run_evals.py` from `v2.5.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 12/28 (43%) | 19/28 (68%) |
| quiet-day | 20/30 (67%) | 20/30 (67%) |
| real-2026-07-07 | 3/6 (50%) | 3/6 (50%) |
| storm-day | 17/27 (63%) | 16/27 (59%) |
| **all** | 52/91 (57%) | 58/91 (64%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 1/4 (25%) | 3/4 (75%) |
| `check_route` | 13/18 (72%) | 11/18 (61%) |
| `get_chain_controls` | 14/20 (70%) | 14/20 (70%) |
| `get_incidents` | 10/15 (67%) | 9/15 (60%) |
| `get_lane_closures` | 7/19 (37%) | 8/19 (42%) |
| `get_wildfires` | 7/15 (47%) | 13/15 (87%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 29 | claude-haiku-4-5 / fire-i5-why: Fails to mention the VULCAN fire as the cause and incorrectly states only southbound is closed... |
| hallucinated-event | 27 | claude-haiku-4-5 / fire-when-reopen: The assistant claims the road is open, contradicting the ground truth that there is an indefinite... |
| other | 7 | claude-haiku-4-5 / real-bay-area: Reports 13 closures instead of the correct 37 lane closures (4 ramp), contradicting the ground... |
| bad-refusal | 4 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for start/end points instead of reporting the known SR-99 lane closure at 7th... |
| wrong-tool-or-no-tool | 2 | claude-haiku-4-5 / fire-vulcan-size: The assistant failed to retrieve the fire data and did not provide the size or containment. |
| wrong-location | 2 | claude-haiku-4-5 / fire-freshness: Identifies VULCAN fire and provides data timestamp, but places it in the LA area rather than the... |
| stale-data-trust | 1 | claude-haiku-4-5 / quiet-place-davis: It claims no lane closures but the closure feed was down, missing the shoulder-only I-80 record and... |

## Tool selection

23/174 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.90**
