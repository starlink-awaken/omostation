---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---
# Product P0 WP2 Honest Agent Cell Receipt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every Agent Cell fixed-success effect and allow exactly one authority-bound, admission-bound, durable sandbox receipt path to return `effect=executed`.

**Architecture:** Keep true read-only actions local. Reject document/test/backup/snapshot claims as `not_executed`; route only `sandbox_digest_ref` through the existing `sandbox.digest_ref` ToolPack and Workflow Mesh receipt path after validating WP4's persisted principal authority context. No new effect adapter, receipt store, provider call, or external side effect is introduced.

**Tech Stack:** Python 3.13, pytest, Ruff, OMO Workflow Mesh, `sandbox_tool_runner.py`, WP4 principal authority contract, Git submodule child-first delivery.

## Global Constraints

- BET: `BET-Y1Q3-T4-05`; depends on completed `BET-Y1Q3-T4-04`.
- Accepted Spec: `docs/superpowers/specs/2026-08-28-product-p0-wp2-honest-agent-cell-receipt-design.md`.
- Only successful effect action: `sandbox_digest_ref`; it proves a durable no-external-side-effect invocation, not a generated document, real test run, backup, or snapshot.
- `generate_doc`, `create_draft`, `format_code`, `run_tests`, `backup`, `snapshot`, and `log` return `effect=not_executed`.
- WP2 consumes WP4's merged `validate_admitted_principal_context`; it never duplicates authority validation.
- OMO child PR/CI/main precedes the root pointer PR.
- Engineering/operational may reach `delivery_accepted`; value remains `NOT_PROVEN`.

---

### Task 1: Amend WP2 Scope and Truth Claims

**Files:**
- Modify: `docs/superpowers/specs/2026-08-28-product-p0-wp2-honest-agent-cell-receipt-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Consumes: merged WP4 helper `validate_admitted_principal_context(...) -> PrincipalAuthorityReceipt`.
- Produces: a Spec authorizing the two existing AGE regression tests and naming `sandbox_digest_ref` as the only receipt-backed success.

- [ ] **Step 1: Add the missing regression write surfaces**

Add exactly:

```text
projects/omo/tests/test_age_v2_e2e.py
projects/omo/tests/test_age_v2_production.py
```

- [ ] **Step 2: Lock the success and authority contracts**

The Spec must state:

```text
WP2 consumes omo.sovereignty.principal_authority.validate_admitted_principal_context.
The only effect action allowed to succeed is sandbox_digest_ref, backed by sandbox.digest_ref.
The receipt proves durable invocation/replay with external_side_effects=disabled.
All former fixed-success actions are explicitly unavailable.
```

- [ ] **Step 3: Recalculate T4-05's digest and merge the amendment**

Compile `prepare_bet_execution('BET-Y1Q3-T4-05')`, commit Spec and ledger in separate lanes, merge required checks, close the superseded amendment run as blocked, and start a fresh implementation run from merged main.

---

### Task 2: Add Fixed-Success and Plan-Aggregation RED Tests

**Files:**
- Create: `projects/omo/tests/test_resident_executor_truth.py`

**Interfaces:**
- Consumes: `Executor.execute_task(task)` and `Executor.execute_plan(plan)`.
- Produces: stable `not_executed` results and a false plan completion when an effect lacks a receipt.

- [ ] **Step 1: Add parameterized fixed-success rejection tests**

```python
from pathlib import Path

import pytest

from omo.resident.executor import Executor


@pytest.mark.parametrize(
    "action",
    [
        "generate_doc",
        "create_draft",
        "format_code",
        "run_tests",
        "backup",
        "snapshot",
        "log",
    ],
)
def test_effectful_action_without_admission_is_not_executed(
    tmp_path: Path,
    action: str,
) -> None:
    target = tmp_path / f"{action}.txt"
    result = Executor(backend="local").execute_task(
        {"action": action, "target": str(target)}
    )

    assert result == {
        "ok": False,
        "effect": "not_executed",
        "error": f"admitted workflow context required for effectful action: {action}",
    }
    assert not target.exists()


def test_plan_is_not_completed_from_fixed_success(tmp_path: Path) -> None:
    result = Executor(backend="local").execute_plan(
        {
            "plan_id": "plan-truth",
            "tasks": [
                {"action": "generate_doc", "target": str(tmp_path / "report.md")}
            ],
        }
    )

    assert result["completed"] is False
    assert result["results"][0]["effect"] == "not_executed"
```

- [ ] **Step 2: Run RED**

```bash
cd projects/omo
uv run pytest tests/test_resident_executor_truth.py \
  -k 'without_admission or fixed_success' -q
```

Expected: FAIL because current local branches return `ok=True` and do not report `effect`.

---

### Task 3: Implement Honest Classification and Receipt Enforcement

**Files:**
- Modify: `projects/omo/src/omo/resident/executor.py`

**Interfaces:**
- Consumes: full task context, `WorkflowMeshStore`, WP4 authority helper, and `run_sandbox_tool`.
- Produces: `sandbox-tool-receipt/v1` success or stable `not_executed` failure.

- [ ] **Step 1: Define action classes and constructor**

```python
READ_ONLY_ACTIONS = frozenset(
    {"read_file", "list_files", "search", "query_status", "get_info", "scan", "check", "validate"}
)
UNAVAILABLE_EFFECT_ACTIONS = frozenset(
    {"generate_doc", "create_draft", "format_code", "run_tests", "backup", "snapshot", "log"}
)
SANDBOX_EFFECT_ACTION = "sandbox_digest_ref"


class Executor:
    def __init__(
        self,
        backend: str = "local",
        *,
        omo_dir: Path | str | None = None,
    ) -> None:
        self.backend = backend
        self.omo_dir = Path(omo_dir) if omo_dir is not None else None
        self.execution_log: list[dict[str, Any]] = []
```

- [ ] **Step 2: Preserve the full task and stable rejection shape**

```python
def _not_executed(action: str, error: str | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "effect": "not_executed",
        "error": error
        or f"admitted workflow context required for effectful action: {action}",
    }


def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
    try:
        if self.backend == "local":
            return self._execute_local(task)
        if self.backend == "pi-worker":
            return self._execute_pi_worker(str(task.get("action", "")), str(task.get("target", "")))
        if self.backend == "multica":
            return self._execute_multica(str(task.get("action", "")), str(task.get("target", "")))
        return _not_executed(str(task.get("action", "")), f"Unsupported backend: {self.backend}")
    except Exception as exc:
        return _not_executed(str(task.get("action", "")), str(exc))
```

- [ ] **Step 3: Make plan completion receipt-aware**

```python
completed = bool(results) and all(
    result.get("ok") is True
    and (
        result.get("effect") != "executed"
        or (
            result.get("receipt_schema") == "sandbox-tool-receipt/v1"
            and bool(result.get("receipt_event_id"))
        )
    )
    for result in results
)
```

- [ ] **Step 4: Implement the single sandbox effect route**

Require these task keys:

```python
REQUIRED_SANDBOX_CONTEXT = (
    "workflow_run_id",
    "trace_id",
    "dispatch_id",
    "worker_id",
    "step_run_id",
    "admission_id",
    "packet_id",
    "packet_hash",
    "principal_authority_ref",
    "principal_receipt_digest",
    "input_ref",
    "input_digest",
)
```

Load `WorkflowMeshStore(self.omo_dir).snapshot(workflow_run_id)`, require a persisted admission, call:

```python
authority = validate_admitted_principal_context(
    admission,
    principal_authority_ref=str(task["principal_authority_ref"]),
    principal_receipt_digest=str(task["principal_receipt_digest"]),
    now=str(task.get("now") or datetime.now(UTC).isoformat()),
)
```

Require the admission `request_identity.packet_id` and `packet_hash` to match the task, then call the existing runner exactly:

```python
receipt = run_sandbox_tool(
    self.omo_dir,
    workflow_run_id=str(task["workflow_run_id"]),
    trace_id=str(task["trace_id"]),
    dispatch_id=str(task["dispatch_id"]),
    worker_id=str(task["worker_id"]),
    step_run_id=str(task["step_run_id"]),
    admission_id=str(task["admission_id"]),
    input_ref=str(task["input_ref"]),
    input_digest=str(task["input_digest"]),
    now=str(task.get("now") or datetime.now(UTC).isoformat()),
)
```

Return success only when `receipt_event_id` is non-empty:

```python
return {
    "ok": True,
    "effect": "executed",
    "receipt_schema": str(receipt["receipt_schema"]),
    "receipt_event_id": str(receipt["receipt_event_id"]),
    "idempotency_key": f"{task['workflow_run_id']}:sandbox-tool:{task['step_run_id']}",
    "external_side_effects": "disabled",
}
```

Expected: authority, admission, packet, worker, lease, and replay failures all return `not_executed` and append no new event.

---

### Task 4: Add Real Mesh Replay and Forgery Tests

**Files:**
- Modify: `projects/omo/tests/test_resident_executor_truth.py`

**Interfaces:**
- Consumes: the existing Workflow Mesh test builders and WP4 authority receipt fixture.
- Produces: one receipt-backed success, replay equality, and zero-event negative cases.

- [ ] **Step 1: Seed a real admitted worker context**

Reuse existing helpers that append `WorkflowRequested`, `WorkflowAdmitted`, `StepDispatched`, and `WorkerAcknowledged`; do not fabricate a snapshot dict outside the store. Capture `before = len(store.events())` before executing.

- [ ] **Step 2: Add replay-safe success**

```python
first = Executor(omo_dir=tmp_path).execute_task(task)
after_first = len(WorkflowMeshStore(tmp_path).events())
replay = Executor(omo_dir=tmp_path).execute_task(task)

assert first["ok"] is True
assert first["receipt_schema"] == "sandbox-tool-receipt/v1"
assert first["external_side_effects"] == "disabled"
assert replay == first
assert len(WorkflowMeshStore(tmp_path).events()) == after_first
```

- [ ] **Step 3: Parameterize forged identity cases**

Mutate `principal_receipt_digest`, `worker_id`, `packet_id`, `packet_hash`, and `input_digest` one at a time. Assert `ok=False`, `effect=not_executed`, and event count equals `before`.

---

### Task 5: Correct Existing AGE Truth Assertions

**Files:**
- Modify: `projects/omo/tests/test_age_v2_realworld.py`
- Modify: `projects/omo/tests/test_age_v2_e2e.py`
- Modify: `projects/omo/tests/test_age_v2_production.py`

**Interfaces:**
- Consumes: plans containing unsupported effect tasks.
- Produces: honest `completed=False` assertions while preserving true read-only successes.

- [ ] **Step 1: Replace fixed-success completion assertions**

For every plan containing an unavailable effect, assert:

```python
assert result["completed"] is False
effect_results = [item for item in result["results"] if item.get("effect") == "not_executed"]
assert effect_results
assert all(item["ok"] is False for item in effect_results)
```

- [ ] **Step 2: Run the full focused suite and Ruff**

```bash
cd projects/omo
uv run pytest \
  tests/test_resident_executor_truth.py \
  tests/test_age_v2_realworld.py \
  tests/test_age_v2_e2e.py \
  tests/test_age_v2_production.py \
  tests/test_sandbox_tool_runner.py -q
uv run ruff check \
  src/omo/resident/executor.py \
  tests/test_resident_executor_truth.py \
  tests/test_age_v2_realworld.py \
  tests/test_age_v2_e2e.py \
  tests/test_age_v2_production.py
```

Expected: all tests and Ruff PASS.

- [ ] **Step 3: Commit the OMO child change**

```bash
git add src/omo/resident/executor.py \
  tests/test_resident_executor_truth.py \
  tests/test_age_v2_realworld.py \
  tests/test_age_v2_e2e.py \
  tests/test_age_v2_production.py
git commit -m "fix(resident): require admitted effect receipts"
```

---

### Task 6: Child-First Delivery, Root Pointer, and Completion

**Files:**
- Child review: OMO files from Tasks 2-5
- Root pointer: `projects/omo`
- Coordinator-only completion: `docs/plans/3y-bet-ledger.yaml`
- Coordinator-only retro: `.omo/_knowledge/retros/BET-Y1Q3-T4-05.md`

**Interfaces:**
- Consumes: OMO child commit and live admitted sandbox receipt.
- Produces: child main, root main pointer, operational replay evidence, and `delivery_accepted`.

- [ ] **Step 1: Push the OMO child branch and merge its PR**

Run child CI and independent review. Resolve the merge SHA from `gh pr view --json mergeCommit --jq .mergeCommit.oid`, then prove it is an ancestor of child `origin/main`.

- [ ] **Step 2: Create a fresh root pointer-only attempt**

Update only `projects/omo` to the merged child-main SHA. Verify:

```bash
python3 bin/ssot/submodule-reachability-gate.py --source head --fetch --require-main --json
git diff --submodule=short origin/main...HEAD -- projects/omo
```

- [ ] **Step 3: Merge the root pointer PR and run the live admitted canary**

Execute `sandbox_digest_ref` through a real persisted admission/worker context. Restart the reader and prove the same receipt/event IDs are replayed without another event. Do not describe this as an external document/test/backup effect.

- [ ] **Step 4: Serialize completion and cleanup**

After engineering and operational receipts exist, set T4-05 to `delivery_accepted`, value=`NOT_PROVEN`, and `done`; write retro and cleanup receipts in coordinator-only commits. Retire child/root clones, merged branches, and workflow locks.

---

## Self-Review

- Spec coverage: fixed-success rejection, WP4 authority dependency, real Mesh receipt, replay, AGE regressions, child/root delivery, operational canary, and value firewall are explicit.
- Placeholder scan: runtime IDs and PR numbers are derived from command output; no unnamed implementation remains.
- Type consistency: Executor consumes full task dict; only `sandbox_digest_ref` maps to existing `sandbox.digest_ref`; receipt keys match `run_sandbox_tool`.
