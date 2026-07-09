# Eval results

Generated 2026-07-09T11:20:53+00:00 by `evals/run_evals.py` from `v1.4.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 15/28 (54%) | 23/28 (82%) |
| quiet-day | 20/30 (67%) | 22/30 (73%) |
| real-2026-07-07 | 2/6 (33%) | 3/6 (50%) |
| storm-day | 14/27 (52%) | 20/27 (74%) |
| **all** | 51/91 (56%) | 68/91 (75%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 1/4 (25%) | 1/4 (25%) |
| `check_route` | 14/18 (78%) | 15/18 (83%) |
| `get_chain_controls` | 14/20 (70%) | 18/20 (90%) |
| `get_incidents` | 8/15 (53%) | 10/15 (67%) |
| `get_lane_closures` | 8/19 (42%) | 10/19 (53%) |
| `get_wildfires` | 6/15 (40%) | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 25 | claude-haiku-4-5 / fire-i5-open: Correctly identifies NB closure and SB incident but frames it as one-directional rather than a full... |
| hallucinated-event | 19 | claude-haiku-4-5 / quiet-101-closures: Invents a second closure (Story Rd on-ramp) not in the ground truth. |
| bad-refusal | 7 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for clarification instead of reporting the known SR-99 lane closure at 7th... |
| other | 7 | claude-haiku-4-5 / real-i80-closures: Reports 8 closures instead of 9, undercounting the active closures despite correctly noting no full... |
| stale-data-trust | 3 | claude-haiku-4-5 / quiet-i80-full-closure-hallucination: Correctly states no closure, but claims camera/chain feeds confirm clear despite admitting data... |
| wrong-tool-or-no-tool | 1 | claude-haiku-4-5 / fire-all-fires: The assistant refused to list the active wildfires, missing all three that should have been... |
| wrong-location | 1 | claude-haiku-4-5 / storm-route-reno-sac: The assistant places the R-1 lane closure at Alta (mile 63.6) instead of Baxter as required by... |

## Tool selection

20/170 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.93**
