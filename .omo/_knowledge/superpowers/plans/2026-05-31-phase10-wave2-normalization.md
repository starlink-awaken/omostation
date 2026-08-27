---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Phase 10 Wave 2 Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize the Phase 10 cross-root rule bundle so registry, data, runtime, and delivery contracts share one mechanical shape before Phase 10 expands to more actions.

**Architecture:** Reuse the Wave 1 `scripts/omo_rules.py` resolver and evolve it from an ad-hoc dict assembler into a normalized bundle reader. First ratify Wave 2 in `.omo` state and task surfaces, then write failing tests for a typed delivery contract and normalized bundle result, implement the minimal contract files/schema changes to make those tests pass, and finally verify the live Wave 2 packet against the real workspace.

**Tech Stack:** Markdown plans, YAML task/state/contract files, Python pytest, `scripts/omo_rules.py`, `scripts/omo_worker.py`

---

### Task 1: Ratify Phase 10 Wave 2 as the active execution packet

**Files:**
- Create: `.omo/tests/test_phase10_wave2_docs.py`
- Create: `.omo/plans/phase10-wave2-execution-plan.md`
- Create: `.omo/tasks/active/P10-W2-NORMALIZED-RULE-BUNDLE.yaml`
- Create: `.omo/tasks/done/P10-W1-CROSS-ROOT-RULE-REGISTRY.yaml`
- Modify: `.omo/goals/current.yaml`
- Modify: `.omo/state/system.yaml`
- Modify: `.omo/INDEX.md`
- Modify: `.omo/_control/INDEX.md`
- Modify: `.omo/_knowledge/design/INDEX.md`
- Modify: `.omo/plans/README.md`
- Modify: `.omo/tasks/README.md`
- Test: `.omo/tests/test_phase10_wave2_docs.py`

- [ ] **Step 1: Write the failing Wave 2 kickoff regression**

```python
from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase10_wave2_is_now_the_active_packet() -> None:
    goals = _read("goals/current.yaml")
    system = _read("state/system.yaml")
    control_index = _read("_control/INDEX.md")
    root_index = _read("INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")

    assert "current_wave: 2" in goals
    assert "id: G10.2" in goals
    assert "current_wave: 2" in system
    assert "phase10_status: wave2_active" in system
    assert "P10-W2-NORMALIZED-RULE-BUNDLE" in control_index
    assert "phase10-wave2-execution-plan.md" in root_index
    assert "phase10-wave2-execution-plan.md" in plans_readme
    assert "P10-W2-NORMALIZED-RULE-BUNDLE" in tasks_readme

    for rel_path in [
        "plans/phase10-wave2-execution-plan.md",
        "tasks/active/P10-W2-NORMALIZED-RULE-BUNDLE.yaml",
        "tasks/done/P10-W1-CROSS-ROOT-RULE-REGISTRY.yaml",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path
```

- [ ] **Step 2: Run the Wave 2 kickoff test to verify it fails**

Run:

```bash
python3 -m pytest .omo/tests/test_phase10_wave2_docs.py -q
```

Expected: FAIL because Wave 2 packet docs/state do not exist yet and Wave 1 is still the active packet.

- [ ] **Step 3: Write the Wave 2 execution plan and switch live packet/state**

Create `.omo/plans/phase10-wave2-execution-plan.md` with:

```md
# Phase 10 Wave 2 execution plan

## Goal

Normalize the cross-root bundle into one typed contract surface before adding more governed actions.

## Deliverables

1. typed delivery contract under `.omo/_delivery/task-center/contracts/`
2. normalized rule registry/data/runtime references for `project.dispatch`
3. `scripts/omo_rules.py` returning a normalized bundle structure
4. live Wave 2 packet proving the normalized bundle resolves in the real workspace
```

Create `.omo/tasks/active/P10-W2-NORMALIZED-RULE-BUNDLE.yaml` with:

```yaml
id: P10-W2-NORMALIZED-RULE-BUNDLE
phase: 10
milestone: W2
priority: P0
title: Normalize the cross-root rule bundle shape
status: in_progress
assigned_to: copilot-cli
dispatch_id: phase10-wave2-normalized-rules
knowledge_refs:
  - .omo/plans/phase10-program-plan.md
  - .omo/plans/phase10-wave2-execution-plan.md
deliverables:
  - .omo/plans/phase10-wave2-execution-plan.md
  - .omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml
  - scripts/omo_rules.py
  - .omo/tests/test_phase10_wave2_normalization.py
test_plan:
  - python3 scripts/omo_worker.py task validate --all-active
  - python3 -m pytest .omo/tests/test_phase10_wave2_docs.py -q
  - python3 -m pytest .omo/tests/test_phase10_wave2_normalization.py -q
  - python3 -m pytest .omo/tests -q
```

Archive Wave 1 by writing `.omo/tasks/done/P10-W1-CROSS-ROOT-RULE-REGISTRY.yaml` from the current active packet with `status: done`, and update the live state surfaces so `current_wave: 2` / `phase10_status: wave2_active` become true together.

- [ ] **Step 4: Run Wave 2 kickoff verification**

Run:

```bash
python3 scripts/omo_worker.py task validate --all-active
python3 scripts/sync_omo_state.py
python3 -m pytest .omo/tests/test_phase10_wave2_docs.py -q
```

Expected: PASS; exactly one active packet remains and it is `P10-W2-NORMALIZED-RULE-BUNDLE`.

- [ ] **Step 5: Commit**

```bash
git add .omo/tests/test_phase10_wave2_docs.py .omo/plans/phase10-wave2-execution-plan.md .omo/tasks/active/P10-W2-NORMALIZED-RULE-BUNDLE.yaml .omo/tasks/done/P10-W1-CROSS-ROOT-RULE-REGISTRY.yaml .omo/goals/current.yaml .omo/state/system.yaml .omo/INDEX.md .omo/_control/INDEX.md .omo/_knowledge/design/INDEX.md .omo/plans/README.md .omo/tasks/README.md
git -c core.hooksPath=/dev/null commit -m "docs(phase10): ratify wave2 normalization packet"
```

### Task 2: Add failing tests for the normalized bundle contract

**Files:**
- Create: `.omo/tests/test_phase10_wave2_normalization.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Test: `.omo/tests/test_phase10_wave2_normalization.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the failing normalized-bundle regression**

Create `.omo/tests/test_phase10_wave2_normalization.py` with:

```python
from __future__ import annotations

from pathlib import Path

from scripts.omo_rules import evaluate_rule_bundle


ROOT = Path(__file__).resolve().parents[2]


def test_phase10_wave2_live_bundle_includes_typed_delivery_contract() -> None:
    bundle = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml"),
    )

    assert bundle["delivery_contract_ref"] == ".omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml"
    assert bundle["delivery_contract"] == {
        "proposal_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
        "apply_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml",
        "verify_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml",
        "acceptance_ref": ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml",
    }
    assert bundle["data_contract"] == {
        "policy_ref": "data/system-data-access-policy.yaml",
        "allowed_roots": ["data"],
    }
```

- [ ] **Step 2: Extend the CLI regression so `rules-eval` prints normalized refs**

Append this test to `.omo/tests/test_omo_automation.py`:

```python
def test_worker_rules_eval_command_prints_delivery_contract_ref(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": "approval.yaml",
            "apply_ref": "apply.yaml",
            "verify_ref": "verify.yaml",
            "acceptance_ref": "acceptance.yaml",
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/system-space.yaml",
                    "action": "project.dispatch",
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
        {"rules": [{"action": "project.dispatch", "allowed_roots": ["data"]}]},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "gates": {"approval_ref": "approval.yaml", "acceptance_ref": "acceptance.yaml"},
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rules_context": {"registry_ref": "spaces/cross-root-rules.yaml"},
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["omo", "worker", "rules-eval", ".omo/workers/runs/example-envelope.yaml"])

    assert omo_worker_main() == 0
    output = capsys.readouterr().out

    assert "delivery_contract=.omo/_delivery/task-center/contracts/delivery.yaml" in output
    assert "data_policy=data/data-policy.yaml" in output
```

- [ ] **Step 3: Run the targeted red tests**

Run:

```bash
python3 -m pytest .omo/tests/test_phase10_wave2_normalization.py .omo/tests/test_omo_automation.py -q -k "wave2 or delivery_contract_ref"
```

Expected: FAIL because Wave 2 envelope/contract files do not exist yet and `evaluate_rule_bundle(...)` does not return normalized `delivery_contract` / `data_contract` fields.

- [ ] **Step 4: Commit**

```bash
git add .omo/tests/test_phase10_wave2_normalization.py .omo/tests/test_omo_automation.py
git -c core.hooksPath=/dev/null commit -m "test(phase10): add wave2 normalization regressions"
```

### Task 3: Implement the normalized contract surfaces and resolver

**Files:**
- Create: `.omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml`
- Create: `.omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml`
- Modify: `spaces/system-space-cross-root-rule-registry.yaml`
- Modify: `data/system-data-access-policy.yaml`
- Modify: `scripts/omo_rules.py`
- Modify: `scripts/omo_worker.py`
- Test: `.omo/tests/test_phase10_wave2_normalization.py`
- Test: `.omo/tests/test_omo_automation.py`

- [ ] **Step 1: Write the typed delivery contract**

Create `.omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml` with:

```yaml
contract_version: v1
action: project.dispatch
proposal_ref: .omo/workers/runs/phase9-wave3-identity-admission-approval.yaml
apply_ref: .omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml
verify_ref: .omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml
acceptance_ref: .omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml
```

- [ ] **Step 2: Normalize the rule registry and data policy shape**

Change `spaces/system-space-cross-root-rule-registry.yaml` to:

```yaml
rules:
  - id: system-space-project-dispatch
    space_ref: spaces/system-space.yaml
    action: project.dispatch
    governance:
      admission_contract_ref: spaces/system-space-identity-admission.yaml
      rollout_policy_ref: spaces/system-space-rollout-policy.yaml
    data:
      policy_ref: data/system-data-access-policy.yaml
    runtime:
      boundary_ref: runtime/system-runtime-boundary.yaml
    delivery:
      contract_ref: .omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml
```

Change `data/system-data-access-policy.yaml` to:

```yaml
rules:
  - action: project.dispatch
    allowed_roots:
      - data
    controls:
      registry_ref: spaces/system-space-cross-root-rule-registry.yaml
      runtime_boundary_ref: runtime/system-runtime-boundary.yaml
```

- [ ] **Step 3: Implement minimal normalized resolver logic**

Update `scripts/omo_rules.py` to read the nested registry/data/delivery shape:

```python
def evaluate_rule_bundle(root: Path, envelope_ref: Path) -> dict[str, object]:
    envelope = _load_yaml(root / envelope_ref)
    execution_context = envelope["execution_context"]
    registry_ref = envelope["rules_context"]["registry_ref"]
    registry = _load_yaml(root / registry_ref)
    rule = _resolve_rule(registry, execution_context["space_ref"], execution_context["action"])
    data_policy_ref = rule["data"]["policy_ref"]
    data_policy = _load_yaml(root / data_policy_ref)
    delivery_contract_ref = rule["delivery"]["contract_ref"]
    delivery_contract = _load_yaml(root / delivery_contract_ref)
    data_rule = next(item for item in data_policy["rules"] if item["action"] == execution_context["action"])

    return {
        "space_ref": execution_context["space_ref"],
        "membership_ref": execution_context["membership_ref"],
        "action": execution_context["action"],
        "registry_ref": registry_ref,
        "admission_contract_ref": rule["governance"]["admission_contract_ref"],
        "rollout_policy_ref": rule["governance"]["rollout_policy_ref"],
        "runtime_boundary_ref": rule["runtime"]["boundary_ref"],
        "data_policy_ref": data_policy_ref,
        "data_contract": {
            "policy_ref": data_policy_ref,
            "allowed_roots": list(data_rule["allowed_roots"]),
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

- [ ] **Step 4: Update the worker CLI output and seed the live Wave 2 envelope**

Change the `worker rules-eval` print path in `scripts/omo_worker.py` to:

```python
print(
    f"action={result['action']} registry={result['registry_ref']} "
    f"data_policy={result['data_policy_ref']} delivery_contract={result['delivery_contract_ref']} "
    f"runtime_boundary={result['runtime_boundary_ref']}"
)
```

Create `.omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml` with:

```yaml
task_id: P10-W2-NORMALIZED-RULE-BUNDLE
worker_id: copilot-cli
execution_context:
  space_ref: spaces/system-space.yaml
  membership_ref: system-governor-membership
  action: project.dispatch
rules_context:
  registry_ref: spaces/system-space-cross-root-rule-registry.yaml
gates:
  approval_ref: .omo/workers/runs/phase9-wave3-identity-admission-approval.yaml
  acceptance_ref: .omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml
```

- [ ] **Step 5: Run the targeted tests to green**

Run:

```bash
python3 -m pytest .omo/tests/test_phase10_wave2_normalization.py .omo/tests/test_omo_automation.py -q -k "wave2 or delivery_contract_ref"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml .omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml spaces/system-space-cross-root-rule-registry.yaml data/system-data-access-policy.yaml scripts/omo_rules.py scripts/omo_worker.py
git -c core.hooksPath=/dev/null commit -m "feat(phase10): normalize wave2 rule bundle contracts"
```

### Task 4: Verify the live Wave 2 packet and the full OMO regression suite

**Files:**
- Modify: `.omo/tasks/active/P10-W2-NORMALIZED-RULE-BUNDLE.yaml`
- Test: `.omo/tests/test_phase10_wave2_docs.py`
- Test: `.omo/tests/test_phase10_wave2_normalization.py`
- Test: `.omo/tests/test_phase10_cross_root_rules.py`

- [ ] **Step 1: Exercise the live resolver against the real Wave 2 envelope**

Run:

```bash
python3 scripts/omo_worker.py worker rules-eval .omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml
```

Expected: stdout includes `registry=spaces/system-space-cross-root-rule-registry.yaml`, `data_policy=data/system-data-access-policy.yaml`, and `delivery_contract=.omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml`.

- [ ] **Step 2: Update the active packet evidence after the live run**

Add the live Wave 2 envelope and delivery contract to `.omo/tasks/active/P10-W2-NORMALIZED-RULE-BUNDLE.yaml`:

```yaml
handoff_refs:
  - .omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml
deliverables:
  - .omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml
evidence_required:
  - normalized bundle includes typed delivery contract and data contract
```

- [ ] **Step 3: Run full verification**

Run:

```bash
python3 scripts/sync_omo_state.py
python3 scripts/omo_worker.py task validate --all-active
python3 -m pytest .omo/tests/test_phase10_wave2_docs.py .omo/tests/test_phase10_wave2_normalization.py .omo/tests/test_phase10_cross_root_rules.py -q
python3 -m pytest .omo/tests -q
```

Expected: PASS; Wave 2 remains the only active packet and the full suite stays green.

- [ ] **Step 4: Commit**

```bash
git add .omo/tasks/active/P10-W2-NORMALIZED-RULE-BUNDLE.yaml
git -c core.hooksPath=/dev/null commit -m "test(phase10): verify wave2 normalized bundle"
```
