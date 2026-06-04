# Worker Prompt Contract

Use this template when dispatching an external worker CLI.

---

WORKER_ID: `<worker-id>`
TASK_ID: `<task-id>`
TRANSPORT: `<cli_prompt|acp_stdio|acp_streamable_http>`
READ_BUDGET: `5`

## Mission

`<one-sentence task goal>`

## Task SSOT

- Task YAML: `<path>`
- Source docs:
  - `<doc 1>`
  - `<doc 2>`

## Constraints

- Stay within declared task scope.
- Write only to declared output paths.
- Do not modify `.omo/state/system.yaml`, `.omo/goals/current.yaml`, or `convergence.yaml`.
- Do not touch blocked capabilities (Apple / WeChat / SMB / family / media / high-autonomy).
- If the task reaches L2/L3 execution, stop and request release.

## Gate Policy

- Allowed execution level: `<L0|L1>`
- May prepare: `<L2>`
- Must not self-approve L2/L3.
- If denied by operation-level policy, return the deny evidence instead of retrying blindly.

## Anti-Stall Contract

- After 5 reads, produce a write, result, or blocked report.
- Emit a checkpoint after each material write.
- If stuck, produce a partial result with:
  - what changed
  - what remains blocked
  - what the next worker should do

## Required Output

Return all of the following:

1. summary of work done
2. changed files
3. evidence
4. unresolved risks
5. recommended next step

## Completion Rule

- If implementation is done, move the task to `review` with evidence.
- Do not mark the task `done`.
- If blocked, emit a blocked note for coordinator decision.
