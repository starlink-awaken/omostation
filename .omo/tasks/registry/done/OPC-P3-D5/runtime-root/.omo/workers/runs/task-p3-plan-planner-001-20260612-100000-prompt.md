# Worker Prompt Contract

WORKER_ID: `planner-001`
TASK_ID: `TASK-P3-PLAN`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

Decompose the fixed OPC status goal into thin-binding worker tasks

## Task SSOT

- Task YAML: `.omo/tasks/active/TASK-P3-PLAN.yaml`
- Source doc: `docs/OPC-ROADMAP.md`
- Source doc: `docs/OPC-PHASE3-SWARM-SPINE.md`

## Constraints

- You may write to `delivery/`
- You may write to `.omo/tasks/active/TASK-P3-PLAN.yaml`
- You may write to `.omo/workers/runs/task-p3-plan-planner-001-20260612-100000-review.md`
- Do not modify global state files.
- Do not mark the task `done`.

## Required deliverables

- Required deliverable: `delivery/planner-plan.md`
- Updating only the review note is not sufficient when required deliverables are listed.
