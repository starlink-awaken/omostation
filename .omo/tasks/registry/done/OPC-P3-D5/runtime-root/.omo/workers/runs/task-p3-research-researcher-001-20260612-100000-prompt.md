# Worker Prompt Contract

WORKER_ID: `researcher-001`
TASK_ID: `TASK-P3-RESEARCH`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

Collect current OPC phase facts from the phase docs

## Task SSOT

- Task YAML: `.omo/tasks/active/TASK-P3-RESEARCH.yaml`
- Source doc: `docs/OPC-PHASE2-MEMORY-SPINE.md`
- Source doc: `docs/OPC-PHASE3-SWARM-SPINE.md`
- Source doc: `docs/OPC-P2-READINESS.md`

## Constraints

- You may write to `delivery/`
- You may write to `.omo/tasks/active/TASK-P3-RESEARCH.yaml`
- You may write to `.omo/workers/runs/task-p3-research-researcher-001-20260612-100000-review.md`
- Do not modify global state files.
- Do not mark the task `done`.

## Required deliverables

- Required deliverable: `delivery/research-findings.md`
- Updating only the review note is not sufficient when required deliverables are listed.
