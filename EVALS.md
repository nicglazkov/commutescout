# Eval results

Generated 2026-07-13T20:41:00+00:00 by `evals/run_evals.py` from `v2.20.2`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 23/28 (82%) |
| quiet-day | 22/30 (73%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 19/27 (70%) |
| **all** | 66/91 (73%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 12/18 (67%) |
| `get_chain_controls` | 17/20 (85%) |
| `get_incidents` | 11/15 (73%) |
| `get_lane_closures` | 10/19 (53%) |
| `get_wildfires` | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 14 | claude-sonnet-5 / fire-incidents-grapevine: The answer invents full closures in both directions and 'emergency work' tags; ground truth only... |
| missed-active-condition | 7 | claude-sonnet-5 / fire-route-sac-la-99: Answer omits the collision at Ming Ave and mislocates the Creek Fire (places it near Kings County... |
| bad-refusal | 3 | claude-sonnet-5 / fire-99-alternative: The assistant refused to answer by asking for clarification instead of providing the known SR-99... |
| other | 1 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the critical context that it's fire season with... |

## Tool selection

12/90 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.65**
