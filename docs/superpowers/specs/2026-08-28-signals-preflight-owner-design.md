---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-33
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Signals preflight owner design

## Objective

Replace the scheduled Documents `@公共/_runtime/signals-rotate.py` writer with
a Workspace-owned, read-only preflight. The old script rewrites
`@驾驶舱/_control/SIGNALS.md` and appends machine-signal records under
`@驾驶舱/_generated`; both are Documents writes and are outside the content
plane boundary.

## Contract

The existing `bin/gac/documents-domain-owner-job.py` entrypoint dispatches
`signals-preflight`. The owner reads the canonical Documents SIGNALS.md,
classifies machine versus human entries using the legacy source vocabulary, and
emits `documents.signals-preflight.v1`. It writes no Documents files.

Exit semantics are stable and truthful: `0` means the input is readable and no
machine signals require review; `1` means the input was read and findings exist;
`2` means the Documents root, SIGNALS.md, or Workspace evidence boundary is
unavailable. Evidence is written only below the Workspace runtime state root.

The owner is an observation/preflight surface, not a second signal ingress. OMO
resident and BCOS remain canonical owners for signal routing and execution. The
legacy writer stays available for rollback/parity until the cutover has been
observed.

## Acceptance

Tests prove missing-root fail-closed behavior, machine/human classification,
Workspace-only evidence publication, rejection of evidence inside Documents,
and no mutation of SIGNALS.md.
