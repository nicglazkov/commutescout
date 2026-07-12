# Eval results

Generated 2026-07-12T09:03:30+00:00 by `evals/run_evals.py` from `v2.17.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 22/28 (79%) |
| quiet-day | 20/30 (67%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 19/27 (70%) |
| **all** | 63/91 (69%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 12/18 (67%) |
| `get_chain_controls` | 15/20 (75%) |
| `get_incidents` | 11/15 (73%) |
| `get_lane_closures` | 8/19 (42%) |
| `get_wildfires` | 15/15 (100%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 17 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the key context that it's fire season with R-0... |
| missed-active-condition | 7 | claude-sonnet-5 / fire-route-sac-la-99: Answer correctly covers the lane closure and Creek Fire but omits the collision at Ming Ave near... |
| bad-refusal | 3 | claude-sonnet-5 / fire-99-alternative: Assistant refused to answer and asked for clarification instead of reporting the known SR-99... |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-place-davis: The answer incorrectly claims the Caltrans lane closure feed is down statewide and fails to convey... |

## Tool selection

11/89 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.70**
