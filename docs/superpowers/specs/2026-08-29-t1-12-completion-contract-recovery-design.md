---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-53
risk_level: L1
---

# T1-12 completion contract recovery

## Objective

Restore the required `workflow` and `write_surfaces` fields for
`BET-Y1Q3-T1-12` after a mainline synthesis removed them while marking the BET
done. Preserve the existing accepted Spec, completion matrix, canary report,
and principal value attestation byte-for-byte.

## Contract

- T1-12 must remain bound to `bet-execution` and its canonical WorkPacket
  write-surface list.
- This repair restores contract metadata only; it does not promote, downgrade,
  or reinterpret any completion axis.
- No historical digest mismatch outside T1-12 is fixed in this slice.
- The repair adds no dispatcher, registry, scheduler, runtime state, or value
  writer.

## Acceptance

- `bet-ledger.py lint` no longer reports missing workflow/write_surfaces for
  T1-12.
- The restored fields match the accepted T1-12 WorkPacket scope.
- Focused spec/ledger tests, SSOT checks, and GaC pass.
