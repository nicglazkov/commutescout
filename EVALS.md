# Eval results

Generated 2026-07-12T00:02:50+00:00 by `evals/run_evals.py` from `v2.11.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 19/28 (68%) | 21/28 (75%) |
| quiet-day | 20/30 (67%) | 22/30 (73%) |
| real-2026-07-07 | 3/6 (50%) | 4/6 (67%) |
| storm-day | 16/27 (59%) | 17/27 (63%) |
| **all** | 58/91 (64%) | 64/91 (70%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 2/4 (50%) |
| `check_route` | 11/18 (61%) | 11/18 (61%) |
| `get_chain_controls` | 14/20 (70%) | 16/20 (80%) |
| `get_incidents` | 11/15 (73%) | 9/15 (60%) |
| `get_lane_closures` | 9/19 (47%) | 12/19 (63%) |
| `get_wildfires` | 11/15 (73%) | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 29 | claude-haiku-4-5 / fire-i5-why: Ground truth says both directions fully closed, but the answer claims southbound is open,... |
| missed-active-condition | 20 | claude-haiku-4-5 / fire-vulcan-size: The assistant failed to find the VULCAN fire (48,213 acres, 15% contained) and incorrectly reported... |
| other | 6 | claude-haiku-4-5 / quiet-chains-statewide: judge output unparseable |
| bad-refusal | 2 | claude-haiku-4-5 / storm-emerald-bay-why: The assistant asked for clarification instead of providing the known SR-89 Emerald Bay closure... |
| wrong-tool-or-no-tool | 1 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for origin/destination instead of reporting the known SR-99 lane closure at 7th... |
| stale-data-trust | 1 | claude-haiku-4-5 / quiet-place-davis: It reported no lane closures but claimed the feed had issues, missing the shoulder-only litter... |
| wrong-location | 1 | claude-haiku-4-5 / storm-lowest-elevation-control: Fails to identify the first control as R-1 at Pollock Pines and R-2 at Twin Bridges, instead... |

## Tool selection

28/175 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **4.09**
