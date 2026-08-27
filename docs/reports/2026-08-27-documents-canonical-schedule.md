---
status: archived
lifecycle: history
owner: unassigned
last-reviewed: 2026-08-27
---
# Documents canonical schedule candidate — 2026-08-27

## Decision

The Workspace owner path is ready for two observation jobs only. The candidate
file is `.omo/cron/documents-content-plane-crontab` and is explicitly **NOT
INSTALLED**.

| Cadence | Current consumer | Candidate owner | Documents write | Status |
| --- | --- | --- | --- | --- |
| daily 06:25 | `@公共/_runtime/async-audit.py` | `documents-domain-owner-job consumer-audit` | none | candidate |
| Monday 06:35 | `@公共/_runtime/control-plane-freshness-audit.py --report` | `documents-domain-owner-job freshness-audit` | none | candidate |

The candidate preserves cadence and routes evidence/logs to Workspace. The
freshness owner currently returns exit 1 because all 12 domains lack a consistent
CLAUDE review-date declaration; this is intentional fail-closed behavior.

The remaining active Documents jobs (OCR, domain-sync, session-brief,
bridge-refresh, convergence, signals rotation, and legacy controller/predictor)
are not included. They require separate parity and rollback evidence.

## Installation gate

No host schedule was changed in this BET. Before installation, snapshot
`crontab -l`, compare the exact old/new matrix, run both commands manually, verify
Workspace evidence, install atomically, and observe one full trigger cycle. Roll
back by restoring the exact snapshot.
