---
type: ephemeral
created: 2026-09-03
---

# T10-57 L4 live Documents content-plane audit stability

## Scope

This slice hardens the read-only L4 content-plane audit against a transient
filesystem change. It does not move, delete, quarantine, execute, or modify
anything below `/Users/xiamingxing/Documents`.

## Delivery evidence

- L4 child PR: `https://github.com/starlink-awaken/omostation-l4-kernel/pull/8`
- Child main after merge: `9bc9ca815089121199a550b9f81d8ec426acc4a3`
- Delivery tags: `delivery/t10-57-l4-audit-stability-20260829-v1` and `-v2`
- Change: complete audit attempts retry up to three times only for stability
  failures; persistent instability remains non-zero and exposes
  `stability_attempts` in the existing JSON result.

## Verification

- RED test reproduced the previous behavior: one transient tree change caused
  an immediate `L4-CONTENT-011` failure.
- L4 targeted tests: content-plane, CLI contract, and archive suites passed.
- L4 full test suite passed on the isolated child clone; Ruff and format checks
  passed in CI on Linux and macOS.
- Real Documents read-only command returned a bounded fail-closed result after
  `stability_attempts: 3`:

  `content tree directory changed during enumeration: /Users/xiamingxing/Documents`

This proves retry and truthful failure behavior. It does not prove a stable
full-tree inventory because the live root continued to change during all three
attempts. A diagnostic scan observed the root directory metadata change after
21,291 visited directories; the current root-level `ZCode` directory was the
most recently modified top-level entry. No content write was performed by the
audit.

## Remaining physical-purification boundary

The migration registry still contains 16 families, with only
`public-runtime` and `cockpit-runtime` marked `in_progress`. The remaining
families require family-scoped stable evidence, consumer proof, and reversible
quarantine before any physical move. The old Documents execution material is
therefore intentionally retained.

## Rollback

The child change is isolated to the L4 audit implementation and tests. Revert
the root gitlink to the previous reachable L4 main if the CI or downstream
contract checks identify an incompatibility; no Documents rollback is needed.
