# Eval results

Generated 2026-07-10T08:16:28+00:00 by `evals/run_evals.py` from `v1.11.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 15/28 (54%) | 20/28 (71%) |
| quiet-day | 19/30 (63%) | 21/30 (70%) |
| real-2026-07-07 | 2/6 (33%) | 3/6 (50%) |
| storm-day | 15/27 (56%) | 18/27 (67%) |
| **all** | 51/91 (56%) | 62/91 (68%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 2/4 (50%) |
| `check_route` | 9/18 (50%) | 13/18 (72%) |
| `get_chain_controls` | 16/20 (80%) | 16/20 (80%) |
| `get_incidents` | 11/15 (73%) | 9/15 (60%) |
| `get_lane_closures` | 5/19 (26%) | 9/19 (47%) |
| `get_wildfires` | 8/15 (53%) | 13/15 (87%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 31 | claude-haiku-4-5 / fire-i5-open: Says southbound is passable when it is actually fully closed at Frazier Mountain Park Rd,... |
| hallucinated-event | 26 | claude-haiku-4-5 / quiet-101-closures: Correctly reports the Trimble Rd closure but invents an unverified Story Rd on-ramp closure not in... |
| other | 5 | claude-haiku-4-5 / fire-route-la-sac: Says I-5 closed only northbound but ground truth is both directions closed; also names I-99 instead... |
| bad-refusal | 4 | claude-haiku-4-5 / quiet-i80-closures: The assistant refused due to claimed feed unavailability instead of reporting the known... |
| stale-data-trust | 2 | claude-haiku-4-5 / quiet-i80-full-closure-hallucination: The ground truth confirms the feed clearly shows no closures, but the assistant hedged by claiming... |
| wrong-location | 1 | claude-haiku-4-5 / quiet-route-oakland-sj: I-880 is in the Bay Area (District 4), not District 5, so the caveat about an unavailable feed is... |

## Tool selection

25/176 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.93**
