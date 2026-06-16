# Pitch: Deep Scenario - Swarm-Native Deep Research Pipeline

## 🎯 The Why (Problem & Opportunity)
The infrastructure is ready, but it lacks a "killer app" to prove its worth. We need a complex, cross-domain scenario that stresses the Memory Spine, Swarm Spine, and Compute Spine simultaneously. A standalone "Deep Research" task—where an agent gathers broad context, delegates specialized analysis to remote nodes, aggregates knowledge, and stays strictly within a token budget—is the ultimate crucible for eCOS v6.

## 🚧 The What (Solution Overview)
Implement a native `Deep Research` workflow leveraging the distributed eCOS architecture.

1.  **Distributed Dispatch:** A Planner Agent receives a broad research topic. It uses the `Compute Spine` to ensure it has the budget to proceed.
2.  **A2A Delegation:** The Planner breaks the topic into sub-topics and uses the `Swarm Spine` (via `A2ANetworkTransport`) to dispatch parallel tasks to available Worker nodes.
3.  **Global Memory Recall:** Worker nodes use the `Memory Spine` (`bos://memory/local/all-search`) to pull historical facts from `gbrain` and `KOS` to inform their analysis.
4.  **Synthesis:** Workers report back to the Planner, who synthesizes a final report and persists the newly generated knowledge back into the Memory Spine via atomic JSONL/Postgres commits.

## 📏 Boundaries & Appetites
-   **Appetite:** 2 Weeks (High complexity, highly integrative).
-   **No-Gos:** Do not build bespoke communication channels for this feature. It MUST strictly use the existing `BOSRouter`, `A2ATransport`, and `FastMCP` infrastructure.

## ⚠️ Rabbit Holes & Risks
-   **Timeout Hell:** Complex distributed workflows are highly susceptible to cascading timeouts if a single worker node hangs. Rigorous use of `bos_circuit_breaker` and timeout configurations is essential.
-   **Budget Explosions:** Recursive agent spawning could rapidly drain the global LLM budget. The Planner must allocate strict local sub-budgets to each Worker.