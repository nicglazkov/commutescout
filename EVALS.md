# Eval results

Generated 2026-07-19T08:48:04+00:00 by `evals/run_evals.py` from `v2.28.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 24/28 (86%) |
| quiet-day | 19/30 (63%) |
| real-2026-07-07 | 3/6 (50%) |
| storm-day | 20/27 (74%) |
| **all** | 66/91 (73%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 1/4 (25%) |
| `check_route` | 11/18 (61%) |
| `get_chain_controls` | 16/20 (80%) |
| `get_incidents` | 11/15 (73%) |
| `get_lane_closures` | 12/19 (63%) |
| `get_wildfires` | 15/15 (100%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 16 | claude-sonnet-5 / fire-incidents-grapevine: Answer correctly mentions the traffic hazard on NB I-5 and road closure on SB I-5, but fabricates a... |
| missed-active-condition | 6 | claude-sonnet-5 / fire-route-sac-la-99: The answer omits the collision at Ming Ave near Bakersfield, which is an active condition mentioned... |
| other | 2 | claude-sonnet-5 / fire-chains: The answer correctly states no chain controls but omits the critical safety context that it's fire... |
| bad-refusal | 1 | claude-sonnet-5 / quiet-i80-closures: The assistant falsely claimed data was unavailable instead of correctly stating there are no lane... |

## Tool selection

15/90 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.63**
