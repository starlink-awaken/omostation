---
schema_version: family-dashboard-canary-approval/v1
bet_id: BET-Y1Q3-T10-122
approved_at: 2026-09-02T07:34:24Z
expires_at: 2026-09-03T07:34:24Z
owner: human
lifecycle: history
last_updated: 2026-09-02
---

# Family dashboard Phase B Documents write canary approval

## Human authorization

The operator replied `批准` immediately after the exact canary target,
proposal ID, proposal digest, create-and-rollback behavior, and remaining
credential prerequisite were presented. This approval authorizes only the
transaction bound below; it does not authorize existing-household-document
writes, Phase C cutover, legacy cleanup, or a persistent service.

## Exact transaction binding

- Target: `/Users/xiamingxing/Documents/@家庭生活/_meta/family-dashboard-write-canary.md`
- BOS target: `documents://family/_meta/family-dashboard-write-canary.md`
- Proposal ID: `family-dashboard-phase-b-canary-20260902`
- Proposal digest: `sha256:75a358adb4122a886c354a1cbdffdc723b27be7ad8efb341dfe5d40c84e6ff31`
- Payload digest: `sha256:f558a1b71cdf0a907be5025c63b9bc28122998b392915bc287b237d0a8384234`
- Expected precondition: the target is absent; source bytes are empty with
  SHA-256 `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Runtime root: `/Users/xiamingxing/Workspace/runtime/family-hub/dashboard`
- Source fingerprint: `sha256:a8e2f11c48b1c7793b28eae01632d9b271a68ad6749a98abff737068bfb77034`

## Required execution and rollback

Cockpit must supply a server-owned authorized principal and submit the exact
proposal through the approved OMO/Agora/family-hub path. The owner may create
the target only after all CAS checks pass, must verify the created bytes, and
must roll back within the same transaction to verified absence. Immutable OMO
and family-hub apply, verify, and rollback receipts are required. A missing
Cockpit credential, proposal/payload digest drift, non-absent target, source
drift, receipt collision, or rollback failure stops execution.
