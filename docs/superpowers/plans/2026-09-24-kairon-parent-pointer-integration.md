# Implementation Plan: Kairon parent gitlink integration

> **Execution contract:** implement only the accepted spec for BET-Y2Q2-T11-03.

1. Register this BET and bind its accepted spec/plan.
2. Verify child commit `642311f4728cb893e0c643f34f78407d66af4b67` and checkout that exact gitlink in the isolated root worktree.
3. Confirm no other submodule pointer changes.
4. Commit the root repair and Kairon pointer with explicit paths, then tag the delivery.
5. Run child tests, root regression tests, GaC local gate, and SSOT guardian.

Acceptance: root pointer equals the independently verified child commit; all listed checks pass; no unrelated paths enter the commit.
