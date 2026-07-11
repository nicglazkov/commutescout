# Eval results

Generated 2026-07-11T18:30:29+00:00 by `evals/run_evals.py` from `v2.8.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 12/28 (43%) | 20/28 (71%) |
| quiet-day | 21/30 (70%) | 20/30 (67%) |
| real-2026-07-07 | 1/6 (17%) | 3/6 (50%) |
| storm-day | 15/27 (56%) | 17/27 (63%) |
| **all** | 49/91 (54%) | 60/91 (66%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 1/4 (25%) | 3/4 (75%) |
| `check_route` | 8/18 (44%) | 12/18 (67%) |
| `get_chain_controls` | 15/20 (75%) | 17/20 (85%) |
| `get_incidents` | 9/15 (60%) | 9/15 (60%) |
| `get_lane_closures` | 9/19 (47%) | 8/19 (42%) |
| `get_wildfires` | 7/15 (47%) | 11/15 (73%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 35 | claude-haiku-4-5 / fire-i5-why: Fails to mention the VULCAN fire cause and only cites southbound closure, missing the full... |
| hallucinated-event | 27 | claude-haiku-4-5 / fire-i5-open: Invents a VULCAN wildfire cause and misstates the southbound closure location as Fort Tejon rather... |
| other | 5 | claude-haiku-4-5 / fire-route-la-sac: Correctly identifies I-5 Grapevine closure and VULCAN fire but says only northbound (ground truth:... |
| bad-refusal | 2 | claude-haiku-4-5 / fire-99-alternative: The assistant refused to answer and asked for more info instead of reporting the SR-99 closure at... |
| stale-data-trust | 2 | claude-haiku-4-5 / quiet-i80-closures: It claims the feed is unavailable and hedges, failing to convey the correct 'no lane closures'... |
| wrong-location | 2 | claude-haiku-4-5 / real-bay-area: States 13 lane/ramp closures instead of 37 lane closures (4 ramp), understating the actual closure... |

## Tool selection

26/177 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.83**
