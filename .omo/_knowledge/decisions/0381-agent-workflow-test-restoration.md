---
id: ADR-0381
title: Agent-workflow test restoration — v10 load_registry regression fix + CI coverage + E-5 trigger SSOT
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-06
---

# 0381 — Agent-Workflow Test Restoration Round

> Parent: ADR-0379/0380 (CI plane), concurrent omo v10 (#1034).
> Restores the 14 broken `test_agent_workflow.py` tests to green,
> fixes the root cause (v10 load_registry regression), adds the test
> file to CI coverage so this class of breakage is no longer silent,
> and lands the lightweight E-5 trigger SSOT.

## Context

ADR-0380 documented 15 failing `tests/test_agent_workflow.py` cases
after concurrent omo v10 (#1034) — attributed to a "taxonomy change".
Root-cause investigation this round proved the failures were a genuine
**v10 regression**, not an intentional behavior change:

`load_registry` (split-directory rework) broke the **monolithic-file
format**: when a single YAML doc contained `workflows`, the branch
`if "workflows" in doc: workflows_list.extend(...); continue` skipped
merging the doc's other top-level keys. Test fixtures (and any legacy
monolithic registry) lost `runner` config (`lock_state_dir` etc.) and
`external_patterns` → runs/locks landed in the real default dirs and
adapter lint contracts were no-ops. 14 tests failed on `assert 2 == 0`
("lock already held" on leftover real-dir locks) and `assert 0 == 1`
(lint no longer rejecting contract-less adapters).

The directory-based registry (production) was unaffected — only the
file-based path regressed, and no CI ran `test_agent_workflow.py`, so
the breakage shipped silently.

## Decision

### D1. P0b — Fix `load_registry` monolithic-file merge

`projects/omo/.../workflow/core.py::load_registry`: the workflows-doc
branch now merges every other top-level key (deep-merge dicts) and
updates `external_patterns` from the same doc, restoring the
pre-v10 monolithic semantics while keeping the directory structure
behavior intact.

Result: **36/36 `test_agent_workflow.py` PASS** (14 restored), 742 omo
project tests still pass.

### D2. P0b — Add `test_agent_workflow.py` to CI coverage

`governance-check.yml`'s pytest step now includes
`tests/test_agent_workflow.py`, so a future regression fails the
interface-check gate instead of shipping silently.

### D3. E-5 (lightweight) — workflow trigger SSOT

`ci-surfaces.yaml` gains a `workflow_triggers:` section (per-workflow
`triggers` + `path_filtered`). `check-ci-surfaces.py` gains
`check_workflow_trigger_drift`: workflow's actual trigger set /
path-filter differs from the registry → `trigger-drift` warn.
`ci-check-runner.py` added to the overlap exemption (it is the
multi-workflow execution engine, not a duplicated check).

## Consequences

### Positive

- 14 tests restored at the root cause; the "known debt" from ADR-0380
  is resolved (not just patched around).
- CI now covers the agent-workflow CLI contract — the exact class of
  silent breakage that shipped with v10 is gate-enforced.
- Trigger drift is observable: renaming/adding triggers or path
  filters without refreshing the registry surfaces as a warning.
- Detector: 0 errors, 4 intentional defense-in-depth overlap warns.

### Negative / Trade-offs

- Full E-5 (path-filter values driving local gate scope parity) is
  still future work; this round adds observability, not scope parity.
- The load_registry fix touches the concurrent v10 implementation —
  reviewed against its 742 tests, no behavioral change for the
  directory path.

## Compliance

- ADR-0379/0380: completes the CI-plane initiative's loose ends.
- ADR-0203: requirement iteration; workflow run registered with path
  coverage.
- ADR-0220 D1: claim `round-0381` (deleted after merge).

## Verification

```bash
python3 -m pytest tests/test_agent_workflow.py -q   # 36 passed
python3 -m pytest tests/test_ci_surfaces.py -q      # 9 passed
python3 bin/gac/check-ci-surfaces.py --json         # ok, 0 errors
python3 bin/gac/gac-healthcheck.py                  # 全绿
make gac-local-gate                                 # PASS
```
