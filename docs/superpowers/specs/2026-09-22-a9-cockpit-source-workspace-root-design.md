---
schema_version: specification/v1
spec_version: 1.0.0
title: A9 cockpit source workspace-root execution
bet_id: BET-Y2Q2-T10-155
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-22'
last-reviewed: '2026-09-22'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
type: ssot
---

# A9 cockpit source workspace-root execution

## Problem

The A9 gate remains PARTIAL even though the strategy corpus repair is merged
and the other cockpit sources are healthy. Fresh projection evidence records
two unavailable sources:

- `workflow` invokes `bin/agent-workflow.py` with the dashboard repository as
  the effective working directory, where the path does not exist.
- `scheduler` invokes `bin/scheduler-compile.py` with the same wrong root.

The two collectors define `/Users/xiamingxing/Workspace` as `WORKSPACE`, but
pass a relative script path to `subprocess.run` without setting `cwd`. They
also invoke the dashboard virtual environment directly. That interpreter lacks
PyYAML, so merely changing the relative path to an absolute path would still
fail. This is an execution-root/runtime-selection defect, not evidence that the
underlying workflow or scheduler is unavailable.

## Evidence

- Authoritative dashboard source states:
  - `workflow=UNAVAILABLE`, with the failed path under
    `~/.local/share/zhixing-dashboard/bin/agent-workflow.py`.
  - `scheduler=UNAVAILABLE`, with the failed path under
    `~/.local/share/zhixing-dashboard/bin/scheduler-compile.py`.
- Canonical-root smoke proof, run read-only before this draft was written:
  - `bin/gac/managed-python run --profile pyyaml -- bin/agent-workflow.py observe --json`
    returned `ok: true`.
  - `bin/gac/managed-python run --profile pyyaml -- bin/scheduler-compile.py --check --json`
    returned `ok: true`.

## Proposed change

Create one explicit workspace-root contract for both collectors:

1. Resolve `ZX_DASHBOARD_WORKSPACE_ROOT` when set; otherwise use
   `/Users/xiamingxing/Workspace`.
2. Resolve the canonical `bin/gac/managed-python`, `bin/agent-workflow.py`, and
   `bin/scheduler-compile.py` paths from that root.
3. Invoke each command with `cwd` set to the canonical workspace root.
4. Use the root-managed `pyyaml` profile instead of the dashboard virtual
   environment. This preserves the repository-selected Python runtime and its
   PyYAML fallback contract.
5. Read workflow run inventory from the same resolved workspace root.
6. Preserve fail-closed source behavior: a missing executable, non-zero exit,
   invalid JSON, schema mismatch, or `ok=false` remains `UNAVAILABLE`; no
   collector may synthesize a green state.

The default root remains explicit for this personal Sovereign OS deployment. The
environment override exists for test isolation and future portability, not as a
second authoritative control plane.

## Required implementation surfaces

- `~/.local/share/zhixing-dashboard/collectors/workflow.py`
- `~/.local/share/zhixing-dashboard/collectors/scheduler.py`
- `~/.local/share/zhixing-dashboard/tests/test_collector_workspace_root.py`
- `docs/plans/3y-bet-ledger.yaml` for the future governed binding
- the matching new BET retrospective

No branch protection, Claims Authority activation, runtime scheduler definition,
second dispatcher, or governance queue may change in this transaction.

## Verification matrix

| Case | Required result |
| --- | --- |
| Default collector configuration | Uses the canonical workspace root, root-managed Python wrapper, absolute wrapper path, and `cwd=<workspace root>` |
| `ZX_DASHBOARD_WORKSPACE_ROOT` override | Uses the override consistently for command cwd, scripts, and workflow inventory |
| Missing managed wrapper or script | Collector returns `UNAVAILABLE`; it does not invoke the dashboard-local path |
| Workflow observe returns non-JSON, non-dict, `ok=false`, or changed schema | Collector returns `UNAVAILABLE` with a precise reason |
| Scheduler check returns non-JSON, non-dict, or `ok=false` | Collector returns `UNAVAILABLE` with a precise reason |
| Canonical commands succeed in a PyYAML-capable managed runtime | Both collector states become `OBSERVED` with `workflow.ok=true` and `scheduler.ok=true` |
| Existing healthy sources | Their states and evidence remain unchanged |

## Acceptance

1. `python3 ~/.local/share/zhixing-dashboard/tests/test_collector_workspace_root.py`
   exits 0.
2. `python3 ~/.local/share/zhixing-dashboard/tests/test_all_collectors.py`
   exits 0.
3. Fresh dashboard projection reports `workflow=OK` and `scheduler=OK`; no
   required cockpit source is `UNAVAILABLE`.
4. A fresh in-memory A9 gate calculation returns `PASS`, with ASD complete,
   cockpit projection fresh, and `bad_sources=[]`.
5. The future root ledger transaction lints, passes the governance gate,
   records a truthful retro, and keeps `value=NOT_PROVEN` unless separate
   qualifying user-value evidence exists.
6. The future implementation PR contains only the declared surfaces plus its
   governance evidence and required registry/ledger binding.

## Rollback

Revert the two collector modules and the new focused test, then refresh the
dashboard projection. The honest pre-repair state is A9 PARTIAL with
`workflow=UNAVAILABLE` and `scheduler=UNAVAILABLE`; rollback must not fake an
A9 PASS. The future BET stays blocked until its acceptance is re-proven.

## Review gate

This Spec is draft-only and is not implementation-authorized. It must not be
marked accepted, bound to a BET, implemented, or used to retire any clone until
the human review verdict and a fresh accepted-binding transaction exist.
