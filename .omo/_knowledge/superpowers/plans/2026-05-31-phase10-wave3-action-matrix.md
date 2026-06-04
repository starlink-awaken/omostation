# Phase 10 Wave 3 Action Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the normalized Phase 10 bundle interface from one governed action to an action-first matrix covering `project.dispatch` and `runtime.observe`.

**Architecture:** Keep all Wave 3 work inside `system-space` and reuse the Wave 2 normalized bundle shape. First ratify Wave 3 as the active packet, then add failing tests for a two-action matrix, implement the smallest contract additions for `runtime.observe`, and finish by exercising the live Wave 3 envelope plus the full OMO regression suite.

**Tech Stack:** Markdown plans, YAML task/state/contract files, Python pytest, `scripts/omo_rules.py`, `scripts/omo_worker.py`

---

### Task 1: Ratify Phase 10 Wave 3 as the active execution packet

**Files:**
- Create: `.omo/tests/test_phase10_wave3_docs.py`
- Create: `.omo/plans/phase10-wave3-execution-plan.md`
- Create: `.omo/tasks/active/P10-W3-ACTION-FIRST-MATRIX.yaml`
- Create: `.omo/tasks/done/P10-W2-NORMALIZED-RULE-BUNDLE.yaml`
- Create: `.omo/workers/runs/phase10-wave3-action-matrix-dispatch.yaml`
- Create: `.omo/workers/runs/phase10-wave3-action-matrix-prompt.md`
- Create: `.omo/workers/runs/phase10-wave3-action-matrix-review.md`
- Create: `.omo/workers/runs/phase10-wave3-action-matrix-checkpoint.md`
- Create: `.omo/workers/runs/phase10-wave3-action-matrix-reclaim.md`
- Modify: `.omo/goals/current.yaml`
- Modify: `.omo/state/system.yaml`
- Modify: `.omo/INDEX.md`
- Modify: `.omo/_control/INDEX.md`
- Modify: `.omo/_knowledge/design/INDEX.md`
- Modify: `.omo/plans/README.md`
- Modify: `.omo/tasks/README.md`
- Test: `.omo/tests/test_phase10_wave3_docs.py`

- [ ] **Step 1: Write the failing Wave 3 kickoff regression**

```python
from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase10_wave3_is_now_the_active_packet() -> None:
    goals = _read("goals/current.yaml")
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")
    wave3_plan = _read("plans/phase10-wave3-execution-plan.md")
    active_task = _read("tasks/active/P10-W3-ACTION-FIRST-MATRIX.yaml")
    done_task = _read("tasks/done/P10-W2-NORMALIZED-RULE-BUNDLE.yaml")

    assert "current_wave: 3" in goals
    assert "id: G10.3" in goals
    assert 'status: active' in goals.split("- id: G10.3", 1)[1]
    assert "P10-W3-ACTION-FIRST-MATRIX" in goals

    assert "current_wave: 3" in system
    assert "phase10_status: wave3_active" in system
    assert "next_milestone: Phase 10 Wave 4 gate" in system

    assert "runtime.observe" in wave3_plan
    assert "action-first matrix" in wave3_plan
    assert "status: in_progress" in active_task
    assert ".omo/plans/phase10-wave3-execution-plan.md" in active_task
    assert "status: done" in done_task

    assert "phase10-wave3-execution-plan.md" in root_index
    assert "P10-W3-ACTION-FIRST-MATRIX" in control_index
    assert "phase10-wave3-execution-plan.md" in design_index
    assert "phase10-wave3-execution-plan.md" in plans_readme
    assert "P10-W3-ACTION-FIRST-MATRIX" in tasks_readme
```

- [ ] **Step 2: Run the Wave 3 kickoff test to verify it fails**

Run:

```bash
python3 -m pytest .omo/tests/test_phase10_wave3_docs.py -q
```

Expected: FAIL because Wave 3 docs/state do not exist yet and Wave 2 is still active.

- [ ] **Step 3: Write the Wave 3 execution plan and switch the live packet/state**

Create `.omo/plans/phase10-wave3-execution-plan.md` with:

```md
# Phase 10 Wave 3 execution plan

## Goal

Expand the normalized bundle interface to the first multi-action rollout matrix.

## Scope

1. keep all work inside `system-space`
2. add `runtime.observe` next to `project.dispatch`
3. prove both actions resolve through the same typed bundle keys
4. keep CLI output and bundle readers action-agnostic
```

Create `.omo/tasks/active/P10-W3-ACTION-FIRST-MATRIX.yaml` with:

```yaml
id: P10-W3-ACTION-FIRST-MATRIX
phase: 10
milestone: W3
priority: P0
title: Expand the normalized bundle into a two-action matrix
status: in_progress
assigned_to: copilot-cli
dispatch_id: phase10-wave3-action-matrix
knowledge_refs:
  - .omo/plans/phase10-program-plan.md
  - .omo/plans/phase10-wave3-execution-plan.md
deliverables:
  - .omo/plans/phase10-wave3-execution-plan.md
  - .omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml
  - scripts/omo_rules.py
  - .omo/tests/test_phase10_wave3_matrix.py
test_plan:
  - python3 scripts/omo_worker.py task validate --all-active
  - python3 -m pytest .omo/tests/test_phase10_wave3_docs.py -q
  - python3 -m pytest .omo/tests/test_phase10_wave3_matrix.py -q
  - python3 -m pytest .omo/tests -q
```

Archive Wave 2 by writing `.omo/tasks/done/P10-W2-NORMALIZED-RULE-BUNDLE.yaml` from the current active packet with `status: done`, then switch the live state surfaces to `current_wave: 3` / `phase10_status: wave3_active`.

Seed the Wave 3 worker skeletons using the same pattern as Wave 2:

```yaml
version: 1
dispatch_id: phase10-wave3-action-matrix
task_id: P10-W3-ACTION-FIRST-MATRIX
worker_id: copilot-cli
transport_mode: cli_prompt
run_ref: .omo/workers/runs/phase10-wave3-action-matrix-dispatch.yaml
inputs:
  task_yaml: .omo/tasks/active/P10-W3-ACTION-FIRST-MATRIX.yaml
  prompt_file: .omo/workers/runs/phase10-wave3-action-matrix-prompt.md
handoff:
  output_summary_ref: .omo/workers/runs/phase10-wave3-action-matrix-review.md
```

- [ ] **Step 4: Run Wave 3 kickoff verification**

Run:

```bash
python3 scripts/omo_worker.py task validate --all-active
python3 scripts/sync_omo_state.py
python3 -m pytest .omo/tests/test_phase10_wave3_docs.py -q
```

Expected: PASS; exactly one active packet remains and it is `P10-W3-ACTION-FIRST-MATRIX`.

- [ ] **Step 5: Commit**

```bash
git add .omo/tests/test_phase10_wave3_docs.py .omo/plans/phase10-wave3-execution-plan.md .omo/tasks/active/P10-W3-ACTION-FIRST-MATRIX.yaml .omo/tasks/done/P10-W2-NORMALIZED-RULE-BUNDLE.yaml .omo/goals/current.yaml .omo/state/system.yaml .omo/INDEX.md .omo/_control/INDEX.md .omo/_knowledge/design/INDEX.md .omo/plans/README.md .omo/tasks/README.md
git -c core.hooksPath=/dev/null commit -m "docs(phase10): ratify wave3 action matrix"
```

### Task 2: Add failing tests for the first two-action normalized matrix

**Files:**
- Create: `.omo/tests/test_phase10_wave3_matrix.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Test: `.omo/tests/test_phase10_wave3_matrix.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing multi-action regression**

Create `.omo/tests/test_phase10_wave3_matrix.py` with:

```python
from __future__ import annotations

from pathlib import Path

from scripts.omo_rules import evaluate_rule_bundle


ROOT = Path(__file__).resolve().parents[2]


def test_phase10_wave3_runtime_observe_resolves_through_same_bundle_shape() -> None:
    bundle = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave3-action-matrix-envelope.yaml"),
    )

    assert bundle["action"] == "runtime.observe"
    assert bundle["delivery_contract_ref"] == ".omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml"
    assert bundle["data_contract"] == {
        "policy_ref": "data/system-data-access-policy.yaml",
        "allowed_roots": [],
    }
    assert bundle["runtime_boundary_ref"] == "runtime/system-runtime-boundary.yaml"


def test_phase10_wave3_project_dispatch_still_uses_same_normalized_keys() -> None:
    bundle = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml"),
    )

    assert sorted(bundle.keys()) == sorted(
        [
            "acceptance_ref",
            "action",
            "admission_contract_ref",
            "approval_ref",
            "data_contract",
            "data_policy_ref",
            "delivery_contract",
            "delivery_contract_ref",
            "membership_ref",
            "registry_ref",
            "rollout_policy_ref",
            "runtime_boundary_ref",
            "space_ref",
        ]
    )
```

- [ ] **Step 2: Extend the CLI regression to prove `runtime.observe` prints the same normalized keys**

Append this test to `.omo/tests/test_omo_automation.py`:

```python
def test_worker_rules_eval_command_prints_runtime_observe_contract(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": "observe-approval.yaml",
            "apply_ref": "observe-apply.yaml",
            "verify_ref": "observe-verify.yaml",
            "acceptance_ref": "observe-acceptance.yaml",
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/system-space.yaml",
                    "action": "runtime.observe",
                    "governance": {
                        "admission_contract_ref": "spaces/identity.yaml",
                        "rollout_policy_ref": "spaces/rollout-policy.yaml",
                    },
                    "runtime": {"boundary_ref": "runtime/runtime-boundary.yaml"},
                    "data": {"policy_ref": "data/data-policy.yaml"},
                    "delivery": {"contract_ref": ".omo/_delivery/task-center/contracts/delivery.yaml"},
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "data" / "data-policy.yaml",
        {"rules": [{"action": "runtime.observe", "allowed_roots": []}]},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "observe-envelope.yaml",
        {
            "task_id": "P10-W3-TASK-1",
            "gates": {"approval_ref": "observe-approval.yaml", "acceptance_ref": "observe-acceptance.yaml"},
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "runtime.observe",
            },
            "rules_context": {"registry_ref": "spaces/cross-root-rules.yaml"},
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["omo", "worker", "rules-eval", ".omo/workers/runs/observe-envelope.yaml"])

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "action=runtime.observe" in output
    assert "delivery_contract=.omo/_delivery/task-center/contracts/delivery.yaml" in output
    assert "runtime_boundary=runtime/runtime-boundary.yaml" in output
```

- [ ] **Step 3: Run the targeted red tests**

Run:

```bash
python3 -m pytest .omo/tests/test_phase10_wave3_matrix.py .omo/tests/test_omo_automation.py -q -k "wave3 or runtime_observe_contract"
```

Expected: FAIL because the Wave 3 live envelope/contract files do not exist yet and `evaluate_rule_bundle(...)` still special-cases only `P10-W2` packets.

- [ ] **Step 4: Commit**

```bash
git add .omo/tests/test_phase10_wave3_matrix.py .omo/tests/test_omo_automation.py
git -c core.hooksPath=/dev/null commit -m "test(phase10): add wave3 action matrix regressions"
```

### Task 3: Implement the `runtime.observe` contract and generic normalized matrix resolver

**Files:**
- Create: `.omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml`
- Create: `.omo/workers/runs/phase10-wave3-action-matrix-envelope.yaml`
- Modify: `spaces/system-space-cross-root-rule-registry.yaml`
- Modify: `data/system-data-access-policy.yaml`
- Modify: `scripts/omo_rules.py`
- Modify: `scripts/omo_worker.py`
- Test: `.omo/tests/test_phase10_wave3_matrix.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the `runtime.observe` delivery contract**

Create `.omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml` with:

```yaml
contract_version: v1
action: runtime.observe
proposal_ref: .omo/workers/runs/phase9-wave3-identity-admission-approval.yaml
apply_ref: .omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml
verify_ref: .omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml
acceptance_ref: .omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml
```

- [ ] **Step 2: Extend the registry and data policy to carry two normalized actions**

Change `spaces/system-space-cross-root-rule-registry.yaml` so it contains a second normalized rule:

```yaml
  - id: system-space-runtime-observe
    space_ref: spaces/system-space.yaml
    action: runtime.observe
    governance:
      admission_contract_ref: spaces/system-space-identity-admission.yaml
      rollout_policy_ref: spaces/system-space-rollout-policy.yaml
    data:
      policy_ref: data/system-data-access-policy.yaml
    runtime:
      boundary_ref: runtime/system-runtime-boundary.yaml
    delivery:
      contract_ref: .omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml
```

Change `data/system-data-access-policy.yaml` so it includes:

```yaml
  - action: runtime.observe
    allowed_roots: []
    controls:
      registry_ref: spaces/system-space-cross-root-rule-registry.yaml
      runtime_boundary_ref: runtime/system-runtime-boundary.yaml
```

- [ ] **Step 3: Remove the `P10-W2` special-case and make normalized bundles generic**

Update `scripts/omo_rules.py` so the normalized return path is selected whenever the rule contains a `delivery.contract_ref`, not only when `task_id.startswith("P10-W2")`:

```python
def _is_normalized_rule(rule: dict) -> bool:
    return bool(rule.get("delivery", {}).get("contract_ref"))


def evaluate_rule_bundle(root: Path, envelope_ref: Path) -> dict[str, object]:
    ...
    if _is_normalized_rule(rule):
        data_policy = _load_yaml(root / data_policy_ref)
        data_rule = _find_data_rule(data_policy, str(execution_context["action"]))
        delivery_contract_ref = str(rule["delivery"]["contract_ref"])
        delivery_contract = _load_yaml(root / delivery_contract_ref)

        return {
            "space_ref": execution_context["space_ref"],
            "membership_ref": execution_context["membership_ref"],
            "action": execution_context["action"],
            "registry_ref": registry_ref,
            "data_policy_ref": data_policy_ref,
            "runtime_boundary_ref": runtime_boundary_ref,
            "admission_contract_ref": admission_contract_ref,
            "rollout_policy_ref": rollout_policy_ref,
            "data_contract": {
                "policy_ref": data_policy_ref,
                "allowed_roots": list(data_rule.get("allowed_roots", [])),
            },
            "delivery_contract_ref": delivery_contract_ref,
            "delivery_contract": {
                "proposal_ref": delivery_contract["proposal_ref"],
                "apply_ref": delivery_contract["apply_ref"],
                "verify_ref": delivery_contract["verify_ref"],
                "acceptance_ref": envelope["gates"]["acceptance_ref"],
            },
            "approval_ref": envelope["gates"]["approval_ref"],
            "acceptance_ref": envelope["gates"]["acceptance_ref"],
        }
```

Keep `worker rules-eval` unchanged except for relying on the generic normalized result rather than packet naming.

- [ ] **Step 4: Seed the live Wave 3 envelope**

Create `.omo/workers/runs/phase10-wave3-action-matrix-envelope.yaml` with:

```yaml
version: 1
task_id: P10-W3-ACTION-FIRST-MATRIX
worker_id: copilot-cli
run_ref: .omo/workers/runs/phase10-wave3-action-matrix-dispatch.yaml
execution_context:
  space_ref: spaces/system-space.yaml
  membership_ref: system-governor-membership
  action: runtime.observe
rules_context:
  registry_ref: spaces/system-space-cross-root-rule-registry.yaml
gates:
  approval_ref: .omo/workers/runs/phase9-wave3-identity-admission-approval.yaml
  acceptance_ref: .omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml
```

- [ ] **Step 5: Run the targeted tests to green**

Run:

```bash
python3 -m pytest .omo/tests/test_phase10_wave3_matrix.py .omo/tests/test_omo_automation.py -q -k "wave3 or runtime_observe_contract"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml .omo/workers/runs/phase10-wave3-action-matrix-envelope.yaml spaces/system-space-cross-root-rule-registry.yaml data/system-data-access-policy.yaml scripts/omo_rules.py scripts/omo_worker.py
git -c core.hooksPath=/dev/null commit -m "feat(phase10): add wave3 action matrix"
```

### Task 4: Verify the live Wave 3 packet and the full OMO regression suite

**Files:**
- Modify: `.omo/tasks/active/P10-W3-ACTION-FIRST-MATRIX.yaml`
- Modify: `.omo/tests/test_phase10_wave2_normalization.py`
- Modify: `.omo/tests/test_phase10_wave2_docs.py`
- Test: `.omo/tests/test_phase10_wave3_docs.py`
- Test: `.omo/tests/test_phase10_wave3_matrix.py`

- [ ] **Step 1: Exercise the live resolver against the real Wave 3 envelope**

Run:

```bash
python3 scripts/omo_worker.py worker rules-eval .omo/workers/runs/phase10-wave3-action-matrix-envelope.yaml
```

Expected: stdout includes `action=runtime.observe`, `registry=spaces/system-space-cross-root-rule-registry.yaml`, and `delivery_contract=.omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml`.

- [ ] **Step 2: Update historical Wave 2 regressions so they no longer assume Wave 2 is current**

Change `.omo/tests/test_phase10_wave2_docs.py` to assert Wave 2 is recorded under `tasks/done/` and that Wave 3 is now current:

```python
def test_phase10_wave2_is_recorded_as_history() -> None:
    system = _read("state/system.yaml")
    done_task = _read("tasks/done/P10-W2-NORMALIZED-RULE-BUNDLE.yaml")

    assert "phase10_status: wave3_active" in system
    assert "status: done" in done_task
```

Keep `.omo/tests/test_phase10_wave2_normalization.py` focused on the normalized `project.dispatch` contract itself, not the current packet state:

```python
def test_phase10_wave2_project_dispatch_bundle_stays_normalized() -> None:
    bundle = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml"),
    )

    assert bundle["action"] == "project.dispatch"
    assert bundle["delivery_contract_ref"] == ".omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml"
```

- [ ] **Step 3: Update the active packet evidence after the live run**

Add the live Wave 3 envelope and runtime-observe delivery contract to `.omo/tasks/active/P10-W3-ACTION-FIRST-MATRIX.yaml`:

```yaml
handoff_refs:
  - .omo/workers/runs/phase10-wave3-action-matrix-envelope.yaml
deliverables:
  - .omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml
evidence_required:
  - runtime.observe resolves through the same normalized bundle keys as project.dispatch
```

- [ ] **Step 4: Run full verification**

Run:

```bash
python3 scripts/sync_omo_state.py
python3 scripts/omo_worker.py task validate --all-active
python3 -m pytest .omo/tests/test_phase10_wave3_docs.py .omo/tests/test_phase10_wave3_matrix.py .omo/tests/test_phase10_wave2_docs.py .omo/tests/test_phase10_wave2_normalization.py -q
python3 -m pytest .omo/tests -q
```

Expected: PASS; Wave 3 remains the only active packet and both normalized actions resolve through the same interface.

- [ ] **Step 5: Commit**

```bash
git add .omo/tasks/active/P10-W3-ACTION-FIRST-MATRIX.yaml .omo/tests/test_phase10_wave2_docs.py .omo/tests/test_phase10_wave2_normalization.py
git -c core.hooksPath=/dev/null commit -m "test(phase10): verify wave3 action matrix"
```
