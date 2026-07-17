# Eval results

Generated 2026-07-17T19:52:34+00:00 by `evals/run_evals.py` from `v2.24.0`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-4-6` (not an evaluated model).

## Scorecard

| Scenario | `claude-sonnet-5` |
|---|---|
| fire-day | 22/28 (79%) |
| quiet-day | 21/30 (70%) |
| real-2026-07-07 | 2/6 (33%) |
| storm-day | 19/27 (70%) |
| **all** | 64/91 (70%) |

## Pass rate by tool

| Tool | `claude-sonnet-5` |
|---|---|
| `check_region` | 2/4 (50%) |
| `check_route` | 10/18 (56%) |
| `get_chain_controls` | 18/20 (90%) |
| `get_incidents` | 11/15 (73%) |
| `get_lane_closures` | 10/19 (53%) |
| `get_wildfires` | 13/15 (87%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 16 | claude-sonnet-5 / fire-incidents-grapevine: The answer adds a full closure of northbound I-5 that is not in the ground truth, which only... |
| missed-active-condition | 5 | claude-sonnet-5 / fire-i5-why: Answer correctly notes fire-related closure but omits the specific VULCAN fire name, its size... |
| bad-refusal | 3 | claude-sonnet-5 / fire-99-alternative: Assistant asked for clarification instead of reporting the known SR-99 closure at 7th Standard Rd... |
| other | 2 | claude-sonnet-5 / fire-chains: Answer correctly states no chain controls but omits the fire season context and R-0 checkpoint... |
| stale-data-trust | 1 | claude-sonnet-5 / storm-kirkwood: Answer correctly identifies R-2 at Carson Pass/Kirkwood Meadows but undermines accuracy by... |

## Tool selection

13/89 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **3.66**
