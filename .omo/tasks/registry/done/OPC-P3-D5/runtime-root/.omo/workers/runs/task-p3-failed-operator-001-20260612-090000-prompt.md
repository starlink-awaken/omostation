# Worker Prompt Contract

WORKER_ID: `operator-001`
TASK_ID: `TASK-P3-FAILED`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

Demonstrate governed follow-up after a reclaim_due worker

## Task SSOT

- Task YAML: `.omo/tasks/active/TASK-P3-FAILED.yaml`
- Source doc: `docs/OPC-MASTER-EXECUTION-PLAYBOOK.md`

## Constraints

- You may write to `delivery/`
- You may write to `.omo/tasks/active/TASK-P3-FAILED.yaml`
- You may write to `.omo/workers/runs/task-p3-failed-operator-001-20260612-090000-review.md`
- Do not modify global state files.
- Do not mark the task `done`.

## Required deliverables

- Required deliverable: `delivery/operator-recovery.md`
- Updating only the review note is not sufficient when required deliverables are listed.
