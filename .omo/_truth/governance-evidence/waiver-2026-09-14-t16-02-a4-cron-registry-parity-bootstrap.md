---
id: waiver-2026-09-14-t16-02-a4-cron-registry-parity-bootstrap
scope: BET-Y1Q4-T16-02 A4 remote-hygiene cron registry parity recovery
created: '2026-09-14'
owner: governance-team
status: active
lifecycle: history
last-reviewed: '2026-09-14'
type: governance-evidence
---

# T16-02 governance-state bootstrap waiver

## Authority

The active recovery objective requires A1–A9 execution-environment repair.
PR #3777 established the accepted `BET-Y1Q4-T16-02` specification binding and
initial candidate matrix at merge `600abfb33818dc0d45ba5c7d7e00223ce24f9bc4`.

The canonical `/Users/xiamingxing/Workspace` remained a concurrent, dirty, and
stale shared tree, so the governance-state successor lane was delivered from
managed clone `t16-02-a4-cron-parity-20260914-05`. Its unbound workflow start
used `AGCP_REQUIREMENT_ITERATION_GATE=0` once only. Every claim, edit,
verification, Git operation, PR, required check, merge, and closeout uses the
default gates.

Claims use canonical Workspace authority and directory-level claims for new
evidence and retro files:

- `.omo/cron/registry.yaml`
- `.omo/_truth/governance-evidence`
- `.omo/_knowledge/retros`

## Recovery boundary

- Register the already installed `remote-hygiene-hourly` job exactly, including
  its stable cron comment suffix.
- Do not change the installed schedule, command, crontab state, script, or
  runtime behavior.
- Do not add or alter a known-orphan allowlist.
- Do not modify the Ledger in this governance-state lane.
- Do not claim A6, A7, A8, A9 admission, business value, or overall completion.

## Verification and rollback

The declaration is accepted only when scheduler parity reports
`drift_count=0, orphan_count=0`, Ledger lint remains clean, and the governance
checks pass. Rollback is limited to reverting this declaration, waiver, and
retro; no runtime rollback is required.
