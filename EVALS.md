# Eval results

Generated 2026-07-09T23:40:10+00:00 by `evals/run_evals.py` from `v1.9.1`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 15/28 (54%) | 19/28 (68%) |
| quiet-day | 21/30 (70%) | 20/30 (67%) |
| real-2026-07-07 | 2/6 (33%) | 3/6 (50%) |
| storm-day | 16/27 (59%) | 16/27 (59%) |
| **all** | 54/91 (59%) | 58/91 (64%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 1/4 (25%) |
| `check_route` | 11/18 (61%) | 12/18 (67%) |
| `get_chain_controls` | 15/20 (75%) | 15/20 (75%) |
| `get_incidents` | 8/15 (53%) | 11/15 (73%) |
| `get_lane_closures` | 10/19 (53%) | 6/19 (32%) |
| `get_wildfires` | 8/15 (53%) | 13/15 (87%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 30 | claude-haiku-4-5 / fire-i5-why: Ground truth states both directions fully closed, but the answer only reports northbound as closed... |
| hallucinated-event | 25 | claude-haiku-4-5 / fire-creek: Correctly conveys the fire details but invents unverified discovery date (July 2nd) and specific... |
| other | 8 | claude-haiku-4-5 / real-i80-closures: States 8 closures instead of 9 and doesn't clearly convey none are full roadway closures, though... |
| bad-refusal | 5 | claude-haiku-4-5 / fire-99-alternative: The assistant asked for more information instead of reporting the SR-99 lane closure at 7th... |
| wrong-location | 1 | claude-haiku-4-5 / storm-lowest-elevation-control: Answer claims no controls and cites Kyburz instead of the expected R-1 at Pollock Pines and R-2 at... |
| wrong-tool-or-no-tool | 1 | claude-sonnet-5 / quiet-i80-closures: The assistant claimed data was unavailable rather than reporting the shoulder-only litter removal... |

## Tool selection

26/171 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.96**
