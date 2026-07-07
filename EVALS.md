# Eval results

Generated 2026-07-07T00:11:29+00:00 by `evals/run_evals.py`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-5`.

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 19/28 (68%) | 25/28 (89%) |
| quiet-day | 23/30 (77%) | 23/30 (77%) |
| storm-day | 21/27 (78%) | 23/27 (85%) |
| **all** | 63/85 (74%) | 71/85 (84%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 2/3 (67%) | 1/3 (33%) |
| `check_route` | 14/17 (82%) | 13/17 (76%) |
| `get_chain_controls` | 15/19 (79%) | 18/19 (95%) |
| `get_incidents` | 12/15 (80%) | 14/15 (93%) |
| `get_lane_closures` | 12/18 (67%) | 13/18 (72%) |
| `get_wildfires` | 8/13 (62%) | 12/13 (92%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| hallucinated-event | 14 | claude-haiku-4-5 / fire-remote: Assistant claims no REMOTE fire exists and invents other fires instead of confirming the ground trut |
| missed-active-condition | 13 | claude-haiku-4-5 / fire-i5-why: Assistant claims no closure, directly contradicting the actual VULCAN fire closure. |
| bad-refusal | 6 | claude-haiku-4-5 / fire-99-alternative: Assistant asked for clarification instead of providing the known SR-99 closure near Bakersfield. |
| other | 3 | claude-haiku-4-5 / storm-chains-r2-meaning: Assistant describes R-1 rules (chains carried but optional) instead of R-2, which requires chains in |

Mean answer quality (judge, 1-5): **4.18**
