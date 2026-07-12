# Eval results

Generated 2026-07-12T18:10:24+00:00 by `evals/run_evals.py` from `v2.18.1`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 24/28 (86%) |
| quiet-day | 23/30 (77%) |
| real-2026-07-07 | 3/6 (50%) |
| storm-day | 20/27 (74%) |
| **all** | 70/91 (77%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 13/18 (72%) |
| `get_chain_controls` | 15/20 (75%) |
| `get_incidents` | 13/15 (87%) |
| `get_lane_closures` | 12/19 (63%) |
| `get_wildfires` | 15/15 (100%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 13 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but invents specific detail about 'fire season / R-0... |
| missed-active-condition | 6 | claude-sonnet-5 / fire-route-sac-la-99: The answer omits the collision at Ming Ave, which is an active condition from the ground truth. |
| bad-refusal | 2 | claude-sonnet-5 / fire-99-alternative: The assistant refused to answer and asked for clarification instead of reporting the known SR-99... |

## Tool selection

12/89 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.76**
