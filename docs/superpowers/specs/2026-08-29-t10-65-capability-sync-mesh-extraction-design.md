---
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-65
spec_version: 1.0.0
title: T10-65 Capability-sync mesh-verification extraction — Design
type: doc
---

# T10-65 Capability-sync mesh-verification extraction — Design

Date: 2026-08-29 · Bet: BET-Y1Q3-T10-65 · Risk: L1 · Appetite: 0.25 day

## Problem

`bin/capability-sync.py` grew to 1575 lines, tripping the god-module error
gate (>1500) and blocking PR #2551's interface-check.

## Design (move-only)

- Extract the bounded mesh-verification projector (425 lines:
  `_mesh_stat_fingerprint` … `verify_material_against_mesh`) into
  `lib/capability_sync_mesh.py` — the house sibling-module home already on
  `sys.path` via capability-sync's LIB bootstrap.
- Downshift the verification constants (VERIFICATION_*, MESH_LOG,
  MAX_MESH_LOG_BYTES, VERIFICATION_MESH_EVENT_STATES) into the mesh module
  as the single source; capability-sync imports them back at the top.
- Mesh module imports its primitives from the existing sibling libs
  (capability_trace_binding, capability_sync_verification_helpers,
  capability_native_*), preserving the one-directional
  capability-sync → mesh → libs graph.

## Verification

- capability-sync.py = 1483 lines (< 1500).
- Capability suites: sync 129 + native receipt/inspection/trace 124, green.
- `omo.cli lint schemas` 7/7; direct-omo-io PASS.

## Rollback

Revert the single commit; no data or behavior migration.
