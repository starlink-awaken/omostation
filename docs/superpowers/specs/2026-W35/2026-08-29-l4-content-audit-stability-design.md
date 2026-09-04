---
schema_version: specification/v1
spec_version: 1.0.0
title: L4 live content-plane audit stability
bet_id: BET-Y1Q3-T10-57
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# L4 live content-plane audit stability

## Intent

Make the read-only L4 Documents content-plane audit useful on a live filesystem
without weakening its fail-closed drift detection. A transient directory change
must be retried as a complete audit attempt; a tree that remains unstable must
still produce a non-zero, explicit stability finding.

## Constraints

- Keep the existing classification rules, no-follow behavior, archive checks,
  and symlink revalidation unchanged.
- Retry only stability failures caused by a tree changing during enumeration or
  revalidation; malformed archives and filesystem errors remain failures.
- Never return a successful or partial audit from an unstable attempt.
- Do not write, move, delete, quarantine, or execute anything under Documents.
- Keep the public CLI envelope and existing callers backward compatible.

## Acceptance

- A single transient tree mutation is retried and a stable second attempt
  returns the complete deterministic classification.
- Persistent tree mutation remains fail-closed and reports the bounded attempt
  count and stability reason.
- Existing content-plane and CLI contract tests remain green.
- The migration checker can consume a stable live audit instead of treating a
  single transient drift as an empty candidate inventory.
