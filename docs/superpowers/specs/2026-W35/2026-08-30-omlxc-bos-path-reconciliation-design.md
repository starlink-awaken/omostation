---
schema_version: specification/v1
spec_version: 1.0.0
title: OMLXC BOS service path reconciliation
bet_id: BET-Y1Q3-T10-74
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# OMLXC BOS service path reconciliation

## Intent

Repair five active OMLXC BOS service declarations whose command paths no longer
match the canonical OMLXC repository layout. The capability URIs, action names,
security levels, and behavior remain unchanged.

## Contract

- In Agora's canonical `etc/bos-services.yaml`, the tree/stream/swarm actions
  resolve to `projects/omlxc/examples/live_nextgen_compute_engine_benchmark.py`.
- The dma/lora actions resolve to
  `projects/omlxc/examples/live_v5_evolution_verification.py`.
- Child Agora tests and the root evidence-smoke check prove all five commands
  resolve on a fully initialized tree.
- No new service, dispatcher, alias, or second registry is introduced.
