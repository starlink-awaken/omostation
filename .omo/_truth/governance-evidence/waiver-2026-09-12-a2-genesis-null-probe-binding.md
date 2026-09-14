---
schema_version: governance-evidence/v1
type: binding-waiver
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-11
created: 2026-09-11
bet_id: BET-Y1Q4-T10-144
spec_version: 1.2.0
---

# Waiver — A2 Spec 1.2.0 genesis NULL probe binding

Non-union replacement of BET-Y1Q4-T10-144 accepted binding from Spec 1.1.0
(gitlink-only) to Spec 1.2.0 (two child paths: `status.py` +
`test_resident_status.py`).

## Reason

Live `resident status` reports `chain broken at read-only probe` on the
production ledger even though `LedgerBroker.verify_chain` and host diagnosis
`a2-t10-144-host-canary-20260909T193729Z` prove the chain is healthy with
genesis `previous_hash=NULL`. Spec 1.1.0 cannot authorize the probe fix.

## Scope

- Authorize only the two named child paths.
- Reject reuse of 1.1.0 WorkPacket / gitlink-only surfaces.
- Root gitlink bump remains a separate successor transaction after child merge.

## Non-authorization

Does not authorize host mutation, ledger rewrite, WAL checkpoint from status,
completion/value evidence, or A6–A9 work.
