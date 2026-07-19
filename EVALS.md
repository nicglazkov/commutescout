# Eval results

Generated 2026-07-19T08:22:47+00:00 by `evals/run_evals.py` from `v2.27.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 23/28 (82%) |
| quiet-day | 21/30 (70%) |
| real-2026-07-07 | 3/6 (50%) |
| storm-day | 20/27 (74%) |
| **all** | 67/91 (74%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 12/18 (67%) |
| `get_chain_controls` | 15/20 (75%) |
| `get_incidents` | 13/15 (87%) |
| `get_lane_closures` | 10/19 (53%) |
| `get_wildfires` | 15/15 (100%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 15 | claude-sonnet-5 / fire-incidents-grapevine: The answer correctly mentions the traffic hazard NB at Grapevine Rd and the SB closure at Frazier... |
| missed-active-condition | 6 | claude-sonnet-5 / fire-route-sac-la-99: The answer omits the collision at Ming Ave near Bakersfield that is part of the ground truth. |
| other | 2 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the key context that it's fire season with R-0... |
| bad-refusal | 1 | claude-sonnet-5 / quiet-i80-closures: The assistant falsely claims its data feed is down and refuses to answer, when the correct answer... |

## Tool selection

11/91 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.74**
