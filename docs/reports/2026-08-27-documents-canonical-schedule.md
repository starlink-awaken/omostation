---
type: ephemeral
created: 2026-09-03
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

## 2026-08-28 candidate verification

The candidate was reviewed on the current main checkout after T10-23 and
T10-24 became complete. It is an overlay containing exactly two active lines:
daily `06:25` consumer audit and Monday `06:35` freshness audit. The other
Documents execution families are explicitly excluded and remain unchanged on
the host.

Dry-run evidence:

- `consumer-audit --documents-root /var/empty --crontab /dev/null
  --launch-agents-root /var/empty --scheduled-root /var/empty --json` returned
  exit `0`, status `ok`, total `0`, unmatched `0`.
- `freshness-audit --documents-root /var/empty --json` returned exit `2`,
  status `unavailable`, preserving fail-closed input-error semantics.
- Static schedule check passed: `STATUS: NOT INSTALLED`, exact cadence present,
  two active lines only, and no active Documents-local executable path.

No host crontab, LaunchAgent, Scheduled skill, or Documents content was
modified. Installation remains a separate human-gated operation requiring an
exact crontab backup and one-cycle observation.
