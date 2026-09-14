---
id: waiver-2026-09-12-t10-157-spec-exact-blob-recovery
scope: docs/superpowers/specs/2026-09-12-t10-157-aetherforge-responses-pointer-close.md
created: 2026-09-12
owner: governance-team
status: active
---

# BET-Y1Q4-T10-157 accepted-spec exact-digest recovery waiver

## Authority and boundary

Under the user's time-bounded delegation for autonomously repairing
post-merge truth regressions, this managed successor changes only the
accepted-spec path and this waiver. It does not modify the Ledger,
completion/value evidence, gitlinks, runtime, CI, branch protection, or
implementation code.

## Reason for one-time start exemption

The canonical claims run is unbound because the Ledger marks
`BET-Y1Q4-T10-157` as `done`; a bound rerun is rejected by
`BET_STATUS_NOT_STARTABLE`. `AGCP_REQUIREMENT_ITERATION_GATE=0` was used
once, only to start canonical run
`20260912T073417Z-project-doc-change-eb813d27`. Claims, verification, Git,
CI, merge, and closeout use default gates.

## Exact-object recovery

The Ledger binds SHA-256
`c3216a927df7db567d0f6b1be4de3c5809ba3f4b8cf14cdf2bd815d34538577e`,
which is Git blob
`153a364e1f7a1f709d3b7aee0a7ffab9cba70090`. After #3651, main contained a
semantic rewrite whose SHA-256 is
`8146d44578a88c557b4351faf5479a1ca713d57ddd3836cca28a183b2db8a96e`;
general ledger lint did not reject the digest drift. This successor
restores the exact bound object without changing the binding.
