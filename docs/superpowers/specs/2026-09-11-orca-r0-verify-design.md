---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-11
last-reviewed: 2026-09-11
title: Orca R0 read-only admission verify toolchain
bet_id: BET-Y1Q4-T10-149
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: true
---

# Orca R0 read-only admission verify toolchain

## 1. Status and authority

Accepted contract for `BET-Y1Q4-T10-149`. Version 1.0.0 authorizes exactly:

```text
bin/gac/orca-r0-verify.py
```

R0 means **observer / admission evidence only**. This Spec does not admit Orca
as a writer control plane and must not create runs, start/stop/abandon/release
workers, dispatch tasks, or resolve gates.

## 2. Goals

1. One reproducible verifier: `python3 bin/gac/orca-r0-verify.py --json`.
2. Define and check **3 R0 transactions** on at least one settled sample.
3. Emit a historical settlement reconciliation report (`reconciled` /
   `mismatch` counts) from `orca orchestration worker-list --json`.
4. Assert accepted `worker_done` (worker.state=succeeded, stage settled when
   present) and resource reclaim (`terminalState` in {released, reclaimable})
   via read-only `worker-show`.
5. Exit 0 only when readiness probes, ≥1 accepted R0 triple, settlement report,
   and write-argv guard all pass.

## 3. Non-goals

- No Orca writer admission; do not modify `bin/gac/orca-codex-supervisor.py`.
- No Multica/A8/A9 work; no host Claims Task 16 activation.
- Global retained-after-success inventory may be non-zero; report it, but overall
  pass requires at least one clean accepted triple, not global zero.

## 4. R0 three transactions

| # | id | evidence | expected |
|---|---|---|---|
| TX1 | dispatch_identity | `worker-list` row + `worker-show` | `dispatchId`, `runId`, `taskId` present; dispatch.status completed/failed recorded |
| TX2 | worker_done_accepted | `worker-show` | `worker.state=succeeded` and (`worker.stage=settled` OR dispatch completed) |
| TX3 | resource_reclaimed | `worker-show` / list row | `terminalState ∈ {released, reclaimable}` |

## 5. Read probes

| id | argv |
|---|---|
| status | `orca status --json` |
| run_list | `orca orchestration run-list --json` |
| worker_list | `orca orchestration worker-list --json --limit 100` |
| worker_show | `orca orchestration worker-show --dispatch <id> --json` |
| host_list | `orca host list --json` |
| environment_list | `orca environment list --json` |

## 6. Settlement report

From `worker-list` rows:

- `reconciled`: workerState in {succeeded, stopped, failed, cancelled, abandoned}
  AND terminalState in {released, reclaimable}
- `mismatch`: workerState in done-like set AND terminalState in
  {active, retained, release_pending, release_unknown}
- `unsupervised` / other rows counted separately

## 7. Circuit breaker

If any argv would mutate Orca orchestration state (run-create, worker-start,
worker-stop, worker-abandon, worker-release, worker-retain, dispatch,
gate-resolve, reset, send, ask, …), stop immediately. Static scan of the
verifier must find none of those tokens in executed argv literals.

## 8. Acceptance

- `python3 bin/gac/orca-r0-verify.py --json` exits 0 on a ready local Orca.
- JSON includes `r0_transactions.accepted >= 1`, settlement
  `reconciled`/`mismatch` counts, and `trust.write_argv_guard.ok=true`.
