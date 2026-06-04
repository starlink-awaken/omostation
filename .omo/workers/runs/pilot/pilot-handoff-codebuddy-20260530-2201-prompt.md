# Worker Prompt Contract

WORKER_ID: `codebuddy`
TASK_ID: `PILOT-WORKER-RECLAIM-HANDOFF-VALIDATION`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

Resume a reclaimed pilot after an intentionally interrupted `reasonix` run.
Read the reclaim context, complete the review note, and move the task YAML to
`review` if successful.

## Task SSOT and Handoff Context

- Task YAML: `.omo/tasks/active/PILOT-worker-reclaim-handoff-validation.yaml`
- First dispatch: `.omo/workers/runs/pilot-reclaim-reasonix-20260530-2158-dispatch.yaml`
- Reclaim note: `.omo/workers/runs/pilot-reclaim-reasonix-20260530-2158-reclaim.md`
- First worker stdout: `.omo/workers/runs/pilot-reclaim-reasonix-20260530-2158-stdout.log`

## Constraints

- You may only write to:
  - `.omo/tasks/active/PILOT-worker-reclaim-handoff-validation.yaml`
  - `.omo/workers/runs/pilot-reclaim-handoff-20260530-2158-review.md`
- Do not modify global state files or framework docs.
- Do not mark the task `done`.

## Required Work Pattern

1. Read the task YAML, reclaim note, and first-worker stdout first.
2. Complete the review note with summary, evidence, risks, and next step.
3. Update the task YAML to `review` if the handoff is complete.
4. Preserve any useful conclusion about reclaim readiness.
