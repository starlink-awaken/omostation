# Debt Approval Seam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal approval seam so gate-level dispatched `revalidate_now` actions require an explicit approval record bound to the latest immutable dispatch run before `omo_debt.py revalidate` can mutate the debt item.

**Architecture:** Keep approval as a narrow control-plane layer on top of the existing dispatch surface. Implement the decision logic in a small pure helper module first, then wire an `approve` CLI command that writes item-local approval artifacts, and finally enforce a pre-flight approval guard inside `revalidate` for gate-level dispatched items only.

**Tech Stack:** Python 3, PyYAML, existing `scripts/omo_debt*.py` helpers, pytest, Markdown, canonical `bash bin/verify-omo.sh`

---

## File Structure

### New files

- `scripts/omo_debt_approval.py` — pure approval helper functions for trigger rules, dispatch-entry lookup, approval record building, and approval path generation
- `.omo/tests/test_omo_debt_approval.py` — focused unit tests for the pure approval helper layer

### Modified files

- `scripts/omo_debt.py` — add `approve` CLI, approval artifact writer, and `revalidate` pre-flight guard
- `.omo/tests/test_omo_debt_cli.py` — cover `approve` CLI success/failure and gate-item revalidate guard behavior
- `.omo/tests/test_omo_debt_docs.py` — assert `.omo/AGENT.md` documents the approval seam
- `.omo/AGENT.md` — document when approval is required, how to run `approve`, and how stale approvals fail

### Approval artifact surfaces created by the implementation

- `.omo/debt/approvals/<ITEM_ID>/current.yaml` — latest approval pointer for one item
- `.omo/debt/approvals/<ITEM_ID>/records/<timestamp>.yaml` — immutable approval record history for one item

### Important boundary note

Approval artifacts are operator-written control-plane state, not generated baseline outputs like dispatch packets. Do **not** publish deterministic repo-local approval files as part of this plan. Approval files should be created only inside tmp test workspaces during regression coverage.

### Repository-boundary note

The workspace root treats `scripts/` as a nested git repository/gitlink. When a task touches both root-tracked files and `scripts/*`, make two commits:

1. a commit inside `/Users/xiamingxing/Workspace/scripts`
2. a root-repo commit inside `/Users/xiamingxing/Workspace` that records the updated `scripts` pointer plus root files

Do not try to commit `scripts/*` pathspecs directly from the root repo.

### Existing files to read before implementation

- `docs/superpowers/specs/2026-06-02-debt-approval-seam-design.md`
- `scripts/omo_debt.py`
- `scripts/omo_debt_dispatch.py`
- `.omo/debt/dispatch/current.yaml`
- `.omo/tests/test_omo_debt_cli.py`
- `.omo/tests/test_omo_debt_docs.py`
- `.omo/AGENT.md`

---

### Task 1: Add the pure approval helper layer

**Files:**
- Create: `/Users/xiamingxing/Workspace/scripts/omo_debt_approval.py`
- Create: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_approval.py`

- [ ] **Step 1: Write the failing approval-helper tests**

Create `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_approval.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.omo_debt_approval import (
    APPROVAL_SCOPE_EXECUTE_REVALIDATE,
    approval_current_path,
    approval_paths,
    build_approval_record,
    dispatch_entry_requires_approval,
    find_dispatch_entry,
)


def _dispatch_packet() -> dict[str, object]:
    return {
        "latest_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        "owners": [
            {
                "owner": "sharedbrain-governance",
                "entries": [
                    {
                        "id": "SB_DECOMPOSITION",
                        "primary_lane": "revalidate_now",
                        "gate_level": "gate",
                    },
                    {
                        "id": "SB_UNTESTED_PKGS",
                        "primary_lane": "revalidate_now",
                        "gate_level": "watchlist",
                    },
                ],
            },
            {
                "owner": "platform-governance",
                "entries": [
                    {
                        "id": "D2_CI_E2E",
                        "primary_lane": "revalidate_now",
                        "gate_level": "watchlist",
                    }
                ],
            },
        ],
    }


def test_dispatch_entry_requires_approval_only_for_gate_revalidate_items() -> None:
    packet = _dispatch_packet()

    assert dispatch_entry_requires_approval(find_dispatch_entry(packet, "SB_DECOMPOSITION")) is True
    assert dispatch_entry_requires_approval(find_dispatch_entry(packet, "SB_UNTESTED_PKGS")) is False
    assert dispatch_entry_requires_approval(find_dispatch_entry(packet, "D2_CI_E2E")) is False
    assert dispatch_entry_requires_approval(find_dispatch_entry(packet, "MISSING")) is False


def test_build_approval_record_and_paths_use_immutable_run_ref() -> None:
    current_only_path = approval_current_path(Path("/tmp/example/.omo"), item_id="SB_DECOMPOSITION")
    current_path, record_path = approval_paths(
        Path("/tmp/example/.omo"),
        item_id="SB_DECOMPOSITION",
        approved_at="2026-06-10T01:00:00Z",
    )

    record = build_approval_record(
        item_id="SB_DECOMPOSITION",
        approved_by="omo-governance",
        approved_at="2026-06-10T01:00:00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        approval_scope=APPROVAL_SCOPE_EXECUTE_REVALIDATE,
    )

    assert current_only_path == Path("/tmp/example/.omo/debt/approvals/SB_DECOMPOSITION/current.yaml")
    assert current_path == current_only_path
    assert record_path == Path("/tmp/example/.omo/debt/approvals/SB_DECOMPOSITION/records/2026-06-10T01-00-00Z.yaml")
    assert record == {
        "item_id": "SB_DECOMPOSITION",
        "approved_by": "omo-governance",
        "approved_at": "2026-06-10T01:00:00Z",
        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        "approval_scope": "execute_revalidate",
    }


def test_build_approval_record_rejects_invalid_scope() -> None:
    with pytest.raises(ValueError, match="invalid approval scope"):
        build_approval_record(
            item_id="SB_DECOMPOSITION",
            approved_by="omo-governance",
            approved_at="2026-06-10T01:00:00Z",
            dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
            approval_scope="watch_only",
        )
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_approval.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.omo_debt_approval'`.

- [ ] **Step 3: Write the minimal approval helper implementation**

Create `/Users/xiamingxing/Workspace/scripts/omo_debt_approval.py`:

```python
from __future__ import annotations

from pathlib import Path


APPROVAL_SCOPE_EXECUTE_REVALIDATE = "execute_revalidate"
VALID_APPROVAL_SCOPES = {
    APPROVAL_SCOPE_EXECUTE_REVALIDATE,
    "promote_lifecycle",
    "escalate",
}


def find_dispatch_entry(dispatch_packet: dict[str, object], item_id: str) -> dict[str, object] | None:
    for owner_packet in dispatch_packet.get("owners", []):
        for entry in owner_packet.get("entries", []):
            if entry.get("id") == item_id:
                return dict(entry)
    return None


def dispatch_entry_requires_approval(entry: dict[str, object] | None) -> bool:
    if entry is None:
        return False
    return entry.get("primary_lane") == "revalidate_now" and entry.get("gate_level") == "gate"


def approval_current_path(omo_dir: Path, item_id: str) -> Path:
    return omo_dir / "debt" / "approvals" / item_id / "current.yaml"


def approval_paths(omo_dir: Path, item_id: str, approved_at: str) -> tuple[Path, Path]:
    slug = approved_at.replace(":", "-")
    item_dir = approval_current_path(omo_dir, item_id).parent
    return item_dir / "current.yaml", item_dir / "records" / f"{slug}.yaml"


def build_approval_record(
    *,
    item_id: str,
    approved_by: str,
    approved_at: str,
    dispatch_run_ref: str,
    approval_scope: str,
) -> dict[str, str]:
    if approval_scope not in VALID_APPROVAL_SCOPES:
        raise ValueError(f"invalid approval scope: {approval_scope}")
    return {
        "item_id": item_id,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "dispatch_run_ref": dispatch_run_ref,
        "approval_scope": approval_scope,
    }
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_approval.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt_approval.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add debt approval helpers\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_approval.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt approval helpers\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 2: Add the `approve` CLI and write approval artifacts

**Files:**
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Add failing CLI tests for `approve`**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_approve_requires_dispatch_packet(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")
    shutil.rmtree(tmp_path / ".omo" / "debt" / "dispatch", ignore_errors=True)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-10T01:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert "dispatch/current.yaml" in result.stderr


def test_debt_approve_writes_current_and_record_files_for_gate_item(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-10T01:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    current_path = tmp_path / ".omo" / "debt" / "approvals" / "SB_DECOMPOSITION" / "current.yaml"
    record_path = tmp_path / ".omo" / "debt" / "approvals" / "SB_DECOMPOSITION" / "records" / "2026-06-10T01-00-00Z.yaml"

    assert result.returncode == 0, result.stderr
    current = yaml.safe_load(current_path.read_text(encoding="utf-8"))
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    assert current == record
    assert current["dispatch_run_ref"] == ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    assert current["approval_scope"] == "execute_revalidate"


def test_debt_approve_rejects_non_gate_item_and_duplicate_record(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    non_gate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "D2_CI_E2E",
            "--approved-by",
            "platform-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-10T01:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    first = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-10T01:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    duplicate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-10T01:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert non_gate.returncode != 0
    assert "does not require approval" in non_gate.stderr
    assert first.returncode == 0, first.stderr
    assert duplicate.returncode != 0
    assert "2026-06-10T01-00-00Z.yaml" in duplicate.stderr
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py::test_debt_approve_requires_dispatch_packet .omo/tests/test_omo_debt_cli.py::test_debt_approve_writes_current_and_record_files_for_gate_item .omo/tests/test_omo_debt_cli.py::test_debt_approve_rejects_non_gate_item_and_duplicate_record -q
```

Expected: FAIL with `invalid choice: 'approve'`.

- [ ] **Step 3: Write the minimal `approve` implementation**

Update `/Users/xiamingxing/Workspace/scripts/omo_debt.py`:

```python
try:
    from scripts.omo_debt_approval import (
        APPROVAL_SCOPE_EXECUTE_REVALIDATE,
        approval_current_path,
        approval_paths,
        build_approval_record,
        dispatch_entry_requires_approval,
        find_dispatch_entry,
    )
except ModuleNotFoundError:
    from omo_debt_approval import (
        APPROVAL_SCOPE_EXECUTE_REVALIDATE,
        approval_current_path,
        approval_paths,
        build_approval_record,
        dispatch_entry_requires_approval,
        find_dispatch_entry,
    )


def approve_item(
    omo_dir: Path,
    *,
    item_id: str,
    approved_by: str,
    approval_scope: str,
    approved_at: str,
) -> None:
    dispatch_path = omo_dir / "debt" / "dispatch" / "current.yaml"
    if not dispatch_path.exists():
        raise FileNotFoundError(f"missing dispatch packet: {dispatch_path}")

    dispatch_packet = _load_yaml(dispatch_path)
    entry = find_dispatch_entry(dispatch_packet, item_id)
    if not dispatch_entry_requires_approval(entry):
        raise ValueError(f"item does not require approval: {item_id}")

    current_path, record_path = approval_paths(omo_dir, item_id=item_id, approved_at=approved_at)
    if record_path.exists():
        raise FileExistsError(f"approval record already exists: {record_path}")

    record = build_approval_record(
        item_id=item_id,
        approved_by=approved_by,
        approved_at=approved_at,
        dispatch_run_ref=dispatch_packet["latest_run_ref"],
        approval_scope=approval_scope,
    )
    _write_yaml(current_path, record)
    _write_yaml(record_path, record)


approve_parser = subparsers.add_parser("approve")
approve_parser.add_argument("--omo-dir", default=".omo")
approve_parser.add_argument("--id", required=True)
approve_parser.add_argument("--approved-by", required=True)
approve_parser.add_argument("--scope", required=True)
approve_parser.add_argument("--approved-at", required=True)


if args.command == "approve":
    approve_item(
        omo_dir,
        item_id=args.id,
        approved_by=args.approved_by,
        approval_scope=args.scope,
        approved_at=args.approved_at,
    )
    print(f"approved {args.id}")
    return 0
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py::test_debt_approve_requires_dispatch_packet .omo/tests/test_omo_debt_cli.py::test_debt_approve_writes_current_and_record_files_for_gate_item .omo/tests/test_omo_debt_cli.py::test_debt_approve_rejects_non_gate_item_and_duplicate_record -q
```

Expected: PASS.

- [ ] **Step 5: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): add debt approval command\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_cli.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover debt approval command\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 3: Enforce the gate-item `revalidate` pre-flight guard

**Files:**
- Modify: `/Users/xiamingxing/Workspace/scripts/omo_debt.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`

- [ ] **Step 1: Add failing revalidate-guard tests**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_cli.py`:

```python
def test_debt_revalidate_gate_item_requires_matching_approval(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--reviewed-at",
            "2026-06-10T02:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode != 0
    assert ".omo/debt/approvals/SB_DECOMPOSITION/current.yaml" in result.stderr


def test_debt_revalidate_gate_item_succeeds_after_matching_approval(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    approve = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-10T01:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    revalidate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--reviewed-at",
            "2026-06-10T02:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    payload = yaml.safe_load((tmp_path / ".omo" / "debt" / "items" / "SB_DECOMPOSITION.yaml").read_text(encoding="utf-8"))
    assert approve.returncode == 0, approve.stderr
    assert revalidate.returncode == 0, revalidate.stderr
    assert payload["last_reviewed_at"] == "2026-06-10T02:00:00Z"
    assert payload["history"][-1]["action"] == "revalidate"


def test_debt_revalidate_rejects_stale_approval_after_new_dispatch(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / ".omo" / "debt"
    shutil.copytree(source, tmp_path / ".omo" / "debt")

    approve = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "approve",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--approved-by",
            "omo-governance",
            "--scope",
            "execute_revalidate",
            "--approved-at",
            "2026-06-10T01:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    dispatch = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "dispatch",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--now",
            "2026-06-11T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    revalidate = subprocess.run(
        [
            sys.executable,
            "scripts/omo_debt.py",
            "revalidate",
            "--omo-dir",
            str(tmp_path / ".omo"),
            "--id",
            "SB_DECOMPOSITION",
            "--reviewed-at",
            "2026-06-11T01:00:00Z",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert approve.returncode == 0, approve.stderr
    assert dispatch.returncode == 0, dispatch.stderr
    assert revalidate.returncode != 0
    assert "approval does not match latest dispatch run" in revalidate.stderr
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py::test_debt_revalidate_gate_item_requires_matching_approval .omo/tests/test_omo_debt_cli.py::test_debt_revalidate_gate_item_succeeds_after_matching_approval .omo/tests/test_omo_debt_cli.py::test_debt_revalidate_rejects_stale_approval_after_new_dispatch -q
```

Expected: FAIL because `revalidate` still updates the item without checking approval state.

- [ ] **Step 3: Write the minimal `revalidate` approval guard**

Update `/Users/xiamingxing/Workspace/scripts/omo_debt.py`:

```python
def require_revalidate_approval(omo_dir: Path, item_id: str) -> None:
    dispatch_path = omo_dir / "debt" / "dispatch" / "current.yaml"
    if not dispatch_path.exists():
        return

    dispatch_packet = _load_yaml(dispatch_path)
    entry = find_dispatch_entry(dispatch_packet, item_id)
    if not dispatch_entry_requires_approval(entry):
        return

    approval_path = approval_current_path(omo_dir, item_id=item_id)
    if not approval_path.exists():
        raise FileNotFoundError(f"missing approval record: {approval_path}")

    approval = _load_yaml(approval_path)
    if approval.get("approval_scope") != APPROVAL_SCOPE_EXECUTE_REVALIDATE:
        raise ValueError(f"invalid approval scope for revalidate: {approval_path}")
    if approval.get("dispatch_run_ref") != dispatch_packet.get("latest_run_ref"):
        raise ValueError(f"approval does not match latest dispatch run: {approval_path}")


if args.command == "revalidate":
    require_revalidate_approval(omo_dir, args.id)
    item_path, payload = update_item(omo_dir, args.id)
    payload["last_reviewed_at"] = args.reviewed_at
    append_history(payload, "revalidate", f"Reviewed at {args.reviewed_at}.")
    _write_yaml(item_path, payload)
    print(f"revalidated {args.id}")
    return 0
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_cli.py::test_debt_revalidate_gate_item_requires_matching_approval .omo/tests/test_omo_debt_cli.py::test_debt_revalidate_gate_item_succeeds_after_matching_approval .omo/tests/test_omo_debt_cli.py::test_debt_revalidate_rejects_stale_approval_after_new_dispatch -q
```

Expected: PASS.

- [ ] **Step 5: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): guard gate debt revalidation with approval\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_omo_debt_cli.py scripts && git -c core.hooksPath=/dev/null commit -m $'test(omo): cover approval-gated revalidation\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

### Task 4: Document the approval seam and run canonical verification

**Files:**
- Modify: `/Users/xiamingxing/Workspace/.omo/AGENT.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_docs.py`

- [ ] **Step 1: Add the failing docs regression**

Update `/Users/xiamingxing/Workspace/.omo/tests/test_omo_debt_docs.py`:

```python
def test_omo_agent_documents_debt_refresh_flow() -> None:
    content = Path(".omo/AGENT.md").read_text(encoding="utf-8")

    assert "python3 scripts/omo_debt.py dispatch --omo-dir .omo --now" in content
    assert "python3 scripts/omo_debt.py approve --omo-dir .omo" in content
    assert ".omo/debt/approvals/<ITEM_ID>/current.yaml" in content
    assert "gate-level" in content.lower()
    assert "execute_revalidate" in content
    assert "dispatch run" in content.lower()
    assert "approval does not match latest dispatch run" in content.lower()
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_docs.py::test_omo_agent_documents_debt_refresh_flow -q
```

Expected: FAIL because `.omo/AGENT.md` does not mention `approve` yet.

- [ ] **Step 3: Update the operator guidance**

Update `/Users/xiamingxing/Workspace/.omo/AGENT.md` in the debt section:

```md
5. `python3 scripts/omo_debt.py approve --omo-dir .omo --id SB_DECOMPOSITION --approved-by omo-governance --scope execute_revalidate --approved-at 2026-06-10T01:00:00Z`

- approval is required only for gate-level dispatched `Revalidate Now` items
- approval records live under `.omo/debt/approvals/<ITEM_ID>/current.yaml` and `records/<timestamp>.yaml`
- `approve` binds the record to the latest immutable dispatch run, not `dispatch/current.yaml`
- `revalidate` fails closed when approval is missing or when approval does not match latest dispatch run
```

- [ ] **Step 4: Run the focused approval suite and canonical verify**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_omo_debt_approval.py .omo/tests/test_omo_debt_cli.py .omo/tests/test_omo_debt_docs.py -q && bash bin/verify-omo.sh
```

Expected: PASS for both the focused approval suite and the full `.omo` verification chain.

- [ ] **Step 5: Commit both repos**

Commit the `scripts` repo:

```bash
cd /Users/xiamingxing/Workspace/scripts && git add omo_debt.py && git -c core.hooksPath=/dev/null commit -m $'feat(omo): enforce debt approval seam\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

Commit the root repo:

```bash
cd /Users/xiamingxing/Workspace && git add .omo/AGENT.md .omo/tests/test_omo_debt_docs.py scripts && git -c core.hooksPath=/dev/null commit -m $'docs(omo): document debt approval seam\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

---

## Self-Review Checklist

Before executing, confirm the plan still covers every approval-spec requirement:

1. per-item approval helper and record schema are covered in Task 1
2. `approve` CLI and immutable item-local approval records are covered in Task 2
3. gate-only `revalidate` enforcement and stale-approval mismatch are covered in Task 3
4. `.omo/AGENT.md` operator guidance and canonical verification are covered in Task 4

Search this file for placeholder words such as `TODO`, `TBD`, `appropriate`, `similar`, or `later`; there should be none.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-02-debt-approval-seam.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
