# Eval results

Generated 2026-07-18T07:17:40+00:00 by `evals/run_evals.py` from `v2.24.1`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 21/28 (75%) |
| quiet-day | 23/30 (77%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 19/27 (70%) |
| **all** | 65/91 (71%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 12/18 (67%) |
| `get_chain_controls` | 17/20 (85%) |
| `get_incidents` | 10/15 (67%) |
| `get_lane_closures` | 12/19 (63%) |
| `get_wildfires` | 12/15 (80%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 15 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but invents a specific timestamp and Caltrans feed check,... |
| missed-active-condition | 9 | claude-sonnet-5 / fire-route-la-sac: Answer correctly identifies the I-5 Grapevine closure and VULCAN fire but fails to mention SR-99 as... |
| bad-refusal | 1 | claude-sonnet-5 / quiet-i80-closures:  |
| other | 1 | claude-sonnet-5 / quiet-us50-watt: The answer correctly says US-50 is not closed but fails to mention the scheduled electrical work at... |

## Tool selection

12/91 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.60**
