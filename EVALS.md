# Eval results

Generated 2026-07-09T10:50:43+00:00 by `evals/run_evals.py` from `v1.2.1`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 12/28 (43%) | 21/28 (75%) |
| quiet-day | 18/30 (60%) | 23/30 (77%) |
| real-2026-07-07 | 3/6 (50%) | 4/6 (67%) |
| storm-day | 17/27 (63%) | 21/27 (78%) |
| **all** | 50/91 (55%) | 69/91 (76%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/4 (50%) | 1/4 (25%) |
| `check_route` | 10/18 (56%) | 14/18 (78%) |
| `get_chain_controls` | 16/20 (80%) | 17/20 (85%) |
| `get_incidents` | 10/15 (67%) | 11/15 (73%) |
| `get_lane_closures` | 6/19 (32%) | 12/19 (63%) |
| `get_wildfires` | 6/15 (40%) | 14/15 (93%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 29 | claude-haiku-4-5 / fire-i5-open: Claims southbound is open when I-5 is closed in both directions, and invents wildfire details. |
| hallucinated-event | 18 | claude-haiku-4-5 / quiet-101-closures: Invented a second closure (Story Rd on-ramp) not in the ground truth. |
| bad-refusal | 8 | claude-haiku-4-5 / fire-remote: The assistant refused to answer and asked for clarification instead of stating the fire poses no... |
| wrong-tool-or-no-tool | 3 | claude-haiku-4-5 / fire-vulcan-size: The assistant failed to provide the fire size and containment, instead asking for clarification. |
| wrong-location | 2 | claude-haiku-4-5 / fire-alt-check: Correctly identifies I-5 Grapevine closure but recommends CA-58 instead of the open SR-99 corridor... |
| other | 2 | claude-haiku-4-5 / real-fires-near-i5: Names a specific fire (MARTINS) but does not mention the ground-truth BIG or WILDWOOD fires, and... |
| stale-data-trust | 1 | claude-sonnet-5 / quiet-place-davis: Claims closure feed is down and can't confirm closures, but ground truth shows a known... |

## Tool selection

22/169 answers led with a different tool than the golden question targets (declared vs first observed call). Not always an error - check_region can legitimately answer a get_incidents question - but a rising rate means the tool descriptions are drifting.

Mean answer quality (judge, 1-5): **4.05**
