# Eval results

Generated 2026-07-12T07:40:26+00:00 by `evals/run_evals.py` from `v2.15.1`. Models answer the golden questions using the MCP tool surface served from recorded fixtures; grading is exact-fact matching plus an LLM judge scored against ground truth. Judge: `claude-opus-4-8` (not an evaluated model).

## Scorecard

| Scenario | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| fire-day | 0/28 (0%) | 0/28 (0%) |
| quiet-day | 0/30 (0%) | 0/30 (0%) |
| real-2026-07-07 | 0/6 (0%) | 0/6 (0%) |
| storm-day | 0/27 (0%) | 0/27 (0%) |
| **all** | 0/91 (0%) | 0/91 (0%) |

## Pass rate by tool

| Tool | `claude-haiku-4-5` | `claude-sonnet-5` |
|---|---|---|
| `check_region` | 0/4 (0%) | 0/4 (0%) |
| `check_route` | 0/18 (0%) | 0/18 (0%) |
| `get_chain_controls` | 0/20 (0%) | 0/20 (0%) |
| `get_incidents` | 0/15 (0%) | 0/15 (0%) |
| `get_lane_closures` | 0/19 (0%) | 0/19 (0%) |
| `get_wildfires` | 0/15 (0%) | 0/15 (0%) |

## Failure taxonomy

| Category | Count | Example |
|---|---|---|
| other | 182 | claude-haiku-4-5 / fire-i5-open:  |

## Tool selection

