# Eval results

Generated 2026-07-17T00:51:43+00:00 by `evals/run_evals.py` from `v2.22.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

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
| `check_route` | 11/18 (61%) |
| `get_chain_controls` | 16/20 (80%) |
| `get_incidents` | 12/15 (80%) |
| `get_lane_closures` | 10/19 (53%) |
| `get_wildfires` | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 12 | claude-sonnet-5 / fire-incidents-grapevine: The answer invents a 'Vulcan Fire' causing full I-5 closures in both directions, while the ground... |
| missed-active-condition | 8 | claude-sonnet-5 / fire-route-sac-la-99: Answer covers the lane closure and Creek fire accurately but omits the collision at Ming Ave near... |
| bad-refusal | 3 | claude-sonnet-5 / fire-99-alternative: The assistant refused to answer and asked for clarification instead of reporting the known SR-99... |
| other | 2 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but misses the key fire-season context with R-0... |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-sr1-bigsur: The assistant undermines the correct answer by claiming its closure data source failed and casting... |

## Tool selection

13/90 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.60**
