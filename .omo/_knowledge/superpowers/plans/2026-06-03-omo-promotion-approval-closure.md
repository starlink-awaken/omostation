# OMO Promotion Approval Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical promotion approval status surface that lets operators see requested/proposed/approved/verified lifecycle state while continuing to use the existing governance approve/apply commands.

**Architecture:** Add a pure helper in `scripts/omo_promotion_approval_status.py` that derives lifecycle entries from planned tasks, approval YAML, proposal YAML, and `_promotion_eval(...)` outputs. Expose that helper through `scripts/omo_worker.py task promotion-approval-status`, document the operator flow, and then rehearse the real `P19-W3-ARCHIVE-TS` request through `scripts/omo_governance.py approve/apply` so the new status surface and readiness surface close the loop together.

**Tech Stack:** Python 3, `pathlib`, `yaml`, existing `scripts/omo_governance.py`, existing `scripts/omo_promotion_approval.py`, existing `scripts/omo_worker.py`, pytest under `.omo/tests`, `.omo` YAML surfaces

---

## File map

- **Create:** `scripts/omo_promotion_approval_status.py`
  - Pure helper for status entry derivation, YAML packet construction, and Markdown rendering.
- **Modify:** `scripts/omo_worker.py`
  - Add `task promotion-approval-status` and write `.omo/workers/promotion/approvals/current.*`.
- **Create:** `.omo/tests/test_omo_promotion_approval_status.py`
  - Unit tests for lifecycle derivation and ordering.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - CLI regressions for `promotion-approval-status` and readiness after governance apply.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Docs regression for the new closure/status workflow.
- **Modify:** `.omo/workers/README.md`
- **Modify:** `.omo/AGENT.md`
- **Modify:** `.omo/tasks/README.md`
  - Document the operator flow: request → status → governance approve/apply → readiness.
- **Create:** `.omo/workers/promotion/approvals/current.yaml`
- **Create:** `.omo/workers/promotion/approvals/current.md`
  - Canonical status surfaces written by the new command.
- **Modify:** `.omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml`
- **Modify:** `.omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml`
- **Modify:** `.omo/workers/promotion/readiness.yaml`
  - Live closure rehearsal artifacts after approve/apply.

---

### Task 1: Build the pure promotion approval status helper

**Files:**
- Create: `scripts/omo_promotion_approval_status.py`
- Test: `.omo/tests/test_omo_promotion_approval_status.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_promotion_approval_status.py`:

```python
from __future__ import annotations

from scripts.omo_promotion_approval_status import (
    build_promotion_approval_status_packet,
    render_promotion_approval_status_markdown,
)


def test_build_status_packet_counts_requested_approved_and_granted_states():
    packet = build_promotion_approval_status_packet(
        generated_at="2026-06-03T00:00:00Z",
        tasks=[
            {
                "task_id": "TASK-REQ",
                "task_ref": ".omo/tasks/planned/TASK-REQ.yaml",
                "approval_ref": ".omo/workers/runs/TASK-REQ-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-REQ-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-REQ-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-REQ-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "proposed",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
            {
                "task_id": "TASK-APPROVED",
                "task_ref": ".omo/tasks/planned/TASK-APPROVED.yaml",
                "approval_ref": ".omo/workers/runs/TASK-APPROVED-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-APPROVED-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-APPROVED-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-APPROVED-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "approved",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
            {
                "task_id": "TASK-GRANTED",
                "task_ref": ".omo/tasks/planned/TASK-GRANTED.yaml",
                "approval_ref": ".omo/workers/runs/TASK-GRANTED-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-GRANTED-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "granted",
                "proposal_id": "TASK-GRANTED-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-GRANTED-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "verified",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["phase_mismatch"],
            },
        ],
    )

    assert packet["approval_task_count"] == 3
    assert packet["requested_count"] == 1
    assert packet["approved_pending_apply_count"] == 1
    assert packet["granted_count"] == 1


def test_build_status_packet_orders_blocked_then_lifecycle_then_task_id():
    packet = build_promotion_approval_status_packet(
        generated_at="2026-06-03T00:00:00Z",
        tasks=[
            {
                "task_id": "TASK-C",
                "task_ref": ".omo/tasks/planned/TASK-C.yaml",
                "approval_ref": ".omo/workers/runs/TASK-C-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-C-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "granted",
                "proposal_id": "TASK-C-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-C-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "verified",
                "human_approval_required": True,
                "eligible": True,
                "blockers": [],
            },
            {
                "task_id": "TASK-A",
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "approval_ref": ".omo/workers/runs/TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "approved",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
            {
                "task_id": "TASK-B",
                "task_ref": ".omo/tasks/planned/TASK-B.yaml",
                "approval_ref": ".omo/workers/runs/TASK-B-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "proposed",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
        ],
    )

    assert [entry["task_id"] for entry in packet["tasks"]] == ["TASK-B", "TASK-A", "TASK-C"]


def test_render_status_markdown_emits_operator_action_hints():
    markdown = render_promotion_approval_status_markdown(
        {
            "generated_at": "2026-06-03T00:00:00Z",
            "approval_task_count": 2,
            "requested_count": 1,
            "approved_pending_apply_count": 0,
            "granted_count": 1,
            "tasks": [
                {
                    "task_id": "TASK-A",
                    "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml",
                    "approval_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z",
                    "approval_status": "requested",
                    "proposal_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal",
                    "proposal_ref": ".omo/_truth/task-center/proposals/TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                    "proposal_status": "proposed",
                    "human_approval_required": True,
                    "eligible": False,
                    "blockers": ["approval_invalid"],
                },
                {
                    "task_id": "TASK-B",
                    "task_ref": ".omo/tasks/planned/TASK-B.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-B-promotion-approval-2026-06-03T00-00-00Z.yaml",
                    "approval_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z",
                    "approval_status": "granted",
                    "proposal_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal",
                    "proposal_ref": ".omo/_truth/task-center/proposals/TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                    "proposal_status": "verified",
                    "human_approval_required": True,
                    "eligible": False,
                    "blockers": ["phase_mismatch"],
                },
            ],
        }
    )

    assert "action=run governance approve" in markdown
    assert "action=approval blocker cleared; check readiness" in markdown
```

- [ ] **Step 2: Run helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_approval_status.py -q
```

Expected: import failure because `scripts/omo_promotion_approval_status.py` does not exist yet.

- [ ] **Step 3: Write minimal helper implementation**

Create `scripts/omo_promotion_approval_status.py`:

```python
from __future__ import annotations


_PROPOSAL_STATUS_ORDER = {"proposed": 0, "approved": 1, "verified": 2, "missing": 3}


def _ordered_tasks(tasks: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        tasks,
        key=lambda item: (
            0 if item["blockers"] else 1,
            _PROPOSAL_STATUS_ORDER.get(str(item["proposal_status"]), 99),
            str(item["task_id"]),
        ),
    )


def build_promotion_approval_status_packet(*, generated_at: str, tasks: list[dict[str, object]]) -> dict[str, object]:
    ordered = _ordered_tasks(tasks)
    return {
        "generated_at": generated_at,
        "approval_task_count": len(ordered),
        "requested_count": sum(
            1 for entry in ordered if entry["approval_status"] == "requested" and entry["proposal_status"] == "proposed"
        ),
        "approved_pending_apply_count": sum(
            1 for entry in ordered if entry["approval_status"] == "requested" and entry["proposal_status"] == "approved"
        ),
        "granted_count": sum(1 for entry in ordered if entry["approval_status"] == "granted"),
        "tasks": ordered,
    }


def _operator_action(entry: dict[str, object]) -> str:
    if entry["proposal_status"] == "proposed":
        return "run governance approve"
    if entry["proposal_status"] == "approved":
        return "run governance apply"
    return "approval blocker cleared; check readiness"


def render_promotion_approval_status_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Promotion Approval Status",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Approval tasks: {packet['approval_task_count']}",
        f"Requested: {packet['requested_count']}",
        f"Approved pending apply: {packet['approved_pending_apply_count']}",
        f"Granted: {packet['granted_count']}",
    ]
    for entry in packet["tasks"]:
        lines.extend(
            [
                "",
                f"## Task: {entry['task_id']}",
                "",
                f"proposal_status={entry['proposal_status']}",
                f"approval_status={entry['approval_status']}",
                f"blockers={','.join(entry['blockers']) or 'none'}",
                f"action={_operator_action(entry)}",
            ]
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run helper tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_approval_status.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit the helper slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_promotion_approval_status.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval status helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/tests/test_omo_promotion_approval_status.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval status helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Add CLI, docs, and governance-closure regressions

**Files:**
- Modify: `scripts/omo_worker.py`
- Modify: `.omo/tests/test_omo_automation.py`
- Modify: `.omo/tests/test_worker_mechanism_consistency.py`
- Modify: `.omo/workers/README.md`
- Modify: `.omo/AGENT.md`
- Modify: `.omo/tasks/README.md`

- [ ] **Step 1: Write the failing CLI/docs tests**

Add to `.omo/tests/test_omo_automation.py`:

```python
from scripts.omo_governance import approve_truth_mutation, apply_truth_mutation


def test_task_promotion_approval_status_rejects_task_without_task_specific_request(tmp_path: Path, monkeypatch):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml",
        {
            "id": "P17-W1-READY",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Ready packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-approval-status", "--task-id", "P17-W1-READY", "--omo-dir", ".omo"],
    )

    with pytest.raises(ValueError, match="task does not point to a task-specific promotion approval"):
        omo_worker_main()
```

Add:

```python
def test_task_promotion_approval_status_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-NEEDS-APPROVAL.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Approval-gated packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "P17-W1-NEEDS-APPROVAL",
            "approval_status": "requested",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "expires_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/P17-W1-NEEDS-APPROVAL.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal",
            "status": "proposed",
            "target": {
                "ref": ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-approval-status", "--omo-dir", ".omo", "--now", "2026-06-03T00:00:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml")

    assert "approval_task_count=1" in output
    assert packet["requested_count"] == 1
    assert packet["tasks"][0]["proposal_status"] == "proposed"
    assert (tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.md").exists()
```

Add:

```python
def test_governance_apply_clears_promotion_approval_invalid_blocker(tmp_path: Path, monkeypatch):
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-NEEDS-APPROVAL.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL",
            "phase": 17,
            "milestone": "M17.1",
            "priority": "P1",
            "title": "Approval-gated packet",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": ["_knowledge/demo.md"],
            "depends_on": [],
            "entry_gate": ["phase16_completed"],
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["demo"],
            "test_plan": ["demo"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "P17-W1-NEEDS-APPROVAL",
            "approval_status": "requested",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "expires_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/P17-W1-NEEDS-APPROVAL.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
        {
            "id": "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal",
            "title": "Grant promotion approval for P17-W1-NEEDS-APPROVAL",
            "operation_level": "L2",
            "requested_by": "copilot-cli",
            "target": {
                "ref": ".omo/workers/runs/P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z.yaml",
            },
            "changes": {"set": {"approval_status": "granted"}},
            "change_summary": "Grant promotion approval",
            "impact": "Releases a planned task into the promotion approval chain.",
            "verification_plan": ["python3 scripts/omo_worker.py task promote-eval P17-W1-NEEDS-APPROVAL --omo-dir .omo"],
            "rollback_plan": ["restore requested state"],
            "secret_refs": [],
            "trace_id": "trace-demo",
            "status": "proposed",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "applied_at": None,
            "verified_at": None,
        },
    )

    approve_truth_mutation(
        tmp_path,
        "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal",
        approver="copilot-cli",
        now="2026-06-03T00:10:00Z",
    )
    apply_truth_mutation(
        tmp_path,
        "P17-W1-NEEDS-APPROVAL-promotion-approval-2026-06-03T00-00-00Z-proposal",
        now="2026-06-03T00:15:00Z",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-readiness", "--omo-dir", ".omo", "--now", "2026-06-03T00:15:00Z"],
    )
    assert omo_worker_main() == 0
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml")

    assert packet["tasks"][0]["blockers"] == []
```

Add to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_promotion_approval_closure_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-approval-status" in workers_text
    assert "promotion-approval-status" in agent_text
    assert "promotion-approval-status" in tasks_text
    assert "omo_governance.py approve" in workers_text
```

- [ ] **Step 2: Run the focused CLI/docs tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval_status or promotion_approval_closure'
```

Expected: failures because the command and docs do not exist yet.

- [ ] **Step 3: Write minimal CLI/docs implementation**

In `scripts/omo_worker.py`, add:

```python
from scripts.omo_promotion_approval_status import (
    build_promotion_approval_status_packet,
    render_promotion_approval_status_markdown,
)


def _proposal_status(root: Path, proposal_ref: str) -> str:
    proposal_path = root / proposal_ref
    if not proposal_path.exists():
        return "missing"
    proposal = _load_yaml(proposal_path)
    return str(proposal.get("status", "missing"))


def _promotion_approval_status_entry(root: Path, task_path: Path, omo_dir: str | Path = ".omo") -> dict[str, object]:
    task = _load_yaml(task_path)
    approval_ref = str(task.get("approval_ref") or "")
    if not _task_has_task_specific_promotion_approval(approval_ref):
        raise ValueError("task does not point to a task-specific promotion approval")

    approval = _load_yaml(root / approval_ref)
    approval_id = str(approval.get("approval_id") or Path(approval_ref).stem)
    proposal_id = f"{approval_id}-proposal"
    proposal_ref = str(Path(omo_dir) / "_truth" / "task-center" / "proposals" / f"{proposal_id}.yaml")
    eval_result = _promotion_eval(root, task["id"], omo_dir=omo_dir)
    return {
        "task_id": task["id"],
        "task_ref": str(task_path.relative_to(root)),
        "approval_ref": approval_ref,
        "approval_id": approval_id,
        "approval_status": str(approval.get("approval_status", "missing")),
        "proposal_id": proposal_id,
        "proposal_ref": proposal_ref,
        "proposal_status": _proposal_status(root, proposal_ref),
        "human_approval_required": bool(task.get("human_approval_required")),
        "eligible": eval_result["eligible"],
        "blockers": eval_result["blockers"],
    }


def _write_task_promotion_approval_status(
    root: Path,
    omo_dir: str | Path = ".omo",
    now: str | None = None,
    task_id: str | None = None,
) -> int:
    omo = _omo_path(root, omo_dir)
    planned_dir = omo / "tasks" / "planned"
    task_paths = (
        [_find_planned_task_file(planned_dir, task_id)]
        if task_id
        else [
            path
            for path in sorted(planned_dir.glob("*.yaml"))
            if _task_has_task_specific_promotion_approval(_load_yaml(path).get("approval_ref"))
        ]
    )
    entries = [_promotion_approval_status_entry(root, path, omo_dir=omo_dir) for path in task_paths]
    packet = build_promotion_approval_status_packet(generated_at=now or _utc_now(), tasks=entries)
    approvals_dir = omo / "workers" / "promotion" / "approvals"
    approvals_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(approvals_dir / "current.yaml", packet)
    write_text_atomic(approvals_dir / "current.md", render_promotion_approval_status_markdown(packet))
    print(f"approval_task_count={packet['approval_task_count']} granted_count={packet['granted_count']}")
    return 0
```

Add parser/dispatch:

```python
promotion_approval_status_parser = task_sub.add_parser("promotion-approval-status")
promotion_approval_status_parser.add_argument("--omo-dir", default=".omo")
promotion_approval_status_parser.add_argument("--task-id")
promotion_approval_status_parser.add_argument("--now")

if args.command == "task" and args.task_command == "promotion-approval-status":
    return _write_task_promotion_approval_status(
        Path.cwd(),
        omo_dir=args.omo_dir,
        now=args.now,
        task_id=args.task_id,
    )
```

Update docs:

```md
# .omo/workers/README.md
- `python3 scripts/omo_worker.py task promotion-approval-status --omo-dir .omo [--task-id <TASK_ID>] [--now <ISO8601>]`
- Operators then run `python3 scripts/omo_governance.py approve <PROPOSAL_ID> --approver <ACTOR> --now <ISO8601>` and `python3 scripts/omo_governance.py apply <PROPOSAL_ID> --now <ISO8601>`.

# .omo/AGENT.md
- Promotion approval closure flow is: request -> promotion-approval-status -> omo_governance.py approve -> omo_governance.py apply -> promotion-readiness.

# .omo/tasks/README.md
- `promotion-approval-status` is the canonical read-side lifecycle surface for requested/granted promotion approvals.
```

- [ ] **Step 4: Re-run the focused CLI/docs tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval_status or promotion_approval_closure'
```

Expected: CLI/docs regressions pass.

- [ ] **Step 5: Run the combined status subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_promotion_approval_status.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval_status or promotion_approval_closure'
```

Expected: helper + CLI + docs coverage pass together.

- [ ] **Step 6: Commit the CLI/docs slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py omo_promotion_approval_status.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval status command" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/tasks/README.md && \
git -c core.hooksPath=/dev/null commit -m "docs(omo): document promotion approval closure flow" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Rehearse approve/apply on the live request and rehydrate closure surfaces

**Files:**
- Modify: `.omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml`
- Modify: `.omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml`
- Create: `.omo/workers/promotion/approvals/current.yaml`
- Create: `.omo/workers/promotion/approvals/current.md`
- Modify: `.omo/workers/promotion/readiness.yaml`

- [ ] **Step 1: Approve and apply the live proposal**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_governance.py approve P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal --approver copilot-cli --now 2026-06-03T00:10:00Z && \
python3 scripts/omo_governance.py apply P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal --now 2026-06-03T00:15:00Z
```

Expected:

1. proposal status becomes `verified`
2. approval YAML status becomes `granted`

- [ ] **Step 2: Refresh status and readiness surfaces**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-approval-status --omo-dir .omo --now 2026-06-03T00:15:00Z && \
python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo --now 2026-06-03T00:15:00Z
```

Expected:

1. `approvals/current.yaml` shows `proposal_status: verified`, `approval_status: granted`
2. `readiness.yaml` drops `approval_invalid` for `P19-W3-ARCHIVE-TS` and leaves only `phase_mismatch`

- [ ] **Step 3: Inspect the live closure state**

Check:

```yaml
# .omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml
approval_status: granted

# .omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml
status: verified

# .omo/workers/promotion/approvals/current.yaml
granted_count: 1
tasks:
  - task_id: P19-W3-ARCHIVE-TS
    proposal_status: verified
    approval_status: granted

# .omo/workers/promotion/readiness.yaml
tasks:
  - task_id: P19-W3-ARCHIVE-TS
    blockers:
      - phase_mismatch
```

- [ ] **Step 4: Run deterministic final verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/sync_omo_state.py --omo-dir .omo --now 2026-06-03T00:15:00Z && \
python3 scripts/omo_worker.py task promotion-history --omo-dir .omo --now 2026-06-03T00:15:00Z && \
python3 scripts/omo_worker.py task promotion-approval-status --omo-dir .omo --now 2026-06-03T00:15:00Z && \
python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo --now 2026-06-03T00:15:00Z && \
python3 scripts/omo_worker.py task validate --all-active && \
python3 scripts/omo_worker.py task validate --all-planned && \
python3 -m pytest .omo/tests -q
```

Expected: full `.omo` regression suite passes with the closure surface and live approved/applied artifact state in place.

- [ ] **Step 5: Commit the live closure rehearsal**

```bash
cd /Users/xiamingxing/Workspace && \
git add \
  .omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml \
  .omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml \
  .omo/workers/promotion/approvals/current.yaml \
  .omo/workers/promotion/approvals/current.md \
  .omo/workers/promotion/readiness.yaml && \
git -c core.hooksPath=/dev/null commit -m "chore(omo): rehearse promotion approval closure" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-review checklist

- Spec coverage:
  - status command/surface -> Task 2
  - lifecycle derivation -> Task 1
  - generic governance approve/apply remains mutation path -> Task 2 docs + Task 3 rehearsal
  - readiness unblock after apply -> Task 2 regression + Task 3 live rehearsal
- Placeholder scan:
  - no `TBD`, `TODO`, or “similar to above” shortcuts remain
- Type consistency:
  - command name stays `promotion-approval-status`
  - helper module stays `omo_promotion_approval_status.py`
  - live lifecycle remains `requested -> approved -> verified/granted`
