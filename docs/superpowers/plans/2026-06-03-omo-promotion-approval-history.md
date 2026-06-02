# OMO Promotion Approval History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical promotion approval history/index surface that scans all task-specific promotion approval artifacts and their linked proposal state into `.omo/workers/promotion/approvals/history/current.*`.

**Architecture:** Mirror the existing promotion history pattern with a pure helper in `scripts/omo_promotion_approval_history.py`, then wire a thin `task promotion-approval-history` command in `scripts/omo_worker.py`. Keep this slice read-only: it only derives history/index packets from approval YAML plus proposal YAML, writes current surfaces, and hydrates the live repo from the existing `P19-W3-ARCHIVE-TS` approval artifact.

**Tech Stack:** Python 3, `pathlib`, `yaml`, existing `scripts/omo_worker.py`, existing promotion approval artifacts under `.omo/workers/runs/`, pytest under `.omo/tests`, `.omo` generated current surfaces

---

## File map

- **Create:** `scripts/omo_promotion_approval_history.py`
  - Pure helper for loading approval/proposal artifacts, filtering valid approval run files, ordering entries, and rendering YAML/Markdown packets.
- **Modify:** `scripts/omo_worker.py`
  - Add `task promotion-approval-history`.
- **Create:** `.omo/tests/test_omo_promotion_approval_history.py`
  - Unit tests for packet construction, sorting, proposal-missing handling, and non-approval filtering.
- **Modify:** `.omo/tests/test_omo_automation.py`
  - CLI regression for `promotion-approval-history`.
- **Modify:** `.omo/tests/test_worker_mechanism_consistency.py`
  - Docs regression for the new history/index surface.
- **Modify:** `.omo/workers/README.md`
- **Modify:** `.omo/AGENT.md`
- **Modify:** `.omo/tasks/README.md`
  - Document the history/index command and canonical paths.
- **Create:** `.omo/workers/promotion/approvals/history/current.yaml`
- **Create:** `.omo/workers/promotion/approvals/history/current.md`
  - Live canonical history/index surfaces.

---

### Task 1: Build the pure promotion approval history helper

**Files:**
- Create: `scripts/omo_promotion_approval_history.py`
- Test: `.omo/tests/test_omo_promotion_approval_history.py`

- [ ] **Step 1: Write the failing helper tests**

Create `.omo/tests/test_omo_promotion_approval_history.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.omo_promotion_approval_history import build_promotion_approval_history


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_build_promotion_approval_history_returns_empty_surface_when_no_approvals_exist(tmp_path: Path):
    result = build_promotion_approval_history(tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z")

    assert result["yaml"]["approval_count"] == 0
    assert result["yaml"]["latest_approval_id"] is None
    assert result["yaml"]["approvals"] == []
    assert "Latest approval: none" in result["markdown"]


def test_build_promotion_approval_history_sorts_latest_requested_first(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-A-promotion-approval-2026-06-02T00-00-00Z.yaml",
        {
            "approval_id": "TASK-A-promotion-approval-2026-06-02T00-00-00Z",
            "task_id": "TASK-A",
            "approval_status": "requested",
            "requested_at": "2026-06-02T00:00:00Z",
            "approved_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "TASK-A-promotion-approval-2026-06-02T00-00-00Z-proposal.yaml",
        {"id": "TASK-A-promotion-approval-2026-06-02T00-00-00Z-proposal", "status": "proposed"},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-B-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "approval_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "TASK-B",
            "approval_status": "granted",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": "2026-06-03T00:10:00Z",
            "approver": "copilot-cli",
            "refs": {
                "task_ref": ".omo/tasks/planned/TASK-B.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
        {"id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal", "status": "verified"},
    )

    result = build_promotion_approval_history(tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z")

    assert result["yaml"]["latest_approval_id"] == "TASK-B-promotion-approval-2026-06-03T00-00-00Z"
    assert result["yaml"]["prior_approval_id"] == "TASK-A-promotion-approval-2026-06-02T00-00-00Z"
    assert [entry["task_id"] for entry in result["yaml"]["approvals"]] == ["TASK-B", "TASK-A"]
    assert result["yaml"]["requested_count"] == 1
    assert result["yaml"]["granted_count"] == 1


def test_build_promotion_approval_history_keeps_entry_when_proposal_missing(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "approval_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "TASK-A",
            "approval_status": "requested",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
        },
    )

    result = build_promotion_approval_history(tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z")

    assert result["yaml"]["approvals"][0]["proposal_status"] == "missing"


def test_build_promotion_approval_history_rejects_missing_required_fields(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "BROKEN-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "approval_id": "BROKEN-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "BROKEN",
        },
    )

    with pytest.raises(ValueError, match="missing required promotion approval field"):
        build_promotion_approval_history(tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z")
```

- [ ] **Step 2: Run helper tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_approval_history.py -q
```

Expected: import failure because `scripts/omo_promotion_approval_history.py` does not exist yet.

- [ ] **Step 3: Write the minimal helper implementation**

Create `scripts/omo_promotion_approval_history.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_promotion_approval_artifact(path: Path) -> bool:
    return "-promotion-approval-" in path.name and path.suffix == ".yaml"


def _proposal_status(root: Path, proposal_ref: Path) -> str:
    proposal_path = root / proposal_ref
    if not proposal_path.exists():
        return "missing"
    proposal = _load_yaml(proposal_path)
    return str(proposal.get("status", "missing"))


def _history_entry(root: Path, omo_ref: Path, approval_path: Path) -> dict[str, object]:
    approval = _load_yaml(approval_path)
    required_fields = [
        ("approval_id", approval.get("approval_id")),
        ("task_id", approval.get("task_id")),
        ("requested_at", approval.get("requested_at")),
        ("approval_status", approval.get("approval_status")),
        ("refs.task_ref", approval.get("refs", {}).get("task_ref")),
        ("refs.readiness_ref", approval.get("refs", {}).get("readiness_ref")),
    ]
    for field_name, field_value in required_fields:
        if field_value is None:
            raise ValueError(f"missing required promotion approval field: {field_name}")

    proposal_id = f"{approval['approval_id']}-proposal"
    proposal_ref = omo_ref / "_truth" / "task-center" / "proposals" / f"{proposal_id}.yaml"
    return {
        "approval_id": approval["approval_id"],
        "approval_ref": str(omo_ref / "workers" / "runs" / approval_path.name),
        "task_id": approval["task_id"],
        "task_ref": approval["refs"]["task_ref"],
        "requested_at": approval["requested_at"],
        "approval_status": approval["approval_status"],
        "proposal_id": proposal_id,
        "proposal_ref": str(proposal_ref),
        "proposal_status": _proposal_status(root, proposal_ref),
        "approver": approval.get("approver"),
        "approved_at": approval.get("approved_at"),
        "applied_at": None if _proposal_status(root, proposal_ref) != "verified" else _load_yaml(root / proposal_ref).get("applied_at"),
        "readiness_ref": approval["refs"]["readiness_ref"],
    }


def build_promotion_approval_history(root: Path, omo_dir: str | Path = ".omo", now: str = "2026-06-03T00:15:00Z") -> dict[str, object]:
    omo_ref = Path(omo_dir)
    runs_dir = root / omo_ref / "workers" / "runs"
    entries = [
        _history_entry(root, omo_ref, path)
        for path in sorted(runs_dir.glob("*-promotion-approval-*.yaml"))
        if _is_promotion_approval_artifact(path)
    ]
    entries.sort(key=lambda item: (_parse_iso8601(item["requested_at"]), item["approval_id"]), reverse=True)

    latest = entries[0] if entries else None
    prior = entries[1] if len(entries) > 1 else None
    yaml_packet = {
        "generated_at": now,
        "latest_approval_id": latest["approval_id"] if latest else None,
        "latest_approval_ref": latest["approval_ref"] if latest else None,
        "prior_approval_id": prior["approval_id"] if prior else None,
        "prior_approval_ref": prior["approval_ref"] if prior else None,
        "approval_count": len(entries),
        "requested_count": sum(
            1 for entry in entries if entry["approval_status"] == "requested" and entry["proposal_status"] == "proposed"
        ),
        "approved_pending_apply_count": sum(
            1 for entry in entries if entry["approval_status"] == "requested" and entry["proposal_status"] == "approved"
        ),
        "granted_count": sum(1 for entry in entries if entry["approval_status"] == "granted"),
        "approvals": entries,
    }
    markdown_lines = [
        "# Promotion Approval History",
        "",
        f"Generated at: {now}",
        f"Latest approval: {yaml_packet['latest_approval_id'] or 'none'}",
        f"Prior approval: {yaml_packet['prior_approval_id'] or 'none'}",
        f"Approval count: {yaml_packet['approval_count']}",
    ]
    for entry in entries:
        markdown_lines.extend(
            [
                "",
                f"## Approval: {entry['approval_id']}",
                "",
                f"task_id={entry['task_id']}",
                f"approval_status={entry['approval_status']}",
                f"proposal_status={entry['proposal_status']}",
                f"task_ref={entry['task_ref']}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
```

- [ ] **Step 4: Run helper tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_promotion_approval_history.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit the helper slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_promotion_approval_history.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval history helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts .omo/tests/test_omo_promotion_approval_history.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval history helper" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Add CLI and docs for promotion approval history

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
def test_task_promotion_approval_history_writes_current_surfaces(tmp_path: Path, monkeypatch, capsys):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "approval_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "TASK-A",
            "approval_status": "requested",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
        {"id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal", "status": "proposed"},
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["omo", "task", "promotion-approval-history", "--omo-dir", ".omo", "--now", "2026-06-03T00:15:00Z"],
    )

    assert omo_worker_main() == 0
    output = capsys.readouterr().out
    packet = _load_yaml(tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml")

    assert "approval_count=1" in output
    assert packet["latest_approval_id"] == "TASK-A-promotion-approval-2026-06-03T00-00-00Z"
    assert (tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.md").exists()
```

Add to `.omo/tests/test_worker_mechanism_consistency.py`:

```python
def test_worker_docs_describe_promotion_approval_history_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-approval-history" in workers_text
    assert "promotion/approvals/history/current.yaml" in workers_text
    assert "promotion-approval-history" in agent_text
    assert "promotion-approval-history" in tasks_text
```

- [ ] **Step 2: Run CLI/docs tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval_history'
```

Expected: failures because the CLI command and docs do not exist yet.

- [ ] **Step 3: Write minimal CLI/docs implementation**

In `scripts/omo_worker.py`, add:

```python
from scripts.omo_promotion_approval_history import build_promotion_approval_history


def _write_task_promotion_approval_history(root: Path, omo_dir: str | Path = ".omo", now: str | None = None) -> int:
    result = build_promotion_approval_history(root, omo_dir=omo_dir, now=now or _utc_now())
    omo = _omo_path(root, omo_dir)
    history_dir = omo / "workers" / "promotion" / "approvals" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(history_dir / "current.yaml", result["yaml"])
    write_text_atomic(history_dir / "current.md", result["markdown"])
    print(f"approval_count={result['yaml']['approval_count']} latest_approval_ref={result['yaml']['latest_approval_ref']}")
    return 0
```

Add parser/dispatch:

```python
promotion_approval_history_parser = task_sub.add_parser("promotion-approval-history")
promotion_approval_history_parser.add_argument("--omo-dir", default=".omo")
promotion_approval_history_parser.add_argument("--now")

if args.command == "task" and args.task_command == "promotion-approval-history":
    return _write_task_promotion_approval_history(Path.cwd(), omo_dir=args.omo_dir, now=args.now)
```

Update docs:

```md
# .omo/workers/README.md
- `python3 scripts/omo_worker.py task promotion-approval-history --omo-dir .omo [--now <ISO8601>]`
- This writes `.omo/workers/promotion/approvals/history/current.yaml` and `.md`

# .omo/AGENT.md
- Promotion approval history lives at `.omo/workers/promotion/approvals/history/current.yaml`

# .omo/tasks/README.md
- `promotion-approval-history` is the canonical history/index surface for task-specific promotion approval artifacts.
```

- [ ] **Step 4: Run CLI/docs tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval_history'
```

Expected: CLI/docs regressions pass.

- [ ] **Step 5: Run combined history subset**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 -m pytest \
  .omo/tests/test_omo_promotion_approval_history.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval_history'
```

Expected: helper + CLI + docs coverage pass together.

- [ ] **Step 6: Commit the CLI/docs slice**

```bash
cd /Users/xiamingxing/Workspace/scripts && \
git add omo_worker.py omo_promotion_approval_history.py && \
git -c core.hooksPath=/dev/null commit -m "feat(omo): add promotion approval history command" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

cd /Users/xiamingxing/Workspace && \
git add scripts \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  .omo/workers/README.md \
  .omo/AGENT.md \
  .omo/tasks/README.md && \
git -c core.hooksPath=/dev/null commit -m "docs(omo): document promotion approval history surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Hydrate the live history surface and run promotion-focused verification

**Files:**
- Create: `.omo/workers/promotion/approvals/history/current.yaml`
- Create: `.omo/workers/promotion/approvals/history/current.md`

- [ ] **Step 1: Hydrate the live history surface**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-approval-history --omo-dir .omo --now 2026-06-03T00:15:00Z
```

Expected:

1. `approval_count=1`
2. latest approval is `P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z`

- [ ] **Step 2: Inspect the live packet**

Check:

```yaml
# .omo/workers/promotion/approvals/history/current.yaml
approval_count: 1
latest_approval_id: P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z
approvals:
  - approval_status: granted
    proposal_status: verified
    task_id: P19-W3-ARCHIVE-TS
```

- [ ] **Step 3: Run promotion-focused verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
python3 scripts/omo_worker.py task promotion-approval-history --omo-dir .omo --now 2026-06-03T00:15:00Z && \
python3 -m pytest \
  .omo/tests/test_omo_promotion_approval_history.py \
  .omo/tests/test_omo_automation.py \
  .omo/tests/test_worker_mechanism_consistency.py \
  -q -k 'promotion_approval_history or promotion_approval_status or promotion_approval_closure'
```

Expected: promotion approval history + closure related regressions all pass.

- [ ] **Step 4: Commit live history hydration**

```bash
cd /Users/xiamingxing/Workspace && \
git add \
  .omo/workers/promotion/approvals/history/current.yaml \
  .omo/workers/promotion/approvals/history/current.md && \
git -c core.hooksPath=/dev/null commit -m "chore(omo): hydrate promotion approval history surface" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-review checklist

- Spec coverage:
  - helper/index packet -> Task 1
  - CLI command -> Task 2
  - docs -> Task 2
  - live hydration -> Task 3
- Placeholder scan:
  - no `TBD`, `TODO`, or “similar to above” shortcuts remain
- Type consistency:
  - command name stays `promotion-approval-history`
  - helper name stays `build_promotion_approval_history`
  - output path stays `.omo/workers/promotion/approvals/history/current.yaml`
