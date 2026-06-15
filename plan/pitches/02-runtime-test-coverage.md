# Pitch: Establish Comprehensive Testing for Runtime Execution Sandbox

## 🎯 The Why (Problem & Opportunity)
The `runtime/ecos` layer acts as the foundation of the execution environment (L1/L0), responsible for agent sandboxing and command orchestration. However, an architectural review revealed a critically low test coverage ratio (0.12/0.18), with the core executor engine operating essentially untested. This lack of verification for the "gatekeeper" infrastructure poses a severe P0 risk of agent escape, logic regressions, and unpredictable system behavior.

## 🚧 The What (Solution Overview)
Implement a comprehensive test suite for the `runtime` module, specifically targeting the execution engine and sandbox boundaries.

1.  **Executor Engine Coverage:** Write unit and integration tests for the core orchestration logic, ensuring state transitions, failure handling, and lifecycle events behave deterministically.
2.  **Sandbox Isolation Verification:** Develop tests to explicitly verify the integrity of the execution sandboxes, confirming that agents cannot access unauthorized resources or bypass network/file system constraints.
3.  **CI Enforcement:** Integrate coverage thresholds into the CI pipeline to prevent future regressions in the `runtime` codebase.

## 📏 Boundaries & Appetites
-   **Appetite:** 2 Weeks (High complexity, critical safety).
-   **No-Gos:** Do not rewrite the executor engine logic unless an unpatchable flaw is discovered. The goal is validation, not architectural redesign.

## ⚠️ Rabbit Holes & Risks
-   **Mocking Complexity:** Testing the sandbox effectively will require sophisticated mocking of OS-level primitives and process isolation mechanisms, which can be brittle if not designed carefully.