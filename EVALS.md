# Eval results

Generated 2026-07-16T10:10:00+00:00 by `evals/run_evals.py` from `v2.21.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 23/28 (82%) |
| quiet-day | 20/30 (67%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 19/27 (70%) |
| **all** | 64/91 (70%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 10/18 (56%) |
| `get_chain_controls` | 17/20 (85%) |
| `get_incidents` | 12/15 (80%) |
| `get_lane_closures` | 9/19 (47%) |
| `get_wildfires` | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 16 | claude-sonnet-5 / fire-incidents-grapevine: The answer invents a 'Vulcan Fire' causing full closures in both directions, while ground truth... |
| missed-active-condition | 6 | claude-sonnet-5 / fire-route-sac-la-99: Misses the collision at Ming Ave and incorrectly states the Creek Fire is 'south of the route'... |
| bad-refusal | 3 | claude-sonnet-5 / quiet-i80-closures: The assistant falsely claimed a data outage instead of correctly reporting no lane closures on I-80... |
| other | 2 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the important context that it's fire season and... |

## Tool selection

11/91 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.58**
