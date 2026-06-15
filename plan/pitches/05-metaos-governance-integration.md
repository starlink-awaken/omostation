# Pitch: Integrate Metaos into the OMO Governance Plane

## 🎯 The Why (Problem & Opportunity)
The `metaos` project, a crucial decision-making component of the engine layer, is currently operating outside the jurisdiction of the system's core governance framework. It completely lacks a `.omo/` governance plane, meaning it bypasses phase tracking, task lifecycles, and technical debt audits. This inconsistency creates a dangerous "blind spot" in the control plane, violating the principle of universal OMO governance.

## 🚧 The What (Solution Overview)
Establish the `.omo/` governance structure for the `metaos` project to ensure it adheres to the universal control protocols.

1.  **Initialize Plane:** Create the standard `.omo/` directory structure within the `projects/metaos/` hierarchy (Truth, Knowledge, Delivery, Control planes).
2.  **Register with Kernel:** Integrate `metaos` into the root OMO kernel's tracking mechanisms, ensuring it participates in system-wide audits and debt reporting.
3.  **Backfill Metadata:** Generate the necessary initial state files (e.g., `boulder.json`, `INDEX.md`, standard constraints) to align `metaos` with the current evolutionary phase of the overall ecosystem.

## 📏 Boundaries & Appetites
-   **Appetite:** 2 Days (Low complexity, administrative alignment).
-   **No-Gos:** Do not alter the functional code of `metaos` during this task. This is purely a governance configuration effort.

## ⚠️ Rabbit Holes & Risks
-   **Audit Failures:** Upon initialization, the strict OMO audit rules might immediately flag existing technical debts within `metaos` that were previously hidden. We must be prepared to triage and catalog these new findings appropriately without stalling the integration.