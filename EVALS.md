# Eval results

Generated 2026-07-06T05:42:48+00:00 by `evals/run_evals.py`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-sonnet-5`.

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 17/25 (68%) | 22/25 (88%) |
| quiet-day | 19/25 (76%) | 18/25 (72%) |
| storm-day | 20/25 (80%) | 22/25 (88%) |
| **all** | 56/75 (75%) | 62/75 (83%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_route` | 13/17 (76%) | 13/17 (76%) |
| `get_chain_controls` | 15/18 (83%) | 17/18 (94%) |
| `get_incidents` | 7/13 (54%) | 6/13 (46%) |
| `get_lane_closures` | 11/14 (79%) | 13/14 (93%) |
| `get_wildfires` | 10/13 (77%) | 13/13 (100%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| missed-active-condition | 19 | claude-haiku-4-5 / fire-i5-why: Correctly conveys closure and wildfire cause but omits VULCAN fire name, acreage, and containment de |
| bad-refusal | 6 | claude-haiku-4-5 / fire-99-alternative: Fails to provide known SR-99 closure info and instead asks for unnecessary details. |
| hallucinated-event | 6 | claude-haiku-4-5 / fire-when-reopen: Claims no closure exists, contradicting the ground truth that an indefinite closure is in effect. |
| other | 1 | claude-haiku-4-5 / storm-chains-r2-meaning: Misstates R-2 as chains-optional/carry-only, when it actually requires 2WD sedans to install chains, |

Mean answer quality (judge, 1-5): **4.12**
