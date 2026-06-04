# Worker Prompt Contract

WORKER_ID: `reasonix`
TASK_ID: `D3-EU-PRICING-TEST`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

eu-pricing 独立测试覆盖 (Resolve D3 debt)

## Task SSOT

- Task YAML: `.omo/tasks/active/D3-EU-PRICING-TEST.yaml`
- Source doc: `_knowledge/management/debt-systems-analysis-and-governance.md`
- Source doc: `_knowledge/design/debt-cleanup-plan.md`

## Constraints

- You may write to `projects/kairon/packages/eu-pricing/tests/`
- You may write to `projects/kairon/packages/eu-pricing/src/eu_pricing/`
- You may write to `projects/kairon/packages/eu-pricing/`
- You may write to `.omo/tasks/active/D3-EU-PRICING-TEST.yaml`
- You may write to `.omo/workers/runs/d3-eu-pricing-test-reasonix-20260603-010543-review.md`
- Do not modify global state files.
- Do not mark the task `done`.

## Required deliverables

- Required deliverable: `projects/kairon/packages/eu-pricing/tests/`
- Required deliverable: `projects/kairon/packages/eu-pricing/src/eu_pricing/`
- Required deliverable: `projects/kairon/packages/eu-pricing/pyproject.toml`
- Updating only the review note is not sufficient when required deliverables are listed.

## Recovery context

- Reclaim reason: lease expired with no checkpoint or review output
- Resume from checkpoint: `.omo/workers/runs/d3-eu-pricing-test-codebuddy-20260602-230142-checkpoint.md`
- Review reclaim handoff: `.omo/workers/runs/d3-eu-pricing-test-codebuddy-20260602-230142-reclaim.md`
- Continue from the recorded checkpoint instead of restarting the task.
