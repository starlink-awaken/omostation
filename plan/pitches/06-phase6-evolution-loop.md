# Pitch: Phase 6 - The Evolution Loop (Auto-Remediation)

## 🎯 The Why (Problem & Opportunity)
Currently, eCOS v6 boasts robust governance (e.g., generating OMO debt files when the compute budget is exhausted or an architectural rule is violated). However, this governance is *passive*. Human intervention is still required to read the `.omo/debt` YAML files and enact fixes (e.g., adjusting budgets, changing models, refactoring code). To achieve true "System Autonomy," eCOS must close the loop: Agents should be able to read their own debt records and automatically propose remediations (PRs) or runtime adjustments.

## 🚧 The What (Solution Overview)
Implement the "Evolution Loop" to transition OMO Governance from Passive to Active.

1.  **Debt-Triggered Workflows:** Create a new OMO Kernel daemon that watches `.omo/debt/items/*.yaml`.
2.  **Auto-Remediation Agents:** When a specific debt (like `BUDGET_EXHAUSTED`) is detected, automatically dispatch a Swarm task to a specialized "Governance Agent".
3.  **Self-Correction Proposals:** The Governance Agent analyzes the context and proposes a fix (e.g., generating a PR to adjust `RUNTIME_LLM_BUDGET_USD` or downgrading the default model in `registry.yaml`), which is then sent to the human operator for 1-click approval via the Cockpit.

## 📏 Boundaries & Appetites
-   **Appetite:** 2 Weeks (High complexity, requires Agent orchestration).
-   **No-Gos:** Fully autonomous code merging without human approval is strictly forbidden in this phase (HITL - Human in the Loop is mandatory).

## ⚠️ Rabbit Holes & Risks
-   **Infinite Repair Loops:** An Agent might propose a fix that introduces a new debt, causing an endless cycle of self-repair. Strict circuit breakers and max-retry limits must be enforced on the Evolution Loop.