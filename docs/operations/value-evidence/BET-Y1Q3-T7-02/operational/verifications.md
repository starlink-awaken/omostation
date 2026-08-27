# T7-02 Operational Evidence: journey-validate + scene-card-lifecycle

## Verifications executed 2026-08-27

### make journey-check (executed)
```
$ make journey-check
✅ admin-notification-workflow.yaml: 7 states, 7 transitions
✅ health-medical-workflow.yaml: 4 states, 4 transitions
✅ inbox-to-decision.yaml: 9 states, 9 transitions
✅ intake-review-deliver-inbox.yaml: 0 states, 0 transitions
...
exit=0
```

### make scene-card-check --p1-only (executed)
```
$ make scene-card-check
scene-cards: ready=15 with-blockers=5 (P1 contract mode)
exit=0
```

Per-card check (4 health cards):
- docs/scene-cards/health-archive.yaml: ready=True
- docs/scene-cards/health-intake.yaml: ready=True
- docs/scene-cards/health-visit-prep.yaml: ready=True
- docs/scene-cards/health-visit.yaml: ready=True

## Live contract: 4 health scene cards each declare risk tier in notes

- health-intake: L0 (record) — risk_engine health.generate:report=L0
- health-visit-prep: L0 (report generation) — L2 if send_email:doctor (HITL)
- health-visit: L0 (record) — L2 send_email:doctor (HITL)
- health-archive: L0 (archive, confidential, local-only)

## Source

- verify.cmd (bet-ledger.yaml): make journey-check / make scene-card-check
- both exit 0 in worktree work/t7-02-health
