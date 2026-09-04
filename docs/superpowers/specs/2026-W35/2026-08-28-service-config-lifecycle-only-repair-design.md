---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-28
last_updated: 2026-08-28
bet_id: BET-Y1Q3-T10-43
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Service declaration lifecycle-only repair

## Objective

Restore deterministic service-config validation and generation. The five OMO
governor/verifier/replay/alert/status records are lifecycle observations, not
installed launchd jobs; they must not generate machine plist files.

## Contract

- Lifecycle-only launchd records declare `generate: false` and are skipped by
  plist generation/check.
- Every enabled launchd record that does generate a plist must include a label
  and a complete program declaration; validation rejects an incomplete record
  before generation.
- `--check` reports structured drift or validation failure and never raises a
  `KeyError` for registry input. Existing host plist drift remains visible and
  is not reclassified as a passing result by this repair.
- When the host launchd observer directory is absent (for example on Linux CI),
  `--check --json` returns a structured `launchd_observer_unavailable` skip
  after declaration validation; it does not fabricate plist drift.
- No host plist, launchctl state, or service process is changed by this BET.

## Verification

1. Focused tests cover lifecycle-only skip and a missing-label generated
   launchd record.
2. `gen-service-configs.py --validate --json` passes; `--check --json` may
   return drift but completes without an unhandled exception.
3. A missing host observer skips only byte comparison; malformed generated
   launchd declarations still fail validation.
4. Existing generated service declarations remain byte-compatible.
