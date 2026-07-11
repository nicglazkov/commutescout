# Eval results

Generated 2026-07-11T00:28:06+00:00 by `evals/run_evals.py` from `v2.3.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 19/28 (68%) | 21/28 (75%) |
| quiet-day | 21/30 (70%) | 19/30 (63%) |
| real-2026-07-07 | 3/6 (50%) | 3/6 (50%) |
| storm-day | 16/27 (59%) | 18/27 (67%) |
| **all** | 59/91 (65%) | 61/91 (67%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 2/4 (50%) |
| `check_route` | 12/18 (67%) | 11/18 (61%) |
| `get_chain_controls` | 15/20 (75%) | 16/20 (80%) |
| `get_incidents` | 10/15 (67%) | 10/15 (67%) |
| `get_lane_closures` | 9/19 (47%) | 10/19 (53%) |
| `get_wildfires` | 11/15 (73%) | 12/15 (80%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 33 | claude-haiku-4-5 / fire-i5-open: Claims southbound is passable when it is actually fully closed, and invents a wildfire cause... |
| hallucinated-event | 19 | claude-haiku-4-5 / fire-alt-check: Correctly identifies I-5 Grapevine closure but invents a specific wildfire, acreage, and detours... |
| other | 6 | claude-haiku-4-5 / storm-chains-r2-meaning: States chains required for sedan but wrongly claims winter tires don't exempt any vehicle, missing... |
| stale-data-trust | 2 | claude-haiku-4-5 / quiet-i80-closures: Claims data feed unavailable and defers to external sources, failing to convey the shoulder-only... |
| bad-refusal | 2 | claude-sonnet-5 / quiet-i80-closures: Claimed the feed was down and refused to answer, when data showing only shoulder litter removal was... |

## Tool selection

28/177 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **4.03**
