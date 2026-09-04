---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0199: Unified BOS URI, Cockpit Integration & Cognitive Governance Workflow

## Status
Accepted

## Context
Following the implementation of the V2.0 Cognitive Mesh (Intent Compiler ADR-0195, Shadow Challenger ADR-0196, Sovereign Fabric ADR-0197, and Domain Cartridges ADR-0198), the system required a standardized, discoverable, and governed access plane. Without explicit BOS URI mappings, Cockpit terminal commands, Agora capability registry entries, and a formal Agent Workflow state machine, autonomous agents and human developers suffered from fragmented tool invocation and un-audited ad-hoc scripts.

## Decision
1. **BOS URI Standard Scheme**:
   - `bos://governance/intent/compile` (QPS: 20, cache_ttl: 15s)
   - `bos://governance/shadow/challenge` (QPS: 15, cache_ttl: 15s)
   - `bos://governance/cartridge/list` (QPS: 30, cache_ttl: 120s)
   - `bos://fabric/snapshot/manage` (QPS: 30, cache_ttl: 60s)
   - `bos://fabric/speculative/eval` (QPS: 20, cache_ttl: 15s)
2. **Agora & Capability Registry**:
   - Register `ecos-intent-compiler`, `ecos-shadow-challenger`, `ecos-domain-cartridge-factory`, and `omlxc-sovereign-fabric` into `projects/agora/src/agora/registry.yaml` and `docs/generated/capability-registry.yaml`.
3. **Cockpit Unified CLI Suite**:
   - Expose direct top-level and governance subcommands:
     - `cockpit intent "<prompt>" [--domain <dom>] [--json]`
     - `cockpit challenge <target> [--domain <dom>] [--auto-patch] [--strict]`
     - `cockpit cartridge [list|export|validate]`
     - `cockpit fabric [inspect|snapshot|speculative-eval]`
4. **First-Class Agent Workflow**:
   - Register `cognitive-governance-delivery.yaml` in `.omo/_truth/registry/agent-workflows/workflows/` defining the 6-phase deterministic execution state machine (Intent -> Compute Triage -> Cartridge -> Dual-Plane Draft -> Shadow Auto-Patch -> Facts Closeout).

## Consequences
- Unifies human interaction (Cockpit), agent tool-use (FastMCP), bus routing (BOS URI), and governed workflow state machine (ADR-0203/0204).
- Provides an auditable, replayable, and fail-safe lifecycle for vertical domain problem-solving.
