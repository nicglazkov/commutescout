# Eval results

Generated 2026-07-18T10:22:07+00:00 by `evals/run_evals.py` from `v2.25.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 23/28 (82%) |
| quiet-day | 21/30 (70%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 18/27 (67%) |
| **all** | 64/91 (70%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 11/18 (61%) |
| `get_chain_controls` | 15/20 (75%) |
| `get_incidents` | 13/15 (87%) |
| `get_lane_closures` | 9/19 (47%) |
| `get_wildfires` | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 16 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but fabricates specific reasoning (mountain passes... |
| missed-active-condition | 7 | claude-sonnet-5 / fire-route-la-sac: Answer correctly identifies I-5 Grapevine closure but fails to mention SR-99 as the recommended... |
| bad-refusal | 3 | claude-sonnet-5 / fire-99-alternative: The assistant refused to answer and asked for clarification instead of reporting the known SR-99... |
| other | 1 | claude-sonnet-5 / quiet-us50-watt: Answer correctly says not closed but misses the key nuance: there IS scheduled electrical work at... |

## Tool selection

14/90 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.60**
