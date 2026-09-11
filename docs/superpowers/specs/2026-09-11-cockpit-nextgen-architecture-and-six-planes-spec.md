---
schema_version: specification/v1
spec_version: 1.0.0
title: Cockpit-UI Next-Gen Architecture & Six-Planes Convergence Spec
bet_id: BET-Y1Q4-T8-24
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-11
---

# Cockpit-UI Next-Gen Architecture & Six-Planes Convergence Spec

## 1. Problem & Context
Currently, `projects/cockpit-ui` contains 40+ flat routes, 60+ lazy-loaded components, and 8 unassimilated workbenches, leading to extreme cognitive overload and maintenance costs.
Simultaneously, the project observatory running on port 43191 (`zhixing-dashboard`) has established high-fidelity SSOT data collection (42 skills, 25 workflows, 8 intent routes, 6 memory tiers, 302 BOS services, 1248 capabilities, 46 documents, and 3Y-BET-LEDGER), but is bottlenecked by monolithic 7.1MB JSON snapshots and raw string-based DOM rendering without execution loops.

## 2. Goals & Convergence Principles
1. **Route B Single Control Plane Convergence**:
   Migrate verified collector and query engine logic from `~/.local/share/zhixing-dashboard/` into `projects/cockpit/src/cockpit/observatory/`.
   Provide `/api/v1/observatory/{manifest, summary, entity, neighbors, brief, stream}` with SSE incremental streaming and exact generation pinning.
   Deprecate fragmented legacy endpoints under `cockpit/web/`.
2. **Six Planes Strictly Decoupled in Data Layer**:
   Control Plane, Knowledge Plane, Business Plane, Evolution Plane, Collaboration Plane, Delivery Plane each backed by an isolated Zustand Store.
3. **Dual-Axis Spatial Model in UI Layer**:
   Do not stack 6 horizontal tabs (anti-pattern). Instead:
   - **3 Primary Workspaces**:
     - `Mission` (Delivery + Macro Evolution + Control Summary)
     - `Operations` (Business Cases + Collaboration Flow + HITL Signatures + PersistentQueue)
     - `Studio` (Deep #know: 6 Memory Tiers + 42 Skills Mesh + 302 BOS Debugger + Doc Vault)
   - **Faceted Plane Lenses**: Global shortcut `L` toggles attribute filters.
   - **Causal Inspector**: Global 480px slide-out drawer revealing all 6 planes for any entity.

## 3. Sub-BET Breakdown & Milestones
- `BET-Y1Q4-T8-24A`: Observatory Unified Engine (projects/cockpit)
- `BET-Y1Q4-T8-24B`: 6-Planes Store & ⌘K Command Palette (projects/cockpit-ui)
- `BET-Y1Q4-T8-24C`: Studio & Knowledge Deep Dive (#know)
- `BET-Y1Q4-T8-24D`: Operations & Mission Workbenches
- `BET-Y1Q4-T8-24E`: A9 Observability Gate Final Verification & 43191 Retirement

## 4. Verification & Gates
- All unit tests passing in `projects/cockpit` and `projects/cockpit-ui`.
- Full parity verification between new Cockpit and port 43191 data points.
- Local governance gate `make gac-local-gate` 100% green.
