# Pitch: Phase 7 - Cockpit Convergence & Spine Visualization

## 🎯 The Why (Problem & Opportunity)
We have successfully built the "Three Spines" of eCOS v6 (Memory, Swarm, Compute). However, these are deeply infrastructural (L0-L2). The user facing layer (`projects/cockpit` and CLI dashboards) remains largely unaware of this rich topology. Operators cannot easily see which Swarm nodes are online, what the global token budget is, or visually trace a `bos://memory/all-search` request traversing the network. The immense power of the system is hidden behind terminal logs.

## 🚧 The What (Solution Overview)
Upgrade the L3 Entry layer (`cockpit`) to surface the real-time state of the Spines.

1.  **Swarm Radar:** Build a visual topology map or CLI dashboard widget showing all registered Swarm nodes, their roles, and their active BOS URIs.
2.  **Budget Telemetry:** Integrate the `quota_ledger` directly into the Cockpit, displaying real-time token consumption, remaining global budget (USD), and recent OMO budget debts.
3.  **Memory Explorer:** Create a unified search interface in the Cockpit that directly binds to the `bos://memory/local/all-search` aggregated endpoint, allowing users to query KOS, gbrain, and Vault from a single input box.

## 📏 Boundaries & Appetites
-   **Appetite:** 1 Week (Medium complexity, primarily UI/UX and API aggregation).
-   **No-Gos:** Do not rebuild the underlying Spines to fit the UI. The UI must adapt to the existing asynchronous MCP/BOS protocols.

## ⚠️ Rabbit Holes & Risks
-   **Performance Degradation:** Polling the Swarm and Quota Ledger too aggressively from the Cockpit could introduce unnecessary load. We must utilize event-driven (SSE) architectures or efficient caching (`bos_cache`).