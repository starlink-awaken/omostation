schema_version: workflow-waiver/v1
waiver_id: WAIVER-2026-08-29-T10-62-OMO-GATE-BOOTSTRAP
issued_at: 2026-08-29T10:30:00Z
issued_by: user-authorized-agent
scope:
  bet_id: BET-Y1Q3-T10-62
  paths:
  - projects/omo
  - docs/plans/3y-bet-ledger.yaml
  - docs/superpowers/specs/2026-08-29-omo-ingress-gate-recovery-design.md
  - docs/reports/2026-08-29-omo-ingress-gate-recovery.md
  - .omo/_knowledge/retros/BET-Y1Q3-T10-62.md
  - .omo/_truth/governance-evidence/waiver-2026-08-29-t10-62-omo-gate-bootstrap.md
reason: User-authorized continuation of the Documents capability-downshift work; a separate OMO child gate recovery BET is required to remove the clean-CI blocker without widening the Documents or capability slices.
constraints:
- Only the existing ingress exemption and its regression coverage may change in the child; preserve negative detection.
- Root may update only the projects/omo gitlink plus T10-62 evidence surfaces.
- No Documents content, host schedule, runtime-state, capability, or dispatcher mutation.
- Formal workflow must be started, all write surfaces claimed, and child/root verification recorded before closeout.
expiry: 2026-08-30T10:30:00Z
