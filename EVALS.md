# Eval results

Generated 2026-07-11T09:50:19+00:00 by `evals/run_evals.py` from `v2.6.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 16/28 (57%) | 22/28 (79%) |
| quiet-day | 21/30 (70%) | 20/30 (67%) |
| real-2026-07-07 | 2/6 (33%) | 3/6 (50%) |
| storm-day | 17/27 (63%) | 16/27 (59%) |
| **all** | 56/91 (62%) | 61/91 (67%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 2/4 (50%) |
| `check_route` | 14/18 (78%) | 10/18 (56%) |
| `get_chain_controls` | 14/20 (70%) | 15/20 (75%) |
| `get_incidents` | 11/15 (73%) | 10/15 (67%) |
| `get_lane_closures` | 5/19 (26%) | 12/19 (63%) |
| `get_wildfires` | 10/15 (67%) | 12/15 (80%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 26 | claude-haiku-4-5 / fire-i5-open: Correctly identifies the closure locations but fabricates a specific 'Vulcan wildfire' cause and... |
| missed-active-condition | 23 | claude-haiku-4-5 / fire-i5-why: Assistant claims I-5 is not closed, contradicting the active VULCAN fire closure. |
| other | 9 | claude-haiku-4-5 / storm-chains-r2-meaning: Incorrectly claims R-2 requires chains on all vehicles with no exceptions, missing that 4WD/AWD... |
| bad-refusal | 5 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for clarification instead of reporting the SR-99 lane closure at 7th Standard... |
| stale-data-trust | 1 | claude-haiku-4-5 / quiet-place-davis: Claims clear but admits lane closure feed unavailable, whereas ground truth shows a shoulder-only... |
| wrong-location | 1 | claude-sonnet-5 / storm-route-sac-reno: Ground truth events are at Baxter but the assistant labels them 'Alta,' and it collapses the Donner... |

## Tool selection

23/175 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.91**
