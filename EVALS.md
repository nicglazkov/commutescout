# Eval results

Generated 2026-07-18T11:06:57+00:00 by `evals/run_evals.py` from `v2.26.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 24/28 (86%) |
| quiet-day | 22/30 (73%) |
| real-2026-07-07 | 3/6 (50%) |
| storm-day | 19/27 (70%) |
| **all** | 68/91 (75%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 11/18 (61%) |
| `get_chain_controls` | 15/20 (75%) |
| `get_incidents` | 13/15 (87%) |
| `get_lane_closures` | 12/19 (63%) |
| `get_wildfires` | 15/15 (100%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 13 | claude-sonnet-5 / fire-incidents-grapevine: The answer halluccinates a full closure in both directions; the ground truth only shows a traffic... |
| missed-active-condition | 6 | claude-sonnet-5 / fire-route-sac-la-99: The answer misses the collision at Ming Ave, which is an active condition mentioned in the ground... |
| bad-refusal | 2 | claude-sonnet-5 / quiet-i80-closures: The assistant falsely claimed its data feed was down instead of correctly reporting no lane... |
| other | 1 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the key context that it's fire season with all... |
| wrong-location | 1 | claude-sonnet-5 / storm-kirkwood: Answer correctly identifies R-2 at Kirkwood Meadows but misses the R-2 at Carson Pass, and... |

## Tool selection

13/91 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.68**
