# Pitch: Submodule Dirty State Cleanup

> **Upstream**: MS-ARCHITECTURE-CONVERGENCE
> **Appetite:** 1 day

## 🎯 The Why (Problem & Opportunity)

`git status` shows **10 submodules with uncommitted modifications** (aetherforge, c2g, family-hub, gbrain, hermes-console, l4-kernel, model-driven, observability, omo-debt, scripts). This creates:
- Risk of losing work if not committed.
- Unclear what changes are intentional vs. drift.
- Blocker for clean workspace operations and CI.

## 🚧 The What (Solution Overview)

1. **Per-submodule audit:** inspect `git status --short` for each dirty submodule.
2. **Classify changes:** code changes, docs updates, pycache noise, or pointer drift.
3. **Commit legitimate changes** with atomic commits per concern.
4. **Reset pycache / accidental changes** that should not be committed.
5. **Bump root repo submodule pointers** to the new clean commits.

## 📏 Boundaries & Appetites

- **Appetite:** 1 day.
- **No-Gos:** Do not merge unrelated changes into a single commit; preserve per-submodule history.

## ⚠️ Rabbit Holes & Risks

- **Dependency risk:** Some submodules may depend on each other; bump order matters.
- **CI risk:** Submodules may have failing tests; verify before pushing.
