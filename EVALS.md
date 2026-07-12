# Eval results

Generated 2026-07-12T11:07:15+00:00 by `evals/run_evals.py` from `v2.17.1`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 23/28 (82%) |
| quiet-day | 22/30 (73%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 17/27 (63%) |
| **all** | 64/91 (70%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 11/18 (61%) |
| `get_chain_controls` | 15/20 (75%) |
| `get_incidents` | 13/15 (87%) |
| `get_lane_closures` | 10/19 (53%) |
| `get_wildfires` | 13/15 (87%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 13 | claude-sonnet-5 / fire-remote: The answer correctly says REMOTE fire is not near major highways but invents fictional fires... |
| missed-active-condition | 10 | claude-sonnet-5 / fire-route-sac-la-99: The answer omits the collision at Ming Ave near Bakersfield, which is an active condition in the... |
| bad-refusal | 3 | claude-sonnet-5 / fire-99-alternative: The assistant refused to answer and asked for clarification instead of providing the known SR-99... |
| other | 1 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the critical fire-season/R-0 checkpoint context... |

## Tool selection

10/89 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.57**
