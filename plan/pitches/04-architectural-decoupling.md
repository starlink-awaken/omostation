# Pitch: Disentangle Agora and Ecos Dependency Cycles

## 🎯 The Why (Problem & Opportunity)
The system suffers from architectural decay via P1 dependency cycles and excessive coupling. Notably, a cyclic dependency exists between the foundational protocol layer (`ecos`, L0) and the service mesh (`agora`, I0). Furthermore, `agora` is heavily coupled with multiple `kairon` packages, turning it into a "God Object." This entangled state breaks layer isolation, complicates deployments, and degrades the maintainability of the microservices architecture.

## 🚧 The What (Solution Overview)
Refactor import paths and architectural boundaries to resolve cyclic dependencies and reduce tight coupling.

1.  **Break Ecos/Agora Cycle:** Refactor the 6 import points in `ecos` (e.g., `cli/dashboard.py`, `ssot/tools/mof-workflow.py`) that depend on `agora`. Replace direct imports with event bus dispatching, callback injection, or strict MCP protocol calls to enforce downward-only dependency.
2.  **Decouple Agora/Kairon:** Analyze the direct imports of `kairon` packages within `agora`. Transition these tight bindings to communicate exclusively via the standardized MCP interfaces over the Agora mesh.
3.  **Declare Metaos Dependency:** Formally declare the missing `agora` dependency in the `metaos` `pyproject.toml` to prevent runtime crashes.

## 📏 Boundaries & Appetites
-   **Appetite:** 1 Week (Medium complexity, significant architectural impact).
-   **No-Gos:** Do not change the fundamental responsibilities of either `agora` or `ecos`. The focus is strictly on the *method* of interaction (interfaces over direct imports).

## ⚠️ Rabbit Holes & Risks
-   **Refactoring Ripple Effects:** Breaking cyclic dependencies often requires introducing new interfaces or moving logic across packages, which can introduce subtle bugs if not thoroughly tested.
-   **MCP Overhead:** Replacing direct in-memory calls with MCP protocol calls between `agora` and `kairon` might introduce slight latency. We must ensure this overhead is acceptable for the affected use cases.