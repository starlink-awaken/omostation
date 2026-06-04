# Worker Prompt Contract

WORKER_ID: `codebuddy`
TASK_ID: `D2-CI-E2E-TEST-ENV`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

CI E2E 测试环境容器化 (Resolve D2 debt)

## Task SSOT

- Task YAML: `.omo/tasks/active/D2-CI-E2E-TEST-ENV.yaml`
- Source doc: `_knowledge/management/debt-systems-analysis-and-governance.md`
- Source doc: `_knowledge/design/debt-cleanup-plan.md`

## Constraints

- You may write to `.omo/tasks/active/D2-CI-E2E-TEST-ENV.yaml`
- You may write to `.omo/workers/runs/d2-ci-e2e-test-env-codebuddy-20260602-230142-review.md`
- Do not modify global state files.
- Do not mark the task `done`.

## Required deliverables

- Updating only the review note is not sufficient when required deliverables are listed.
