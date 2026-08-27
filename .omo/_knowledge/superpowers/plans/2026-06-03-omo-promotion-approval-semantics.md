---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO Promotion Approval Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten promotion gates so `human_approval_required: true` planned tasks need a task-specific promotion approval artifact instead of any non-empty `approval_ref`.

**Architecture:** Add a focused helper in `scripts/omo_promotion_approval.py` that validates whether an `approval_ref` is a task-specific promotion approval record. Keep `_promotion_eval(...)` as the single gate authority by delegating approval qualification to that helper, so `promote-eval`, `promote-apply`, and `promotion-readiness` all inherit the same stricter contract.

**Tech Stack:** Python 3, `pathlib`, `yaml`, existing `scripts/omo_io.py` helpers, `argparse`, pytest under `.omo/tests`, `.omo` YAML templates and SSOT task packets

---

## File map

- **Create:** `scripts/omo_promotion_approval.py`
  - Pure helper for validating promotion approval refs and returning fail-closed status/blocker data.
- **Create:** `.omo/workers/templates/worker-promotion-approval.yaml`
  - Canonical template for task-specific promotion approval artifacts.
- **Create:** `.omo/tests/test_omo_promotion_approval.py`
  - Focused unit tests for missing ref, shared markdown ref, mismatched YAML, and valid YAML.
- **Modify:** `scripts/omo_worker.py`
  - Call the approval helper from `_promotion_eval(...)` and keep all downstream promotion surfaces aligned.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - Add `promote-eval` / `promotion-readiness` regressions for `approval_invalid`.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Add docs regression so the backlog-presence vs promotion-approval distinction stays documented.
- **Modify:** `.omo/workers/README.md`
  - Document the promotion approval template and the stricter gate meaning.
- **Modify:** `.omo/AGENT.md`
  - Tell operators that shared backlog-presence notes do not authorize promotion.
- **Modify:** `.omo/tasks/README.md`
  - Clarify `approval_ref` semantics for planned packets requiring human approval.
- **Modify:** `.omo/workers/promotion/readiness.yaml`
- **Modify:** `.omo/workers/promotion/readiness.md`
  - Rehydrate the live readiness surface so future human-approved tasks show `approval_invalid`.

---

### Task 1: Build the promotion approval helper and template

**Files:**
- Create: `scripts/omo_promotion_approval.py`
- Create: `.omo/workers/templates/worker-promotion-approval.yaml`
- Test: `.omo/tests/test_omo_promotion_approval.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_promotion_approval.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from scripts.omo_promotion_approval import evaluate_promotion_approval


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_evaluate_promotion_approval_returns_missing_when_ref_absent(tmp_path: Path):
    result = evaluate_promotion_approval(
        tmp_path,
        approval_ref=None,
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
    )

    assert result["approval_ready"] is False
    assert result["blocker"] == "approval_missing"


def test_evaluate_promotion_approval_rejects_shared_markdown_baseline_ref(tmp_path: Path):
    _write_text(
        tmp_path / ".omo" / "workers" / "runs" / "future-active-l2l3-pending-approval-2026-06-02.md",
        "# planning backlog presence only\n",
    )

    result = evaluate_promotion_approval(
        tmp_path,
        approval_ref=".omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md",
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
    )

    assert result["approval_ready"] is False
    assert result["blocker"] == "approval_invalid"


def test_evaluate_promotion_approval_rejects_yaml_for_different_task(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "OTHER-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "OTHER-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "OTHER",
            "approval_status": "granted",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": "2026-06-03T00:05:00Z",
            "expires_at": None,
            "approver": "human",
            "refs": {"task_ref": ".omo/tasks/planned/OTHER.yaml", "readiness_ref": ".omo/workers/promotion/readiness.yaml"},
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )

    result = evaluate_promotion_approval(
        tmp_path,
        approval_ref=".omo/workers/runs/OTHER-promotion-approval-2026-06-03T00-00-00Z.yaml",
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
    )

    assert result["approval_ready"] is False
    assert result["blocker"] == "approval_invalid"


def test_evaluate_promotion_approval_accepts_valid_task_specific_yaml(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "P19-W3-ARCHIVE-TS",
            "approval_status": "granted",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": "2026-06-03T00:05:00Z",
            "expires_at": None,
            "approver": "human",
            "refs": {
                "task_ref": ".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )

    result = evaluate_promotion_approval(
        tmp_path,
        approval_ref=".omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml",
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
    )

    assert result["approval_ready"] is True
    assert result["blocker"] is None
```

- [ ] **Step 2: Run the focused helper tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_approval.py -q
```

Expected: import failure because `scripts/omo_promotion_approval.py` does not exist yet.

- [ ] **Step 3: Write the minimal helper and template**

Create `scripts/omo_promotion_approval.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def evaluate_promotion_approval(
    root: Path,
    *,
    approval_ref: str | None,
    task_id: str,
    task_ref: str,
) -> dict[str, object]:
    if not approval_ref:
        return {"approval_ready": False, "blocker": "approval_missing"}
    if not approval_ref.endswith(".yaml"):
        return {"approval_ready": False, "blocker": "approval_invalid"}

    approval_path = root / approval_ref
    approval = _load_yaml(approval_path)
    if approval.get("task_id") != task_id:
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("approval_status") != "granted":
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("approval_scope") != "task.promote_apply":
        return {"approval_ready": False, "blocker": "approval_invalid"}
    if approval.get("refs", {}).get("task_ref") != task_ref:
        return {"approval_ready": False, "blocker": "approval_invalid"}
    return {"approval_ready": True, "blocker": None}
```

Create `.omo/workers/templates/worker-promotion-approval.yaml`:

```yaml
version: 1
approval_id: "<TASK_ID>-promotion-approval-<STAMP>"
task_id: "<TASK_ID>"
approval_status: "<requested|granted|denied|expired>"
requested_operation_level: "<L2|L3>"
approval_scope: "task.promote_apply"
requested_at: "<ISO8601>"
approved_at: null
expires_at: null
approver: null
refs:
  task_ref: ".omo/tasks/planned/<task-file>.yaml"
  readiness_ref: ".omo/workers/promotion/readiness.yaml"
evidence:
  request_evidence: []
  approval_evidence: []
```

- [ ] **Step 4: Re-run the helper tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_approval.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit the helper/template slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_promotion_approval.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/tests/test_omo_promotion_approval.py .omo/workers/templates/worker-promotion-approval.yaml && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit plus one root commit limited to the helper/template slice.

---

### Task 2: Tighten `_promotion_eval(...)` and protect docs/readiness behavior

**Files:**
- Modify: `scripts/omo_worker.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/workers/README.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tasks/README.md`

- [ ] **Step 1: Write the failing gate/docs tests**

Add to `.omo/tests/test_omo_automation.py`:

```python
def test_task_promote_eval_rejects_shared_backlog_presence_ref_for_human_approval_task(tmp_path: Path, monkeypatch, capsys):
    approval_note = tmp_path / ".omo" / "workers" / "runs" / "future-active-l2l3-pending-approval-2026-06-02.md"
    approval_note.parent.mkdir(parents=True, exist_ok=True)
    approval_note.write_text("# planning backlog presence only\n", encoding="utf-8")
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 18})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml",
        {
            "id": "P19-W3-ARCHIVE-TS",
            "phase": 19,
            "milestone": "M19.3",
            "priority": "P1",
            "title": "Archive TS",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase18_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L1",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["omo", "task", "promote-eval", "P19-W3-ARCHIVE-TS", "--omo-dir", ".omo"])

    assert omo_worker_main() == 1
    output = capsys.readouterr().out
    assert "approval_invalid" in output
```

Also add a readiness regression to `.omo/tests/test_omo_automation.py`:

```python
def test_task_promotion_readiness_reports_approval_invalid_for_future_human_approval_packets(tmp_path: Path, monkeypatch):
    approval_note = tmp_path / ".omo" / "workers" / "runs" / "future-active-l2l3-pending-approval-2026-06-02.md"
    approval_note.parent.mkdir(parents=True, exist_ok=True)
    approval_note.write_text("# planning backlog presence only\n", encoding="utf-8")
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml",
        {
            "id": "P19-W3-ARCHIVE-TS",
            "phase": 19,
            "milestone": "M19.3",
            "priority": "P1",
            "title": "Archive TS",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase18_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L1",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-readiness", "--omo-dir", ".omo", "--now", "2026-06-03T00:00:00Z"],
    )

    assert omo_worker_main() == 0
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml")
    assert packet["tasks"][0]["blockers"] == ["phase_mismatch", "approval_invalid"]
```

Add to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_distinguish_backlog_presence_approval_from_promotion_approval():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "worker-promotion-approval.yaml" in workers_text
    assert "does not authorize promotion" in agent_text
    assert "approval_invalid" in tasks_text
```

- [ ] **Step 2: Run the focused gate/docs tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'approval_invalid or backlog_presence_approval'
```

Expected: failures because `_promotion_eval(...)` still treats any non-empty `approval_ref` as ready and the docs do not yet describe the distinction.

- [ ] **Step 3: Tighten `_promotion_eval(...)` and update docs**

In `scripts/omo_worker.py`, import the helper and update the approval check:

```python
from scripts.omo_promotion_approval import evaluate_promotion_approval


def _promotion_eval(root: Path, task_id: str, omo_dir: str | Path = ".omo") -> dict[str, object]:
    omo = _omo_path(root, omo_dir)
    goals = _load_yaml(omo / "goals" / "current.yaml")
    task_file = _find_planned_task_file(omo / "tasks" / "planned", task_id)
    task = _load_yaml(task_file)
    active_target = omo / "tasks" / "active" / task_file.name

    approval_result = (
        {"approval_ready": True, "blocker": None}
        if not task.get("human_approval_required")
        else evaluate_promotion_approval(
            root,
            approval_ref=task.get("approval_ref"),
            task_id=task_id,
            task_ref=str(task_file.relative_to(root)),
        )
    )

    checks = {
        "queue_membership_ok": True,
        "status_ok": task.get("status") in {"candidate", "pending"},
        "phase_ok": task.get("phase") == int(goals["phase"]) + 1,
        "approval_ready": approval_result["approval_ready"],
        "target_path_clear": not active_target.exists(),
    }
    ...
    if approval_result["blocker"] == "approval_missing":
        blockers.append("approval_missing")
    elif approval_result["blocker"] == "approval_invalid":
        blockers.append("approval_invalid")
```

Update docs:

```md
# .omo/workers/README.md
- Human-approved planned packets need `.omo/workers/templates/worker-promotion-approval.yaml` records.
- Shared backlog-presence notes are informative only and do not authorize promotion.

# .omo/AGENT.md
- `future-active-l2l3-pending-approval-*.md` is backlog-presence evidence only; it does not authorize promotion.

# .omo/tasks/README.md
- For `human_approval_required: true` planned packets, `approval_ref` must point to a task-specific promotion approval YAML.
- Non-YAML or wrong-scope refs fail closed as `approval_invalid`.
```

- [ ] **Step 4: Re-run the focused gate/docs tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'approval_invalid or backlog_presence_approval'
```

Expected: promotion eval/readiness/docs regressions pass.

- [ ] **Step 5: Run the combined approval subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_promotion_approval.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval or approval_invalid or backlog_presence_approval'
```

Expected: helper + gate wiring + docs coverage pass together.

- [ ] **Step 6: Commit the gate/docs slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py omo_promotion_approval.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): tighten promotion approval gate" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/tasks/README.md && \
git -c core.hooksPath=/dev/null commit -m "docs(omo): clarify promotion approval semantics" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit plus one root commit limited to the stricter gate slice.

---

### Task 3: Rehydrate readiness and run deterministic final verification

**Files:**
- Modify: `.omo/workers/promotion/readiness.yaml`
- Modify: `.omo/workers/promotion/readiness.md`

- [ ] **Step 1: Materialize readiness with the stricter approval semantics**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo --now 2026-06-03T00:00:00Z
```

Expected: human-approved future packets backed only by the shared markdown note now include `approval_invalid`.

- [ ] **Step 2: Inspect the live readiness packet**

Confirm entries like `P19-W3-ARCHIVE-TS`, `P21-W1-IMMUNITY-METAOS`, `P21-W2-GENESIS-TRIAGE`, and `P24-W2-NUCLEUS-REPLACE` now show:

```yaml
eligible: false
blockers:
  - phase_mismatch
  - approval_invalid
```

- [ ] **Step 3: Run deterministic final verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/sync_omo_state.py --omo-dir .omo --now 2026-06-03T00:00:00Z && \
python3 scripts/omo_worker.py task promotion-history --omo-dir .omo --now 2026-06-03T00:00:00Z && \
python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo --now 2026-06-03T00:00:00Z && \
python3 scripts/omo_worker.py task validate --all-active && \
python3 scripts/omo_worker.py task validate --all-planned && \
python3 -m pytest .omo/tests -q
```

Expected: full `.omo` suite passes with readiness frozen to the deterministic timestamp.

- [ ] **Step 4: Commit the refreshed readiness surface**

```bash
cd /Users/xiamingxing/Workspace && \
git add .omo/workers/promotion/readiness.yaml .omo/workers/promotion/readiness.md && \
git -c core.hooksPath=/dev/null commit -m "chore(omo): freeze promotion approval readiness state" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one root commit containing only the deterministic readiness surface changes.

---

## Self-review checklist

- Spec coverage:
  - task-specific immutable approval artifact -> Task 1
  - tighter `_promotion_eval(...)` semantics -> Task 2
  - readiness truthfulness -> Task 2 + Task 3
  - docs distinction -> Task 2
  - deterministic verification -> Task 3
- Placeholder scan:
  - no `TBD`, `TODO`, or “similar to above” shortcuts remain
- Type consistency:
  - helper returns `approval_ready` + `blocker`
  - blockers remain `approval_missing` or `approval_invalid`
  - readiness output still uses existing `eligible`, `blockers`, `checks`, `errors`
