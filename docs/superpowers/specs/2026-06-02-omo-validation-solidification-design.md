# OMO validation solidification design

Date: 2026-06-02
Status: approved-by-default baseline (user unavailable; proceeded with recommended option)
Scope: make the Workspace `.omo` verification flow canonical, reusable, and drift-resistant across local use, CI, and operator guidance

## 1. Context

The current Workspace `.omo` verification story now has a known good end-to-end chain:

1. `python3 scripts/sync_omo_state.py --omo-dir .omo`
2. `python3 scripts/omo_worker.py task validate --all-active`
3. `python3 -m pytest .omo/tests -q`

That chain was just re-validated successfully and is now the most accurate proof that:

- `.omo/state/system.yaml` can be refreshed
- active task metadata satisfies schema and run-chain expectations
- the `.omo` governance regression suite remains green

However, the chain is not yet fully solidified across the workspace:

- `Makefile` still exposes `governance-check`, but that target runs a different sequence (`validate -> sync -> index`)
- GitHub Actions already runs a stronger `.omo` governance workflow, but its exact behavior is not surfaced as the single local entrypoint
- `.omo/AGENT.md` explains pieces of the process, but does not yet declare one canonical verification command that local operators and CI both share

The result is avoidable drift:

1. local operators may run a weaker check than CI
2. CI may encode policy that is not obvious from the local developer workflow
3. future edits may reintroduce mismatch between documentation, shell entrypoints, and automated enforcement

## 2. Goals

This work should:

1. define one canonical `.omo` verification pipeline
2. make local invocation and CI enforcement use the same underlying sequence
3. document the canonical pipeline in the operator-facing `.omo` guidance
4. reduce the chance that Make targets, workflows, and docs drift apart again
5. keep the solidification bounded to `.omo` governance verification rather than broad workspace CI redesign

## 3. Non-goals

This design does not:

1. redesign the entire root CI strategy
2. replace project-specific test/lint/build flows outside `.omo`
3. fold unrelated checks into the `.omo` governance gate just because they exist
4. turn documentation into the source of truth for verification logic
5. introduce a second competing validation path for convenience

## 4. Approaches considered

### A. Recommended: single canonical verification entrypoint reused by local + CI

Create one small canonical verification surface for `.omo`, then make:

- local `make` targets call it
- CI call it
- `.omo/AGENT.md` reference it

Pros:

- lowest drift risk
- people and automation run the same thing
- failures become easier to interpret because there is one shared contract

Cons:

- requires a little cleanup of existing Makefile/workflow layering
- may need one dedicated guard test to prevent future divergence

### B. Docs-first only

Keep current commands and workflow behavior, but update docs to say what people should run.

Pros:

- cheapest initial change
- low code churn

Cons:

- weakest guarantee
- drift returns as soon as someone edits CI or Make targets independently

### C. CI-first enforcement

Treat GitHub Actions as the real source of truth and let local commands remain thinner or partially overlapping.

Pros:

- strongest remote enforcement
- easiest for gatekeeping on PRs

Cons:

- local developer loop remains fuzzy
- operators can still believe they verified something locally when they did not run the full chain

## 5. Recommended design

Use **Approach A**.

The core decision is:

> The Workspace should have exactly **one canonical `.omo` verification pipeline**, and every higher-level surface should delegate to it instead of re-spelling its own partial logic.

That means the solidification work is not primarily about adding more checks. It is about removing ambiguity around **which chain is authoritative**.

The recommended canonical chain remains:

1. `sync_omo_state`
2. `task validate --all-active`
3. `.omo` regression tests

Other checks that are useful but not part of this minimum proof (for example index coverage or broader consistency scripts) should either:

- run as separate named checks, or
- be explicitly layered after the canonical validation gate

They should not silently redefine what “`.omo` verification passed” means.

## 6. Components and boundaries

### 6.1 Canonical runner

A single repo-local entrypoint should represent the authoritative `.omo` verification contract.

Form:

- either a dedicated script such as `bin/verify-omo.sh`
- or a single Make target that becomes the only canonical entrypoint and is directly reused by CI

Recommendation:

- prefer a dedicated script, because scripts are easier for CI, local shell use, and future composition than parsing Make target internals

### 6.2 Local ergonomics layer

The root `Makefile` should expose a friendly target such as:

- `make governance-verify`

That target should be a thin wrapper around the canonical runner, not an independently maintained command chain.

Existing adjacent targets like `governance-sync`, `governance-validate`, and `governance-index-check` can remain for focused use, but they should no longer imply “full `.omo` verification”.

### 6.3 CI enforcement layer

`.github/workflows/governance-check.yml` should call the same canonical runner for the minimum `.omo` verification contract.

If CI also wants extra gates such as index coverage or system consistency, that is acceptable, but those steps should be visibly separate from the canonical verification step.

This preserves a clean mental model:

- canonical `.omo` verification = one shared chain
- additional policy checks = explicit extra layers

### 6.4 Operator documentation layer

`.omo/AGENT.md` should explicitly state:

1. what command proves `.omo` is green
2. what that command covers
3. which adjacent commands are partial checks only

This turns the operator guide into a routing surface, not a second implementation of the logic.

## 7. Data flow and control flow

The solidified flow should read as:

1. operator or CI calls the canonical runner
2. runner syncs live `.omo` state
3. runner validates active task metadata and run/review chain integrity
4. runner executes `.omo` regression tests
5. caller gets a single success/failure result for the canonical gate

Then, optionally:

6. separate non-canonical checks may run afterward (for example index coverage)

The key rule is that step 6 must not be confused with steps 1-5.

## 8. Drift prevention

To keep the solidification durable, add at least one guard that prevents future divergence.

Recommended guard:

1. a dedicated `.omo` regression test that asserts:
   - the documented canonical command exists in `.omo/AGENT.md`
   - the Make target delegates to the canonical runner
   - the GitHub workflow invokes the same canonical runner

This is the highest-leverage hardening step because it tests the relationship between:

- docs
- local entrypoint
- CI entrypoint

instead of trusting humans to keep them aligned.

## 9. Error handling and policy

The solidified runner should:

1. stop on the first failing stage
2. preserve stage order (`sync -> validate -> test`)
3. surface which stage failed
4. avoid silent fallback behavior

The design should not:

1. auto-fix task metadata
2. auto-rewrite `.omo` state beyond the intentional sync step
3. blur the boundary between verification and mutation

## 10. Testing and verification

Verification of the solidification work should include:

1. a direct run of the canonical runner
2. a direct run of the wrapper Make target
3. a targeted regression test that guards parity between:
   - canonical runner
   - Makefile entrypoint
   - `.omo/AGENT.md`
   - GitHub workflow
4. a final `.omo` regression pass proving the solidified path did not change behavior

## 11. Rollout sequence

1. add the canonical runner
2. repoint the root Make target to it
3. repoint the GitHub workflow to it
4. update `.omo/AGENT.md` to declare it as the authoritative command
5. add the parity guard test
6. run the full verification flow

## 12. Success criteria

This design is successful when:

1. there is one obvious authoritative `.omo` verification command
2. local and CI use the same underlying verification logic
3. `.omo/AGENT.md` routes operators to that same command
4. future drift between docs, Make, and workflow is guarded by tests
5. “`.omo` verification passed” has one stable meaning across the workspace
