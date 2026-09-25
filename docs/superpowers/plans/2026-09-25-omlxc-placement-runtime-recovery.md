# OMLXC Placement Runtime Recovery Implementation Plan

> **Execution rule:** follow `skill://subagent-driven-development` only if work is delegated; otherwise execute each task in order. Run the specified test immediately after each production change.

**Goal:** Make recovered OMLXC backends and transient AetherForge capacity failures self-healing without restarting either process.

**Design spec:** `docs/superpowers/specs/2026-09-25-omlxc-placement-runtime-recovery-design.md`

**Verification:** Python 3.13, `uv`, targeted pytest first, then project-local lint/type checks where available. No real hardware or remote runtime mutation in tests.

## Task 1: Add failing OMLXC recovery regression

**Files:**
- Modify: `projects/omlxc/tests/integration/test_task11_fix6_eligibility.py`
- Reference: `projects/omlxc/src/omlxc/daemon/composition.py`

1. Inspect the existing fake backend/config helpers and the public model-state response shape.
2. Add one deterministic async test that establishes a placement in stale/unavailable state, performs a successful backend refresh, and asserts the same placement becomes available/ready with current catalog data.
3. Run:
   ```bash
   cd projects/omlxc
   uv run pytest tests/integration/test_task11_fix6_eligibility.py -q
   ```
4. Confirm the new test fails for the current implementation before editing production code.

## Task 2: Implement scoped successful-probe placement refresh

**Files:**
- Modify: `projects/omlxc/src/omlxc/daemon/composition.py`

1. Trace the existing successful probe `_apply` path and stale failure `_fail_stale` path.
2. Add the smallest backend-scoped recomputation that uses existing readiness/load/capacity predicates and state ownership.
3. Preserve configured placement identity, unrelated backend state, and response schema.
4. Avoid new registries, retries, or synchronous request-path work.
5. Run the targeted OMLXC test from Task 1 and the adjacent eligibility tests:
   ```bash
   cd projects/omlxc
   uv run pytest tests/integration/test_task11_fix6_eligibility.py tests/integration/test_resident_reconcile_loop.py -q
   ```

## Task 3: Add failing AetherForge decay regression

**Files:**
- Modify: `projects/aetherforge/packages/gateway/tests/test_health_failure_decay.py`
- Reference: `projects/aetherforge/packages/gateway/src/llm_gateway/gateway.py`

1. Preserve existing success-reset, transient-TTL, and permanent-failure coverage.
2. Replace the obsolete assertion that `no_capacity` is permanent with a behavioral test proving it expires through the existing bounded TTL and can recover on a later successful request.
3. Keep a separate deterministic missing-model/configuration failure permanent.
4. Run:
   ```bash
   cd projects/aetherforge
   uv run pytest packages/gateway/tests/test_health_failure_decay.py -q
   ```
5. Confirm the changed no-capacity test fails before production code changes if the current permanent branch is exercised.

## Task 4: Implement transient no-capacity classification

**Files:**
- Modify: `projects/aetherforge/packages/gateway/src/llm_gateway/gateway.py`

1. Remove only the unconditional permanent classification for typed `no_capacity` failures.
2. Route that error through existing threshold and TTL decay state.
3. Leave typed missing-model/configuration failures permanent.
4. Do not alter cost/quota/provider routing or introduce another health registry.
5. Run the gateway health-decay test file, then the gateway package’s narrow related tests if failures identify callers.

## Task 5: Run cross-layer targeted verification

1. Run both modified test files from the repository root with their project-local `uv` environments.
2. Run OMLXC CLI canaries:
   ```bash
   cd projects/omlxc
   uv run omlxc models show coding-next --json
   uv run omlxc route plan coding-next --json
   ```
3. Run the available AetherForge health/catalog checks and an authenticated inference canary if the local runtime key is present.
4. If authenticated inference cannot run, record the exact credential/runtime blocker; do not claim inference proof from health alone.
5. Run the project-local lint/type checks required by each project’s AGENTS.md when the targeted behavior is green.

## Task 6: Governance verification and closeout evidence

1. Record exact test and canary outputs in the BET retro receipt.
2. Run:
   ```bash
   uv run --with pyyaml python bin/agent-workflow.py verify 20260925T014237Z-project-code-change-44d6eaf9 --from-diff --execute
   ```
3. Run the required project/workspace gate; report pre-existing unrelated failures separately.
4. Do not commit or push unless the user explicitly authorizes it.
5. Close the workflow with evidence and update the BET lifecycle only with observed results.
