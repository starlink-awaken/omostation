# Pitch: eCOS v6 Architecture Consolidation & SSOT Alignment

## 🎯 The Why (Problem & Opportunity)
Over the past several phases (Phase 2 through Phase 9), eCOS v6 has undergone massive structural evolution: the Memory Spine (aggregated search), Swarm Spine (A2A network, Ed25519 trust), Compute Spine (quota ledgers, budget intercepts), and the Cockpit Convergence (HITL gate). While the physical code is battle-tested and running, the L0 semantic models (MOF), cross-cutting governance standards (X1-X4), and project-level documentation (`AGENTS.md`) have drifted from this new reality. If we do not crystallize these changes into the Single Source of Truth (SSOT) now, future development will suffer from severe cognitive dissonance and architectural rot.

## 🚧 The What (Solution Overview)
Execute a full-stack crystallization pass to align the documentation, models, and registries with the physical code.

1.  **L0 Model Precipitation:** Update the `ecos/ssot/mof/m1` nodes to formally define the new Spines (e.g., declaring `A2ANetworkTransport` and `EvolutionLoop` as core components).
2.  **X1-X4 Governance Distillation:** Draft/update the definitive `.omo/standards/` documents for the four cross-cutting concerns based on our physical implementations:
    *   **X1 (Security):** Ed25519 Swarm signatures and node identity.
    *   **X2 (Consistency):** The `llm_quota_ledger.jsonl` atomic deduction flow.
    *   **X3 (Value Alignment):** MetaOS Admission Gate criteria (`declared_values`, `role` restrictions).
    *   **X4 (Observability):** The `MutationProposal` HITL envelope and OTLP requirements.
3.  **SSOT Sync (`AGENTS.md` & Registries):** 
    *   Update all `AGENTS.md` boundaries across `agora`, `runtime`, `aetherforge`, `cockpit`, and `omo` to document the correct `bos://` URIs and capabilities.
    *   Update `protocols/port-registry.yaml` to cement the 7422 (HTTP MCP) and 7455 (Swarm UDP) assignments.
4.  **Verification:** Implement a model-driven validation script to cross-check `AGENTS.md` BOS declarations against the active Agora routing table.

## 📏 Boundaries & Appetites
-   **Appetite:** 1 Week (Medium complexity, highly administrative but critical).
-   **No-Gos:** Do not introduce new functional code during this phase. This is strictly a documentation, modeling, and validation pass.

## ⚠️ Rabbit Holes & Risks
-   **Documentation Drift:** Updating multiple markdown files manually is prone to human error. We must rely on automated validation scripts (e.g., `check-interfaces.py` or a new BOS checker) to prove the documentation matches the code.