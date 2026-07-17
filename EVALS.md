# Eval results

Generated 2026-07-17T07:58:28+00:00 by `evals/run_evals.py` from `v2.23.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 23/28 (82%) |
| quiet-day | 21/30 (70%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 20/27 (74%) |
| **all** | 66/91 (73%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 12/18 (67%) |
| `get_chain_controls` | 15/20 (75%) |
| `get_incidents` | 13/15 (87%) |
| `get_lane_closures` | 10/19 (53%) |
| `get_wildfires` | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 14 | claude-sonnet-5 / fire-incidents-grapevine: The answer invents full bidirectional closures and fire-related emergency work; ground truth only... |
| missed-active-condition | 6 | claude-sonnet-5 / fire-route-sac-la-99: The answer omits the collision at Ming Ave near Bakersfield, which is an active condition from the... |
| bad-refusal | 3 | claude-sonnet-5 / fire-99-alternative: The assistant refused to answer by asking for clarification instead of providing the known SR-99... |
| other | 2 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the key context that it is fire season and all... |

## Tool selection

9/89 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.70**
