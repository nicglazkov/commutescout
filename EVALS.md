# Eval results

Generated 2026-07-10T00:08:25+00:00 by `evals/run_evals.py` from `v1.9.2`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 15/28 (54%) | 22/28 (79%) |
| quiet-day | 18/30 (60%) | 19/30 (63%) |
| real-2026-07-07 | 2/6 (33%) | 3/6 (50%) |
| storm-day | 16/27 (59%) | 18/27 (67%) |
| **all** | 51/91 (56%) | 62/91 (68%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 2/4 (50%) |
| `check_route` | 11/18 (61%) | 10/18 (56%) |
| `get_chain_controls` | 15/20 (75%) | 16/20 (80%) |
| `get_incidents` | 8/15 (53%) | 10/15 (67%) |
| `get_lane_closures` | 7/19 (37%) | 11/19 (58%) |
| `get_wildfires` | 8/15 (53%) | 13/15 (87%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 28 | claude-haiku-4-5 / fire-i5-why: The assistant claims I-5 is not closed, contradicting the active VULCAN fire closure in the ground... |
| hallucinated-event | 24 | claude-haiku-4-5 / fire-i5-open: Invents specific wildfire details (VULCAN, acreage, containment) not in ground truth, though it... |
| other | 10 | claude-haiku-4-5 / fire-route-la-sac: Correctly identifies the I-5 Grapevine closure and VULCAN fire but calls the alternate 'I-99'... |
| bad-refusal | 3 | claude-haiku-4-5 / fire-sr17: The assistant asked for clarification instead of reporting that Highway 17 has no incidents or... |
| wrong-tool-or-no-tool | 2 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for origin/destination instead of reporting the SR-99 closure at 7th Standard... |
| wrong-location | 1 | claude-haiku-4-5 / quiet-route-sac-tahoe: US-50 through Sierra/Tahoe is District 3, not District 10, and the answer missed the scheduled Watt... |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-place-davis: It reports the closure feed as down and can't confirm closures, but the ground truth shows the feed... |

## Tool selection

24/174 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.97**
