# Eval results

Generated 2026-07-09T22:37:23+00:00 by `evals/run_evals.py` from `v1.7.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 14/28 (50%) | 23/28 (82%) |
| quiet-day | 18/30 (60%) | 23/30 (77%) |
| real-2026-07-07 | 3/6 (50%) | 4/6 (67%) |
| storm-day | 12/27 (44%) | 19/27 (70%) |
| **all** | 47/91 (52%) | 69/91 (76%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 2/4 (50%) |
| `check_route` | 10/18 (56%) | 14/18 (78%) |
| `get_chain_controls` | 13/20 (65%) | 16/20 (80%) |
| `get_incidents` | 9/15 (60%) | 12/15 (80%) |
| `get_lane_closures` | 6/19 (32%) | 11/19 (58%) |
| `get_wildfires` | 7/15 (47%) | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 26 | claude-haiku-4-5 / fire-i5-open: Says southbound is passable but ground truth is a full southbound closure at Frazier Mountain Park... |
| hallucinated-event | 22 | claude-haiku-4-5 / fire-when-reopen: The assistant claims the road is open with no closures, contradicting the ground truth of an... |
| other | 9 | claude-haiku-4-5 / quiet-fires-statewide: judge output unparseable |
| bad-refusal | 5 | claude-haiku-4-5 / quiet-chains-tahoe: The assistant asked for a starting location instead of providing the available chain control... |
| wrong-tool-or-no-tool | 2 | claude-haiku-4-5 / fire-vulcan-size: The assistant asked for clarification instead of providing the fire's size and containment. |
| wrong-location | 1 | claude-haiku-4-5 / quiet-region-bay-area: Misplaces the I-80 University Ave incident in San Francisco instead of Berkeley and adds unverified... |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-place-davis: Claims Caltrans closure feed is down statewide, but ground truth shows a valid I-80 shoulder-only... |

## Tool selection

22/172 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.97**
