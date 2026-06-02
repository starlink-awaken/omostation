# .omo/workers/ — External Worker Framework

This directory contains the lightweight framework for integrating external
agent CLIs into OMO collaboration.

## Layout

```text
workers/
├── README.md
├── registry.yaml
├── runbooks/
│   └── pilot-dispatch-and-reclaim.md
├── runs/
└── templates/
    ├── worker-approval-record.yaml
    ├── worker-dispatch-record.yaml
    ├── worker-prompt.md
    ├── worker-reclaim-note.md
    └── worker-task-envelope.yaml
```

## What This Framework Does

1. registers worker capabilities and policies
2. standardizes handoff packets
3. prevents worker stalls from becoming unrecoverable
4. keeps knowledge shareable between workers
5. keeps gate and permission decisions with the coordinator

## Coordinator Workflow

1. Select a task from `.omo/tasks/active/`.
2. Pick a worker from `registry.yaml`.
3. Use the dispatch CLI to preclaim the lease and generate the run packet.
4. Launch the worker via CLI or ACP.
5. Watch lease/heartbeat and collect checkpoints.
6. If the worker stalls, create a reclaim note and reassign.
7. Review results and then close, block, or requeue the task.

### Dispatch CLI

Minimal usage:

```bash
scripts/omo worker dispatch <TASK_ID> --worker <worker-id> --write-path <path>
```

Example:

```bash
scripts/omo worker dispatch TASK-123 --worker codebuddy --write-path src/app.py
```

To immediately launch the worker after packet generation:

```bash
scripts/omo worker dispatch TASK-123 --worker codebuddy --write-path src/app.py --launch
```

Check current active worker runs:

```bash
scripts/omo worker status
```

Reclaim a stalled task to a successor worker while carrying forward checkpoint context:

```bash
scripts/omo worker reclaim TASK-123 --successor reasonix --reason "lease expired" --write-path src/app.py
```

The reclaim flow updates the prior dispatch to `reclaimed`, records the reclaim reason,
and injects checkpoint/reclaim references into the successor packet so the next worker
continues from the last checkpoint instead of restarting.

## Current Workers

### codebuddy

- CLI prompt: `codebuddy -p "<prompt>"`
- ACP stdio: `codebuddy --acp --acp-transport stdio`
- ACP HTTP: `codebuddy --acp --acp-transport streamable-http`

### reasonix

- CLI prompt: `reasonix run "<prompt>"`
- ACP stdio: `reasonix acp`

## Governance Rule

Workers are execution agents, not governance agents.

They may implement and verify within declared scope, but they must not:

- mark phase completion
- alter global state files
- release blocked capabilities
- self-approve L2/L3 actions

## Default Recommendation

Use external workers as **L1 execution workers** by default.

For L2/L3 tasks:

- let the worker prepare the change
- let the coordinator release the gated step
- let the reviewer close the task

## Operational Records

- Put live dispatch records in `.omo/workers/runs/`.
- Use `templates/worker-dispatch-record.yaml` as the run ledger.
- Use `templates/worker-approval-record.yaml` whenever L2/L3 release is requested.
- Use `templates/worker-reclaim-note.md` whenever a worker is reclaimed.
- Use `runbooks/pilot-dispatch-and-reclaim.md` as the first operational playbook.

Generate the canonical promotion history surface:

```bash
python3 scripts/omo_worker.py task promotion-history --omo-dir .omo
```

This writes:

1. `.omo/workers/promotion/current.yaml`
2. `.omo/workers/promotion/current.md`

Generate the canonical promotion readiness surface:

```bash
python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo
```

This writes:

1. `.omo/workers/promotion/readiness.yaml`
2. `.omo/workers/promotion/readiness.md`

Human-approved planned packets need a task-specific promotion approval record:

1. `.omo/workers/templates/worker-promotion-approval.yaml`
2. shared backlog-presence notes are informative only and do not authorize promotion
3. request a task-specific record with `python3 scripts/omo_worker.py task promotion-request-approval <TASK_ID> --requested-by <ACTOR> --now <ISO8601> --omo-dir .omo`
4. the command writes `.omo/workers/runs/<TASK_ID>-promotion-approval-<STAMP>.yaml` and `.omo/_truth/task-center/proposals/<APPROVAL_ID>-proposal.yaml`
5. while that record stays `approval_status: requested`, readiness continues to report `approval_invalid`

Canonical promotion approval closure surface:

1. `python3 scripts/omo_worker.py task promotion-approval-status --omo-dir .omo [--task-id <TASK_ID>] [--now <ISO8601>]`
2. operators then run `python3 scripts/omo_governance.py approve <PROPOSAL_ID> --approver <ACTOR> --now <ISO8601>`
3. then run `python3 scripts/omo_governance.py apply <PROPOSAL_ID> --now <ISO8601>`
4. after apply, re-run `promotion-readiness` to confirm the approval blocker is gone

Canonical promotion approval history/index surface:

1. `python3 scripts/omo_worker.py task promotion-approval-history --omo-dir .omo [--now <ISO8601>]`
2. this writes `.omo/workers/promotion/approvals/history/current.yaml`
3. and `.omo/workers/promotion/approvals/history/current.md`

Canonical promotion approval analytics surface:

1. `python3 scripts/omo_worker.py task promotion-approval-analytics --omo-dir .omo [--now <ISO8601>]`
2. this reads `.omo/workers/promotion/approvals/current.yaml`
3. this reads `.omo/workers/promotion/approvals/history/current.yaml`
4. this writes `.omo/workers/promotion/approvals/analytics/current.yaml`
5. and `.omo/workers/promotion/approvals/analytics/current.md`

Canonical governance overlay surface:

1. `python3 scripts/omo_worker.py task governance-overlay-status --omo-dir .omo [--now <ISO8601>]`
2. this reads `.omo/_control/governance-overlay/current.yaml`
3. this reads `.omo/_truth/governance-overlay/roadmap.yaml`
4. this reads `.omo/_truth/governance-overlay/autopilot-policy.yaml`
5. this writes `.omo/workers/governance-overlay/current.yaml`
6. and `.omo/workers/governance-overlay/current.md`

Canonical governance overlay autopilot loop:

1. `python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor <ACTOR> [--now <ISO8601>]`
2. this reads the governance overlay current control/policy/roadmap inputs
3. this only advances `.omo/tasks/planned/*.yaml` target refs in v1
4. this reuses `promotion-request-approval` or `promote-apply` semantics instead of bypassing existing gates
5. this writes `.omo/workers/runs/governance-overlay-<STAMP>.yaml`
6. and refreshes `.omo/workers/governance-overlay/current.yaml`

When the current roadmap item is already `in_progress`, `governance-overlay-run-next` no longer scans a new pending candidate first. It continues the current active roadmap item, writes `mode: continue_active` into the run artifact, and can close a finished roadmap item and advance control state.

Within `continue_active` mode, the canonical overlay status may now recommend:

1. `dispatch:<TASK_ID>` when an active task is still `pending` and safe preclaim/dispatch should happen next
2. `verify:<TASK_ID>` when an active task has reached `review` and the coordinator should verify/close it next
3. `monitor:<ROADMAP_ITEM_ID>` while active work is still in flight
