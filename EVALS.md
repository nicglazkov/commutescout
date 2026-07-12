# Eval results

Generated 2026-07-12T11:23:50+00:00 by `evals/run_evals.py` from `v2.18.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 23/28 (82%) |
| quiet-day | 23/30 (77%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 16/27 (59%) |
| **all** | 64/91 (70%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 12/18 (67%) |
| `get_chain_controls` | 14/20 (70%) |
| `get_incidents` | 12/15 (80%) |
| `get_lane_closures` | 10/19 (53%) |
| `get_wildfires` | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 15 | claude-sonnet-5 / fire-i5-open: The answer invents a specific 'Vulcan fire' with precise acreage and containment figures not in the... |
| missed-active-condition | 7 | claude-sonnet-5 / fire-route-sac-la-99: The answer omits the collision at Ming Ave, which is an active condition mentioned in the ground... |
| bad-refusal | 3 | claude-sonnet-5 / fire-99-alternative: The assistant refused to answer and asked for clarification instead of reporting the known SR-99... |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-place-davis: The answer correctly notes no CHP incidents but wrongly claims it cannot check lane closures due to... |
| wrong-location | 1 | claude-sonnet-5 / storm-kirkwood:  |

## Tool selection

12/90 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.62**
