# Pitch: Human-Machine Symbiosis (Atomic HITL Gate)

## 🎯 The Why (Problem & Opportunity)
Phase 6 (The Evolution Loop) empowers OMO to automatically generate remediation proposals (like modifying budgets or deleting redundant code) when technical debt is detected. However, executing these mutations blindly is too dangerous. We need an ergonomic way to preserve the "Human in the Loop" (HITL) without bogging down the automated analysis.

## 🚧 The What (Solution Overview)
Implement a `Transaction Approval Queue` within the L3 Cockpit layer to govern system mutations.

1.  **Mutation Envelope:** When the Evolution Loop (or any Agent) proposes a destructive action or configuration change, it creates a `MutationProposal` envelope saved to `.omo/state/proposals/`.
2.  **Cockpit UI:** Add an "Approval Queue" widget to the Web Dashboard. It lists pending proposals with a visual diff (what will change).
3.  **1-Click Execution:** The human operator reviews the proposal and clicks "Approve" or "Reject". If approved, the Cockpit API securely executes the mutation and marks the debt as resolved.

## 📏 Boundaries & Appetites
-   **Appetite:** 1 Week (Medium complexity, primarily UI and state management).
-   **No-Gos:** Do not build a complex branching approval logic. The flow is strictly binary: Approve (Execute) or Reject (Discard).

## ⚠️ Rabbit Holes & Risks
-   **Stale Proposals:** A proposal generated on Monday might be invalid by Wednesday if the underlying codebase changed. The execution engine must perform a "pre-flight conflict check" before applying an approved mutation to prevent corrupting state.