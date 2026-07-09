# Eval results

Generated 2026-07-09T22:51:16+00:00 by `evals/run_evals.py` from `v1.8.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 13/28 (46%) | 23/28 (82%) |
| quiet-day | 19/30 (63%) | 20/30 (67%) |
| real-2026-07-07 | 3/6 (50%) | 5/6 (83%) |
| storm-day | 18/27 (67%) | 16/27 (59%) |
| **all** | 53/91 (58%) | 64/91 (70%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 1/4 (25%) | 1/4 (25%) |
| `check_route` | 11/18 (61%) | 12/18 (67%) |
| `get_chain_controls` | 14/20 (70%) | 16/20 (80%) |
| `get_incidents` | 10/15 (67%) | 11/15 (73%) |
| `get_lane_closures` | 9/19 (47%) | 10/19 (53%) |
| `get_wildfires` | 8/15 (53%) | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 29 | claude-haiku-4-5 / fire-i5-why: The assistant claims I-5 is open, contradicting the active VULCAN fire closure in both directions. |
| hallucinated-event | 21 | claude-haiku-4-5 / fire-i5-open: Claims southbound is passable when it's actually closed, and invents a specific wildfire cause... |
| other | 8 | claude-haiku-4-5 / quiet-sr17-clear: judge output unparseable |
| bad-refusal | 6 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for more info instead of reporting the known SR-99 lane closure at 7th Standard... |
| stale-data-trust | 1 | claude-haiku-4-5 / quiet-place-davis: Claims Caltrans closure feeds are unavailable, but the ground truth cites a specific I-80... |

## Tool selection

25/170 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.95**
