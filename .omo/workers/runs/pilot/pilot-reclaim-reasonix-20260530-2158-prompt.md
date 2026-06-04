# Worker Prompt Contract

WORKER_ID: `reasonix`
TASK_ID: `PILOT-WORKER-RECLAIM-HANDOFF-VALIDATION`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

Perform the first leg of a reclaim/handoff pilot. Inspect the OMO worker
framework docs and begin a structured review, but expect this run to be
intentionally interrupted by the coordinator.

## Task SSOT

- Task YAML: `.omo/tasks/active/PILOT-worker-reclaim-handoff-validation.yaml`
- Source docs:
  - `.omo/standards/agent-cli-worker-collaboration.md`
  - `.omo/workers/README.md`
  - `.omo/workers/runbooks/pilot-dispatch-and-reclaim.md`

## Constraints

- You may only write to:
  - `.omo/tasks/active/PILOT-worker-reclaim-handoff-validation.yaml`
  - `.omo/workers/runs/pilot-reclaim-handoff-20260530-2158-review.md`
  - `.omo/workers/runs/pilot-reclaim-reasonix-20260530-2158-reclaim.md`
- Do not modify global state files or framework docs.
- Do not mark the task `done`.

## Required Work Pattern

1. Read the task YAML and framework docs.
2. Start producing a review summary or checkpoint.
3. Preserve any partial findings in stdout or allowed output files.
4. Expect coordinator interruption; do not assume you will finish.
