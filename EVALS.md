# Eval results

Generated 2026-07-07T23:17:38+00:00 by `evals/run_evals.py` from `351f3250afeea9d20d990badee2b8b8ca0734bed`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 14/28 (50%) | 20/28 (71%) |
| quiet-day | 22/30 (73%) | 22/30 (73%) |
| real-2026-07-07 | 2/6 (33%) | 5/6 (83%) |
| storm-day | 15/27 (56%) | 20/27 (74%) |
| **all** | 53/91 (58%) | 67/91 (74%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 4/4 (100%) |
| `check_route` | 11/18 (61%) | 12/18 (67%) |
| `get_chain_controls` | 13/20 (65%) | 18/20 (90%) |
| `get_incidents` | 9/15 (60%) | 10/15 (67%) |
| `get_lane_closures` | 9/19 (47%) | 9/19 (47%) |
| `get_wildfires` | 9/15 (60%) | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 29 | claude-haiku-4-5 / fire-i5-why: Answer claims I-5 is not closed, contradicting the active VULCAN fire closure. |
| hallucinated-event | 20 | claude-haiku-4-5 / fire-i5-open: Attributes closure to a fabricated VULCAN wildfire and adds invented mile markers rather than the... |
| bad-refusal | 6 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for clarification instead of reporting the known SR-99 lane closure at 7th... |
| wrong-tool-or-no-tool | 3 | claude-haiku-4-5 / fire-all-fires: The assistant refused to list the three active wildfires, deflecting to external sources instead of... |
| other | 3 | claude-haiku-4-5 / storm-chains-r2-meaning: States chains required for sedan but omits the key R-2 exemption for 4WD/AWD with snow tires. |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-place-davis: Assistant claims the Caltrans closure feed is down, but ground truth shows a closure record... |

## Tool selection

25/170 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **4.06**
