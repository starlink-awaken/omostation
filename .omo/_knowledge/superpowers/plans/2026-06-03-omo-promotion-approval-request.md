---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO Promotion Approval Request Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a task-side workflow that requests promotion approval by creating a task-specific requested approval YAML, updating the planned task to point at it, and emitting a governance proposal for later human release.

**Architecture:** Add a small pure helper in `scripts/omo_promotion_request.py` that builds the requested approval record and proposal payload. Keep the operator entrypoint in `scripts/omo_worker.py` as `task promotion-request-approval`, reusing existing planned-task lookup and governance proposal infrastructure so the stricter promotion gate remains unchanged and simply starts seeing task-specific `requested` artifacts instead of shared baseline notes.

**Tech Stack:** Python 3, `pathlib`, `yaml`, existing `scripts/omo_governance.py` truth proposal helper, existing `scripts/omo_io.py` atomic writers, `argparse`, pytest under `.omo/tests`, `.omo` YAML task and worker artifacts

---

## File map

- **Create:** `scripts/omo_promotion_request.py`
  - Pure helper for building request approval YAML paths, request records, and proposal payloads.
- **Modify:** `scripts/omo_worker.py`
  - Add `task promotion-request-approval` and wire it to the helper + planned task mutation flow.
- **Create:** `.omo/tests/test_omo_promotion_request.py`
  - Focused unit tests for request record/proposal payload generation.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - Add CLI regressions for request rejection, record/proposal creation, and duplicate-request blocking.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Add docs regression for the new request command and task-specific approval workflow.
- **Modify:** `.omo/workers/README.md`
  - Document the request command and the new artifact path.
- **Modify:** `.omo/AGENT.md`
  - Document that operators should request promotion approval instead of hand-authoring YAML.
- **Modify:** `.omo/tasks/README.md`
  - Document how `promotion-request-approval` updates `approval_ref`.
- **Create:** `.omo/workers/runs/<TASK_ID>-promotion-approval-<STAMP>.yaml`
  - Requested approval artifact produced during live rehearsal.
- **Modify:** `.omo/tasks/planned/<TASK_ID>.yaml`
  - Rehearsal task’s `approval_ref` points at the new requested artifact.
- **Modify:** `.omo/workers/promotion/readiness.yaml`
- **Modify:** `.omo/workers/promotion/readiness.md`
  - Rehydrate after the live rehearsal so the queue reflects task-specific `requested` approval refs.

---

### Task 1: Build the pure promotion request helper

**Files:**
- Create: `scripts/omo_promotion_request.py`
- Test: `.omo/tests/test_omo_promotion_request.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_promotion_request.py`:

```python
from __future__ import annotations

from scripts.omo_promotion_request import (
    build_promotion_approval_proposal,
    build_promotion_approval_request,
    promotion_approval_ref,
)


def test_promotion_approval_ref_uses_task_id_and_timestamp_slug():
    assert promotion_approval_ref("P19-W3-ARCHIVE-TS", "2026-06-03T00:00:00Z") == (
        ".omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml"
    )


def test_build_promotion_approval_request_creates_requested_record():
    approval_ref = promotion_approval_ref("P19-W3-ARCHIVE-TS", "2026-06-03T00:00:00Z")

    record = build_promotion_approval_request(
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
        requested_operation_level="L2",
        requested_at="2026-06-03T00:00:00Z",
        approval_ref=approval_ref,
    )

    assert record["approval_id"] == "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z"
    assert record["approval_status"] == "requested"
    assert record["approval_scope"] == "task.promote_apply"
    assert record["refs"]["task_ref"] == ".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml"
    assert record["refs"]["readiness_ref"] == ".omo/workers/promotion/readiness.yaml"


def test_build_promotion_approval_proposal_targets_requested_record():
    approval_ref = promotion_approval_ref("P19-W3-ARCHIVE-TS", "2026-06-03T00:00:00Z")

    proposal = build_promotion_approval_proposal(
        task_id="P19-W3-ARCHIVE-TS",
        requested_by="copilot-cli",
        approval_ref=approval_ref,
    )

    assert proposal["id"] == "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal"
    assert proposal["target"]["ref"] == approval_ref
    assert proposal["changes"]["set"]["approval_status"] == "granted"
    assert proposal["requested_by"] == "copilot-cli"
```

- [ ] **Step 2: Run the focused helper tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_request.py -q
```

Expected: import failure because `scripts/omo_promotion_request.py` does not exist yet.

- [ ] **Step 3: Write the minimal helper implementation**

Create `scripts/omo_promotion_request.py`:

```python
from __future__ import annotations


def _timestamp_slug(now: str) -> str:
    return now.replace(":", "-")


def promotion_approval_ref(task_id: str, now: str) -> str:
    return f".omo/workers/runs/{task_id}-promotion-approval-{_timestamp_slug(now)}.yaml"


def build_promotion_approval_request(
    *,
    task_id: str,
    task_ref: str,
    requested_operation_level: str,
    requested_at: str,
    approval_ref: str,
) -> dict[str, object]:
    approval_id = approval_ref.rsplit("/", 1)[-1].removesuffix(".yaml")
    return {
        "version": 1,
        "approval_id": approval_id,
        "task_id": task_id,
        "approval_status": "requested",
        "requested_operation_level": requested_operation_level,
        "approval_scope": "task.promote_apply",
        "requested_at": requested_at,
        "approved_at": None,
        "expires_at": None,
        "approver": None,
        "refs": {
            "task_ref": task_ref,
            "readiness_ref": ".omo/workers/promotion/readiness.yaml",
        },
        "evidence": {
            "request_evidence": [],
            "approval_evidence": [],
        },
    }


def build_promotion_approval_proposal(
    *,
    task_id: str,
    requested_by: str,
    approval_ref: str,
) -> dict[str, object]:
    approval_id = approval_ref.rsplit("/", 1)[-1].removesuffix(".yaml")
    return {
        "id": f"{approval_id}-proposal",
        "title": f"Grant promotion approval for {task_id}",
        "operation_level": "L2",
        "requested_by": requested_by,
        "target": {"ref": approval_ref},
        "changes": {"set": {"approval_status": "granted"}},
        "change_summary": f"Grant promotion approval for {task_id}",
        "impact": "Releases a planned task into the promotion approval chain.",
        "verification_plan": [
            f"python3 scripts/omo_worker.py task promote-eval {task_id} --omo-dir .omo",
        ],
        "rollback_plan": [
            f"Set {approval_ref} approval_status back to requested if the release must be withdrawn.",
        ],
        "secret_refs": [],
        "trace_id": f"trace-{approval_id}",
    }
```

- [ ] **Step 4: Re-run the helper tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_request.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit the helper slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_promotion_request.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval request helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/tests/test_omo_promotion_request.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval request helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit plus one root commit limited to the helper slice.

---

### Task 2: Add `promotion-request-approval` CLI and docs guardrails

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
def test_task_promotion_request_approval_rejects_non_human_approval_task(tmp_path: Path, monkeypatch):
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "P17-W1-READY.yaml", {
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
    })

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-request-approval",
            "P17-W1-READY",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    with pytest.raises(ValueError, match="task does not require human approval"):
        omo_worker_main()
```

Also add:

```python
def test_task_promotion_request_approval_writes_requested_record_and_governance_proposal(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml", {
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
    })

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-request-approval",
            "P19-W3-ARCHIVE-TS",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-06-03T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    task_packet = _load_yaml(tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml")
    approval_ref = ".omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml"
    proposal_ref = ".omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml"

    assert f"approval_ref={approval_ref}" in output
    assert f"proposal_ref={proposal_ref}" in output
    assert task_packet["approval_ref"] == approval_ref
    assert (tmp_path / approval_ref).exists()
    assert (tmp_path / proposal_ref).exists()
```

And duplicate-request blocking:

```python
def test_task_promotion_request_approval_rejects_duplicate_task_specific_request(tmp_path: Path, monkeypatch):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "P19-W3-ARCHIVE-TS",
            "approval_status": "requested",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "expires_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "P19-W3-ARCHIVE-TS.yaml", {
        "id": "P19-W3-ARCHIVE-TS",
        "phase": 19,
        "milestone": "M19.3",
        "priority": "P1",
        "title": "Archive TS",
        "status": "pending",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": ".omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml",
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
    })

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "omo",
            "task",
            "promotion-request-approval",
            "P19-W3-ARCHIVE-TS",
            "--requested-by",
            "copilot-cli",
            "--now",
            "2026-06-04T00:00:00Z",
            "--omo-dir",
            ".omo",
        ],
    )

    with pytest.raises(ValueError, match="task already points to a task-specific promotion approval"):
        omo_worker_main()
```

Add to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_promotion_request_workflow():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-request-approval" in workers_text
    assert "promotion-request-approval" in agent_text
    assert "promotion-request-approval" in tasks_text
```

- [ ] **Step 2: Run the focused CLI/docs tests to confirm RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_request_approval or promotion_request_workflow'
```

Expected: failures because the CLI subcommand and docs do not exist yet.

- [ ] **Step 3: Wire the CLI and update docs**

In `scripts/omo_worker.py`, import the helper and add:

```python
from scripts.omo_governance import propose_truth_mutation
from scripts.omo_promotion_request import (
    build_promotion_approval_proposal,
    build_promotion_approval_request,
    promotion_approval_ref,
)


def _task_has_task_specific_promotion_approval(approval_ref: str | None) -> bool:
    return bool(approval_ref and approval_ref.endswith(".yaml") and "-promotion-approval-" in approval_ref)


def _request_task_promotion_approval(
    root: Path,
    task_id: str,
    requested_by: str,
    now: str,
    omo_dir: str | Path = ".omo",
) -> int:
    omo = _omo_path(root, omo_dir)
    task_path = _find_planned_task_file(omo / "tasks" / "planned", task_id)
    task = _load_yaml(task_path)
    if not task.get("human_approval_required"):
        raise ValueError("task does not require human approval")
    if task.get("status") not in {"candidate", "pending"}:
        raise ValueError("task must remain candidate or pending before requesting promotion approval")
    if _task_has_task_specific_promotion_approval(task.get("approval_ref")):
        raise ValueError("task already points to a task-specific promotion approval")

    approval_ref = promotion_approval_ref(task_id, now)
    approval_record = build_promotion_approval_request(
        task_id=task_id,
        task_ref=str(task_path.relative_to(root)),
        requested_operation_level=str(task["risk_level"]),
        requested_at=now,
        approval_ref=approval_ref,
    )
    proposal = build_promotion_approval_proposal(
        task_id=task_id,
        requested_by=requested_by,
        approval_ref=approval_ref,
    )

    _write_yaml(root / approval_ref, approval_record)
    task["approval_ref"] = approval_ref
    _write_yaml(task_path, task)
    propose_truth_mutation(root, proposal, now=now)
    print(f"approval_ref={approval_ref} proposal_ref=.omo/_truth/task-center/proposals/{proposal['id']}.yaml")
    return 0
```

Add parser/dispatch:

```python
promotion_request_parser = task_sub.add_parser("promotion-request-approval")
promotion_request_parser.add_argument("task_id")
promotion_request_parser.add_argument("--requested-by", required=True)
promotion_request_parser.add_argument("--now", required=True)
promotion_request_parser.add_argument("--omo-dir", default=".omo")

if args.command == "task" and args.task_command == "promotion-request-approval":
    return _request_task_promotion_approval(
        Path.cwd(),
        args.task_id,
        requested_by=args.requested_by,
        now=args.now,
        omo_dir=args.omo_dir,
    )
```

Update docs:

```md
# .omo/workers/README.md
- `python3 scripts/omo_worker.py task promotion-request-approval <TASK_ID> --requested-by <ACTOR> --now <ISO8601> --omo-dir .omo`
- This writes `.omo/workers/runs/<TASK_ID>-promotion-approval-<STAMP>.yaml` and a proposal under `.omo/_truth/task-center/proposals/`.

# .omo/AGENT.md
- When a human-approved planned packet shows `approval_invalid`, request task-specific promotion approval with `promotion-request-approval` instead of hand-editing YAML.

# .omo/tasks/README.md
- `promotion-request-approval` rewrites a planned task’s `approval_ref` from the shared backlog note to a task-specific requested approval YAML.
```

- [ ] **Step 4: Re-run the focused CLI/docs tests to confirm GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest .omo/tests/test_omo_automation.py .omo/tests/test_worker_mechanism_consistency.py -q -k 'promotion_request_approval or promotion_request_workflow'
```

Expected: request command + docs regressions pass.

- [ ] **Step 5: Run the combined request subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_promotion_request.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_request_approval or promotion_request_workflow or promotion_request'
```

Expected: helper + CLI + docs coverage pass together.

- [ ] **Step 6: Commit the CLI/docs slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py omo_promotion_request.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval request workflow" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/tasks/README.md && \
git -c core.hooksPath=/dev/null commit -m "docs(omo): document promotion approval request" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one `scripts` commit plus one root commit limited to the request workflow slice.

---

### Task 3: Rehearse one live request and run deterministic final verification

**Files:**
- Modify: `.omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml`
- Create: `.omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml`
- Create: `.omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml`
- Modify: `.omo/workers/promotion/readiness.yaml`
- Modify: `.omo/workers/promotion/readiness.md`

- [ ] **Step 1: Rehearse the request command on one real future human-approved packet**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-request-approval P19-W3-ARCHIVE-TS --requested-by copilot-cli --now 2026-06-03T00:00:00Z --omo-dir .omo
```

Expected: stdout includes both:

1. `approval_ref=.omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml`
2. `proposal_ref=.omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml`

- [ ] **Step 2: Rehydrate readiness deterministically**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo --now 2026-06-03T00:00:00Z
```

Expected: `P19-W3-ARCHIVE-TS` still shows `approval_invalid`, but its `approval_ref` now points at the task-specific requested YAML instead of the shared baseline note.

- [ ] **Step 3: Inspect the rehearsal artifacts**

Check:

```yaml
# .omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml
approval_status: requested
approval_scope: task.promote_apply
refs:
  task_ref: .omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml

# .omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml
status: proposed
target:
  ref: .omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml
changes:
  set:
    approval_status: granted
```

- [ ] **Step 4: Run deterministic final verification**

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

Expected: full `.omo` suite passes with the requested approval workflow artifacts in place.

- [ ] **Step 5: Commit the rehearsal state**

```bash
cd /Users/xiamingxing/Workspace && \
git add \
  .omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml \
  .omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml \
  .omo/_truth/task-center/proposals/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml \
  .omo/workers/promotion/readiness.yaml \
  .omo/workers/promotion/readiness.md && \
git -c core.hooksPath=/dev/null commit -m "chore(omo): rehearse promotion approval request" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one root commit containing only the live request rehearsal and refreshed readiness surface.

---

## Self-review checklist

- Spec coverage:
  - request command -> Task 2
  - requested approval artifact -> Task 1 + Task 3
  - governance proposal emission -> Task 1 + Task 2 + Task 3
  - readiness remains fail-closed until grant -> Task 2 + Task 3
- Placeholder scan:
  - no `TBD`, `TODO`, or “similar to above” shortcuts remain
- Type consistency:
  - command name stays `promotion-request-approval`
  - helper names stay `promotion_approval_ref`, `build_promotion_approval_request`, `build_promotion_approval_proposal`
  - approval status remains `requested` until a later governance step grants it
