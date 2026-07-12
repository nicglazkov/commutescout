# Eval results

Generated 2026-07-12T08:14:41+00:00 by `evals/run_evals.py` from `v2.16.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 23/28 (82%) |
| quiet-day | 21/30 (70%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 19/27 (70%) |
| **all** | 65/91 (71%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 12/18 (67%) |
| `get_chain_controls` | 16/20 (80%) |
| `get_incidents` | 12/15 (80%) |
| `get_lane_closures` | 9/19 (47%) |
| `get_wildfires` | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 15 | claude-sonnet-5 / fire-incidents-grapevine: The answer invents a 'Vulcan Fire' causing I-5 closures in both directions, which is not in the... |
| missed-active-condition | 6 | claude-sonnet-5 / fire-route-sac-la-99: The answer omits the collision at Ming Ave near Bakersfield, which is an active condition mentioned... |
| bad-refusal | 2 | claude-sonnet-5 / fire-99-alternative: The assistant refused to answer and asked for unnecessary clarification instead of reporting the... |
| other | 2 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the key contextual reason (fire season / R-0... |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-sr1-bigsur: The assistant hedges so heavily about data uncertainty that it effectively contradicts the ground... |

## Tool selection

14/91 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.53**
