---
schema_version: specification/v1
spec_version: 1.0.0
title: Recent workspace documentation convergence
bet_id: BET-Y1Q4-T10-168
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-17
last-reviewed: 2026-09-17
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
type: ssot
---

# Recent workspace documentation convergence

## Background and problem

The 2026-09-02 through 2026-09-16 delivery wave added authoritative
specifications and runtime capabilities faster than the hand-maintained
navigation documents were updated. Several root pointers and stable
architecture descriptions therefore omit recent delivery surfaces or retain
counts that the documentation contract says must not be hard-coded.

## Scope

- Update `docs/SYSTEM-INDEX.md` with current authoritative pointers and replace
  stale scene and Journey counts with a live-count pointer.
- Register the recent accepted specifications in
  `docs/superpowers/specs/README.md`, preserving its registry semantics.
- Add the delivered Resident Flight Deck pointer to
  `docs/architecture/resident-agent-system-v1.md`.
- Regenerate supported documentation indexes only when their generators
  produce a focused, reviewable diff; do not hand-edit generated output.
- Validate cross-references, document lifecycle metadata, and repository gates.

## Non-goals

- Do not edit runtime projections, `.omo/state/**`, `BRIEF.md`, or concurrent
  agent artifacts.
- Do not modify submodule contents or pointers.
- Do not redesign the accepted A8, ledger-hardening, or Flight Deck specs.
- Do not convert the specification registry to a generated index in this BET;
  record that as a follow-up if the current manual registry remains too costly.

## Acceptance criteria

1. Every pointer added by this BET resolves to an existing authoritative file.
2. `docs/SYSTEM-INDEX.md` no longer hard-codes stale scene or Journey counts.
3. The recent accepted specifications covered by this delivery wave are
   discoverable from the specification registry.
4. The resident architecture contract names Flight Deck as a delivered
   surface without claiming BOS or CLI integration that does not exist.
5. Documentation lint, cross-reference checks, and the local governance gate
   pass, with unrelated pre-existing dirty state excluded from the diff.

## Verification commands

```text
python3 bin/ssot/doc-ssot-lint.py --json
python3 bin/ssot/doc-governance-check.py --json
python3 bin/ssot/check-index-drift.py
python3 bin/ssot/check-cross-refs.py
python3 bin/ssot/dir-hygiene-check.py
make gac-local-gate
```
