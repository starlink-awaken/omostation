# tests/ — Root-Level Tests

> Root workspace tests. Project-level tests live in each `projects/*/tests/`.

## Unit Tests

Run all: `uv run pytest tests/ -q`

| File | What It Tests |
|------|---------------|
| `test_agent_workflow.py` | `bin/agent-workflow.py` — workflow lifecycle, bootstrap, lint, integrations/adapters |
| `test_bos_deprecated_count.py` | BOS service declaration vs execution alignment (deprecated count drift) |
| `test_classify_planned.py` | Task classification logic (planned vs active vs done) |
| `test_cron_mypy_gate.py` | Cron entry correctness — verifies mypy-baseline-gate is scheduled |
| `test_feedback_loop_guard.py` | `bin/gac/feedback-loop-guard.py` — P0 self-feedback loop monitoring |
| `test_god_module_lint.py` | `omo_lint_god_module` — single-file LOC hard rule enforcement |
| `test_governance_evolution.py` | `bin/gac/governance-evolution.py` — governance evolution roadmap validation |
| `test_yaml_bypass_invariant.py` | YAML bypass invariant — no unauthorized `status` field in `.omo/debt/items/*.yaml` |

## Integration Tests

Run all: `bash tests/integration/run-all.sh`

| File | What It Tests |
|------|---------------|
| `run-all.sh` | Unified test harness — runs all integration tests in sequence |
| `e2e-smoke.sh` | End-to-end smoke test — quick workspace health verification |
| `test-02-pipeline.sh` | Pipeline integration test (numbered: 02) |
| `test-05-pricing.sh` | Pricing integration test (numbered: 05) |
| `test-10-runtime-check.sh` | Runtime health check integration test (numbered: 10) |
| `test_ecos_dynamic_workflow.py` | eCOS dynamic workflow integration test |
| `test_quest_points_e2e.py` | Family QuestBoard + eCOS points calculation e2e |
| `test_runtime_e2e.py` | Runtime full-stack health verification e2e |

## Numbering Scheme

Integration shell scripts use a `test-NN-name.sh` pattern where `NN` is a priority/ordering number (02, 05, 10). Lower numbers run first in `run-all.sh`.
