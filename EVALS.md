# Eval results

Generated 2026-07-11T18:23:05+00:00 by `evals/run_evals.py` from `v2.7.1`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 15/28 (54%) | 19/28 (68%) |
| quiet-day | 19/30 (63%) | 21/30 (70%) |
| real-2026-07-07 | 3/6 (50%) | 3/6 (50%) |
| storm-day | 13/27 (48%) | 19/27 (70%) |
| **all** | 50/91 (55%) | 62/91 (68%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 3/4 (75%) |
| `check_route` | 9/18 (50%) | 10/18 (56%) |
| `get_chain_controls` | 12/20 (60%) | 17/20 (85%) |
| `get_incidents` | 12/15 (80%) | 10/15 (67%) |
| `get_lane_closures` | 5/19 (26%) | 8/19 (42%) |
| `get_wildfires` | 10/15 (67%) | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 29 | claude-haiku-4-5 / fire-i5-why: The assistant claims no closure exists, contradicting the active VULCAN fire closure of I-5 at the... |
| hallucinated-event | 24 | claude-haiku-4-5 / fire-i5-open: Correctly identifies the closure but invents the Vulcan wildfire details and mischaracterizes the... |
| other | 11 | claude-haiku-4-5 / fire-route-la-sac: Correctly identifies I-5 Grapevine closure but says only northbound (ground truth is both... |
| stale-data-trust | 2 | claude-haiku-4-5 / quiet-i80-full-closure-hallucination: Claims the closure feed is unavailable and hedges, when the feed actually shows no closures, so it... |
| wrong-location | 2 | claude-haiku-4-5 / storm-route-reno-sac: Assistant ordered Donner Lake Interchange after Kingvale, but ground truth has Donner Lake first... |
| bad-refusal | 2 | claude-sonnet-5 / fire-99-alternative: The assistant asked for trip details instead of reporting the SR-99 closure at 7th Standard Rd. |

## Tool selection

25/175 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.88**
