# Worker Prompt Contract

WORKER_ID: `reviewer-001`
TASK_ID: `TASK-P3-REVIEW`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

Verify the research findings and produce the final governed answer

## Task SSOT

- Task YAML: `.omo/tasks/active/TASK-P3-REVIEW.yaml`
- Source doc: `delivery/planner-plan.md`
- Source doc: `delivery/research-findings.md`
- Source doc: `.omo/tasks/done/TASK-P3-PLAN.yaml`
- Source doc: `.omo/tasks/done/TASK-P3-RESEARCH.yaml`

## Constraints

- You may write to `delivery/`
- You may write to `.omo/tasks/active/TASK-P3-REVIEW.yaml`
- You may write to `.omo/workers/runs/task-p3-review-reviewer-001-20260612-100000-review.md`
- Do not modify global state files.
- Do not mark the task `done`.

## Required deliverables

- Required deliverable: `delivery/final-answer.md`
- Updating only the review note is not sufficient when required deliverables are listed.
