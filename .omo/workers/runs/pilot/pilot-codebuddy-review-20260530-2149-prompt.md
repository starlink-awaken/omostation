# Worker Prompt Contract

WORKER_ID: `codebuddy`
TASK_ID: `PILOT-EXTERNAL-WORKER-DISPATCH-VALIDATION`
TRANSPORT: `cli_prompt`
READ_BUDGET: `5`

## Mission

Run a safe L0 pilot dispatch against the OMO worker-framework docs. Do not edit
framework docs in this pilot. Instead, validate the handoff packet, inspect the
framework docs, write a structured review note, and update the task YAML to
`review` if successful.

## Task SSOT

- Task YAML: `.omo/tasks/active/PILOT-external-worker-dispatch-validation.yaml`
- Source docs:
  - `.omo/standards/agent-cli-worker-collaboration.md`
  - `.omo/workers/README.md`
  - `.omo/workers/runbooks/pilot-dispatch-and-reclaim.md`

## Constraints

- Stay within declared task scope.
- You may only write to:
  - `.omo/tasks/active/PILOT-external-worker-dispatch-validation.yaml`
  - `.omo/workers/runs/pilot-codebuddy-review-20260530-2149-review.md`
- Do not modify `.omo/state/system.yaml`, `.omo/goals/current.yaml`, `convergence.yaml`, or framework docs.
- Do not mark the task `done`.

## Gate Policy

- Allowed execution level: `L0`
- No approval flow is needed for this pilot.

## Required Work Pattern

1. Read the task YAML and the three framework docs first.
2. Validate whether the dispatch packet is coherent and recoverable.
3. Write a review note with:
   - summary of work done
   - changed files
   - evidence
   - unresolved risks
   - recommended next step
4. If successful, update the task YAML to `review`.
5. Do **not** mark the task `done`.

## Anti-Stall Contract

- After 5 reads, produce a write, result, or blocked report.
- If stuck, preserve partial output in the review note.
