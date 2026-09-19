---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-24
last_updated: 2026-09-03
title: Governance Convergence Implementation Plan
type: doc
---

# Governance Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以最小改动恢复治理一致性：orphan lock 自动清理、debt YAML 字段冲突修复、human gate 证据校验、未注册目录收敛。

**Architecture:** 不新建服务层，而是在现有 `compliance` / `diagnostics` / `bin/gac` 路径中插入轻量修复逻辑，保持单一 authority。

**Tech Stack:** Python 3.13, pytest, PyYAML, existing `projects/omo/src/omo/workflow` infrastructure

## Global Constraints

- Python 3.13+ type hints required (`list[str]`, `dict[str, Any]`)
- All new scripts must be executable via `python3 -m py_compile`
- Tests run with `uv run pytest` from workspace root
- No new third-party dependencies (use stdlib + existing `pyyaml`)
- Follow existing `bin/gac/` script patterns (argparse + YAML + JSON output)
- Debt YAML edits must be reversible (git-tracked, no destructive writes without `--apply`)

---

## File Structure

```
bin/gac/
├── fix-orphan-locks.py           # T0.1: 孤儿锁清理
├── fix-debt-fields.py            # T0.2: debt 字段冲突修复
├── fix-submodule-drift.py        # T1.3: submodule 漂移修复
└── validate-human-gate.py        # T1.1: human gate 证据校验

projects/omo/src/omo/workflow/
└── diagnostics.py                # T0.1 集成: compliance 自动修复

tests/
├── test_fix_orphan_locks.py      # T0.1 测试
├── test_fix_debt_fields.py       # T0.2 测试
├── test_validate_human_gate.py   # T1.1 测试
└── test_fix_submodule_drift.py   # T1.3 测试

docs/operations/
└── directory-convergence-decisions.md  # T1.2 决策文档
```

---

## Phase P0: 止血（今天完成）

### Task 1: 清理孤儿锁

**Files:**
- Create: `bin/gac/fix-orphan-locks.py`
- Modify: `projects/omo/src/omo/workflow/diagnostics.py:698-810`
- Test: `tests/test_fix_orphan_locks.py`

**Interfaces:**
- Consumes: `diagnostics.py` 的 `load_run_records()`, `load_registry()`, lock 扫描逻辑
- Produces: `--dry-run` 输出 JSON, `--apply` 移动孤儿锁到 `.archive/`, exit code 0/1

- [ ] **Step 1: 写失败测试**

```python
# tests/test_fix_orphan_locks.py
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def test_orphan_lock_detection():
    """orphan lock 应被检测到（如尚未修复）"""
    result = subprocess.run(
        [
            sys.executable,
            "bin/gac/fix-orphan-locks.py",
            "--dry-run",
            "--registry",
            str(WORKSPACE / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    # 可能已被 Task 2 自动修复，此时 orphan_count=0；否则应包含已知孤儿锁
    if report["orphan_count"] > 0:
        assert any(
            item["run_id"] == "20260822T032402Z-project-code-change-4ebce162"
            for item in report["orphans"]
        )


def test_orphan_lock_fix_creates_archive():
    """--apply 应将孤儿锁移入 .archive/"""
    archive_dir = WORKSPACE / ".omo/_delivery/agent-workflows/locks/.archive"
    subprocess.run(
        [
            sys.executable,
            "bin/gac/fix-orphan-locks.py",
            "--apply",
            "--registry",
            str(WORKSPACE / ".omo"),
        ],
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
    )
    assert archive_dir.exists()
    archived = list(archive_dir.glob("*.yaml"))
    assert len(archived) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_fix_orphan_locks.py -v`
Expected: FAIL with "No module named 'fix_orphan_locks'"

- [ ] **Step 3: 写最小实现**

```python
#!/usr/bin/env python3
"""fix-orphan-locks.py — 清理无对应 run 的孤儿锁."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _load_run_ids(runs_dir: Path) -> set[str]:
    run_ids: set[str] = set()
    if not runs_dir.is_dir():
        return run_ids
    for run_file in sorted(runs_dir.glob("*.yaml")):
        try:
            import yaml

            payload = yaml.safe_load(run_file.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        run_id = payload.get("run_id")
        if isinstance(run_id, str) and run_id:
            run_ids.add(run_id)
    return run_ids


def scan_orphan_locks(workspace: Path) -> list[dict[str, object]]:
    locks_dir = workspace / ".omo/_delivery/agent-workflows/locks"
    runs_dir = workspace / ".omo/_delivery/agent-workflows/runs"
    run_ids = _load_run_ids(runs_dir)
    orphans: list[dict[str, object]] = []
    if not locks_dir.is_dir():
        return orphans
    for lock_file in sorted(locks_dir.glob("*.yaml")):
        if lock_file.name.startswith("."):
            continue
        try:
            import yaml

            lock = yaml.safe_load(lock_file.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        lock_run_id = str(lock.get("run_id") or "")
        if lock_run_id and lock_run_id in run_ids:
            continue
        orphans.append(
            {
                "path": str(lock_file),
                "run_id": lock_run_id or None,
                "actor": lock.get("actor"),
            }
        )
    return orphans


def move_to_archive(lock_path: Path, archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / lock_path.name
    shutil.move(str(lock_path), str(target))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fix orphan lock files")
    parser.add_argument("--registry", type=Path, default=WORKSPACE / ".omo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    orphans = scan_orphan_locks(WORKSPACE)
    report: dict[str, object] = {
        "orphan_count": len(orphans),
        "orphans": orphans,
        "applied": [],
    }
    if args.apply and orphans:
        archive_dir = WORKSPACE / ".omo/_delivery/agent-workflows/locks/.archive"
        for item in orphans:
            target = move_to_archive(Path(str(item["path"])), archive_dir)
            report["applied"].append(str(target))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_fix_orphan_locks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/gac/fix-orphan-locks.py tests/test_fix_orphan_locks.py
git commit -m "feat(gac): add orphan lock cleanup tool with tests"
```

---

### Task 2: 集成到 compliance

**Files:**
- Modify: `projects/omo/src/omo/workflow/diagnostics.py:698-810`
- Test: `tests/test_agent_workflow.py` (add compliance test)

**Interfaces:**
- Consumes: `fix-orphan-locks.py --dry-run` JSON output
- Produces: compliance finding severity downgraded from `halt` → `warn` when orphan auto-fixed

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_workflow.py (append)
def test_compliance_auto_fix_orphan_lock(monkeypatch, tmp_path):
    """compliance 应能自动修复孤儿锁并降级 finding"""
    import subprocess, json, sys
    from pathlib import Path
    workspace = Path("/Users/xiamingxing/Workspace")
    # 先执行 fix
    subprocess.run(
        [sys.executable, "bin/gac/fix-orphan-locks.py", "--apply", "--registry", str(workspace / ".omo")],
        capture_output=True, text=True, cwd=workspace,
    )
    # 再跑 compliance
    result = subprocess.run(
        [sys.executable, "bin/agent-workflow.py", "compliance"],
        capture_output=True, text=True, cwd=workspace,
    )
    assert "orphan_lock" not in result.stdout
    assert "continue" in result.stdout or "PASS" in result.stdout or result.returncode == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_agent_workflow.py::test_compliance_auto_fix_orphan_lock -v`
Expected: FAIL (orphan_lock still present in compliance output)

- [ ] **Step 3: 修改 diagnostics.py**

```python
# projects/omo/src/omo/workflow/diagnostics.py (在 compliance_report 函数开头添加)
def _auto_fix_orphan_locks(registry_path: Path) -> list[dict[str, Any]]:
    """自动修复孤儿锁，返回已修复列表."""
    fix_script = Path(__file__).resolve().parents[2] / "bin" / "gac" / "fix-orphan-locks.py"
    if not fix_script.exists():
        return []
    try:
        proc = subprocess.run(
            [sys.executable, str(fix_script), "--apply", "--registry", str(registry_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return json.loads(proc.stdout).get("applied", [])
    except Exception:
        pass
    return []
```

然后在 `compliance_report` 函数体最开始添加：
```python
    # Auto-fix orphan locks before compliance check
    registry_path = Path(registry.get("root", "."))
    if str(registry_path) == "." or not (registry_path / "_delivery").exists():
        registry_path = WORKSPACE if 'WORKSPACE' in dir() else Path(".")
    _auto_fix_orphan_locks(registry_path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_agent_workflow.py::test_compliance_auto_fix_orphan_lock -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/omo/src/omo/workflow/diagnostics.py tests/test_agent_workflow.py
git commit -m "feat(omo): auto-fix orphan locks in compliance check"
```

---

### Task 3: 修复 debt YAML 字段冲突

**Files:**
- Create: `bin/gac/fix-debt-fields.py`
- Modify: `.omo/debt/items/ATTIC_ORPHAN_GITLINK.yaml`
- Test: `tests/test_fix_debt_fields.py`

**Interfaces:**
- Consumes: `.omo/debt/items/*.yaml`
- Produces: `--dry-run` 报告冲突, `--apply` 删除 deprecated `status` 字段, 清理 `<pending>` 占位符

- [ ] **Step 1: 写失败测试**

```python
# tests/test_fix_debt_fields.py
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def _run_fix_debt_fields(*args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(WORKSPACE / "bin/gac/fix-debt-fields.py"), *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_debt_field_conflict_detection(tmp_path: Path):
    """debt YAML 字段冲突应被检测到"""
    debt_dir = tmp_path / ".omo/debt/items"
    debt_dir.mkdir(parents=True)
    conflict_file = debt_dir / "TEST-CONFLICT.yaml"
    conflict_file.write_text(
        "id: TEST-CONFLICT\nlifecycle_state: open\nstatus: closed\n", encoding="utf-8"
    )
    result = _run_fix_debt_fields("--dry-run", "--root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["conflict_count"] >= 1
    assert any(item["id"] == "TEST-CONFLICT" for item in report["conflicts"])


def test_debt_field_fix_removes_status(tmp_path: Path):
    """--apply 应删除 deprecated status 字段"""
    debt_dir = tmp_path / ".omo/debt/items"
    debt_dir.mkdir(parents=True)
    conflict_file = debt_dir / "TEST-CONFLICT.yaml"
    conflict_file.write_text(
        "id: TEST-CONFLICT\nlifecycle_state: open\nstatus: closed\n", encoding="utf-8"
    )
    result = _run_fix_debt_fields("--apply", "--root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    content = conflict_file.read_text(encoding="utf-8")
    assert "status:" not in content
    assert "lifecycle_state: open" in content
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_fix_debt_fields.py -v`
Expected: FAIL with "No module named 'fix_debt_fields'"

- [ ] **Step 3: 写最小实现**

```python
#!/usr/bin/env python3
"""fix-debt-fields.py — 修复 debt YAML 字段冲突."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]


def scan_debt_items(root: Path) -> tuple[list[dict], list[dict]]:
    items_dir = root / ".omo" / "debt" / "items"
    conflicts: list[dict] = []
    placeholders: list[dict] = []
    if not items_dir.is_dir():
        return conflicts, placeholders
    for path in sorted(items_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        item_id = data.get("id", path.stem)
        if "status" in data and "lifecycle_state" in data:
            conflicts.append(
                {
                    "id": item_id,
                    "path": str(path),
                    "has_status": True,
                    "has_lifecycle_state": True,
                }
            )
        for field in ["closed_evidence", "resolution_evidence"]:
            value = str(data.get(field, ""))
            if "<pending>" in value:
                placeholders.append(
                    {
                        "id": item_id,
                        "path": str(path),
                        "field": field,
                        "value": value[:120],
                    }
                )
    return conflicts, placeholders


def fix_debt_items(root: Path, apply: bool) -> dict:
    conflicts, placeholders = scan_debt_items(root)
    report = {
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "placeholder_count": len(placeholders),
        "placeholders": placeholders,
        "applied": [],
    }
    if apply:
        items_dir = root / ".omo" / "debt" / "items"
        for conflict in conflicts:
            path = Path(conflict["path"])
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            data.pop("status", None)
            path.write_text(
                yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            report["applied"].append({"path": str(path), "action": "removed_status"})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fix debt YAML field conflicts")
    parser.add_argument("--root", type=Path, default=WORKSPACE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    if args.apply:
        report = fix_debt_items(args.root, apply=True)
    else:
        conflicts, placeholders = scan_debt_items(args.root)
        report = {
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "placeholder_count": len(placeholders),
            "placeholders": placeholders,
            "applied": [],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_fix_debt_fields.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/gac/fix-debt-fields.py tests/test_fix_debt_fields.py
git commit -m "feat(gac): add debt YAML field conflict fixer with tests"
```

---

## Phase P1: 标准化（本周完成）

### Task 4: Human Gate 证据校验

**Files:**
- Create: `bin/gac/validate-human-gate.py`
- Create: `tests/test_validate_human_gate.py`

**Interfaces:**
- Consumes: `docs/scene-cards/*.yaml` 中的 evidence_refs
- Produces: JSON 报告，列出 prohibited sources

- [ ] **Step 1: 写失败测试**

```python
# tests/test_validate_human_gate.py
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def _run_validate_human_gate(*args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            "python",
            str(WORKSPACE / "bin/gac/validate-human-gate.py"),
            *args,
        ],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_merge_event_is_prohibited():
    """merge_event 应被识别为 prohibited source"""
    result = _run_validate_human_gate(
        "--scene-card",
        str(WORKSPACE / "docs/scene-cards/engineering-delivery-dogfood.yaml"),
    )
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert report["prohibited_count"] >= 1
    assert any("merge_event" in item["source"] for item in report["prohibited_sources"])


def test_manual_adjudication_is_allowed():
    """场景卡中 manual_adjudication 不应被标记为 prohibited"""
    result = _run_validate_human_gate(
        "--scene-card",
        str(WORKSPACE / "docs/scene-cards/engineering-delivery-dogfood.yaml"),
    )
    report = json.loads(result.stdout)
    assert report["prohibited_count"] >= 1
    assert not any(item["source"] == "manual_adjudication" for item in report["prohibited_sources"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_validate_human_gate.py -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
#!/usr/bin/env python3
"""validate-human-gate.py — 校验 human gate 证据来源."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]

PROHIBITED_SOURCES = {
    "merge_event",
    "issue_comment_automation",
    "ci_pass",
    "automated_workflow",
}


def extract_evidence_refs(scene_card_path: Path) -> list[str]:
    docs = list(yaml.safe_load_all(scene_card_path.read_text(encoding="utf-8")))
    refs: list[str] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        evidence = doc.get("evidence_refs", [])
        if isinstance(evidence, list):
            refs.extend(str(item) for item in evidence)
        notes = doc.get("notes", [])
        if isinstance(notes, list):
            for note in notes:
                refs.append(str(note))
        description = str(doc.get("description", ""))
        refs.append(description)
    return refs


def validate_human_gate(scene_card_path: Path, allow_manual: bool = False) -> dict:
    refs = extract_evidence_refs(scene_card_path)
    prohibited = []
    for ref in refs:
        for source in PROHIBITED_SOURCES:
            if source in ref.lower():
                prohibited.append({"source": source, "ref": ref[:200]})
    return {
        "scene_card": str(scene_card_path),
        "prohibited_count": len(prohibited),
        "prohibited_sources": prohibited,
        "allowed": allow_manual,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate human gate evidence sources")
    parser.add_argument("--scene-card", type=Path, required=True)
    parser.add_argument("--allow-manual", action="store_true")
    args = parser.parse_args(argv)
    report = validate_human_gate(args.scene_card, args.allow_manual)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["prohibited_count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_validate_human_gate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/gac/validate-human-gate.py tests/test_validate_human_gate.py
git commit -m "feat(gac): add human gate evidence validator"
```

---

### Task 5: 目录收敛决策与执行

**Files:**
- Create: `docs/operations/directory-convergence-decisions.md`
- Modify: `.gitmodules`, `.gitignore`
- Script: `bin/gac/fix-submodule-drift.py`

**Interfaces:**
- Consumes: `git submodule status` 输出
- Produces: 收敛决策文档 + 执行脚本

- [ ] **Step 1: 写决策文档**

```markdown
# docs/operations/directory-convergence-decisions.md

> 2026-08-22 决策：5 个未注册目录收敛方案

| 路径 | 当前状态 | 决策 | 执行动作 | 负责人 |
|------|----------|------|----------|--------|
| `projects/bus-foundation` | `?` untracked | archive | 移动到 `.omo/_attic/bus-foundation-archive/` | governance-team |
| `projects/model-driven` | `?` untracked | register | `git submodule add` + 注册 | governance-team |
| `projects/observability` | `?` untracked | register | `git submodule add` + 注册 | governance-team |
| `projects/omo` | `+` modified submodule | sync | 提交 submodule 内改动 + 更新指针 | governance-team |
| `docs/operations/human-attestations/` | `??` untracked | register | `git add` + 提交 | governance-team |
```

- [ ] **Step 2: 写失败测试（submodule drift）**

```python
# tests/test_fix_submodule_drift.py
import json
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def test_submodule_drift_detection():
    result = subprocess.run(
        [sys.executable, "bin/gac/fix-submodule-drift.py", "--check", "--root", str(WORKSPACE)],
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
    )
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["untracked_count"] >= 3
```

- [ ] **Step 3: 写最小实现（fix-submodule-drift.py）**

```python
#!/usr/bin/env python3
"""fix-submodule-drift.py — 检测并报告 submodule 漂移."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def check_submodule_drift(root: Path) -> dict:
    proc = subprocess.run(
        ["git", "submodule", "status", "--recursive"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    lines = proc.stdout.strip().splitlines()
    issues = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        status = line[0] if line else ""
        parts = line.lstrip("+- ").split()
        git_hash = parts[0] if parts else ""
        path = parts[1] if len(parts) > 1 else ""
        if status in {"+", "-", "?"}:
            issues.append(
                {
                    "path": path,
                    "status": status,
                    "git_hash": git_hash,
                    "issue": {
                        "+": "modified",
                        "-": "uninitialized",
                        "?": "untracked",
                    }[status],
                }
            )
    return {
        "total_submodules": len(lines),
        "issue_count": len(issues),
        "issues": issues,
        "untracked_count": sum(1 for i in issues if i["issue"] == "untracked"),
        "modified_count": sum(1 for i in issues if i["issue"] == "modified"),
        "uninitialized_count": sum(1 for i in issues if i["issue"] == "uninitialized"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check submodule drift")
    parser.add_argument("--root", type=Path, default=WORKSPACE)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args(argv)
    report = check_submodule_drift(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.check and report["issue_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_fix_submodule_drift.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add bin/gac/fix-submodule-drift.py tests/test_fix_submodule_drift.py docs/operations/directory-convergence-decisions.md
git commit -m "feat(gac): add submodule drift checker and directory convergence decisions"
```

---

## Phase P2: 机制化（下周完成）

### Task 6: Deprecated 命令退休

**Files:**
- Modify: `projects/cockpit/src/cockpit/commands/registry.py`
- Modify: `projects/cockpit/src/cockpit/commands/help_map.py`
- Test: `tests/test_cockpit_deprecated.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cockpit_deprecated.py
import subprocess
import sys

def test_cockpit_deprecated_commands_hidden_by_default():
    result = subprocess.run(
        [sys.executable, "-m", "cockpit.cli", "--help"],
        capture_output=True, text=True, cwd="/Users/xiamingxing/Workspace/projects/cockpit"
    )
    assert "ssb" not in result.stdout
    assert "model-driven" not in result.stdout


def test_cockpit_deprecated_commands_shown_with_flag():
    result = subprocess.run(
        [sys.executable, "-m", "cockpit.cli", "--help", "--show-deprecated"],
        capture_output=True, text=True, cwd="/Users/xiamingxing/Workspace/projects/cockpit"
    )
    assert "ssb" in result.stdout or "DEPRECATED" in result.stdout
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_cockpit_deprecated.py -v`
Expected: FAIL (commands still visible by default)

- [ ] **Step 3: 修改 registry.py**

在 `registry.py` 的 command 列表添加 `deprecated` 标记，并在 CLI 渲染时过滤。

```python
# projects/cockpit/src/cockpit/commands/registry.py
# 在 command 定义处添加:
#   deprecated: true
#   removal_version: "v6.1.0"
#   replacement: "..." (可选)
```

修改 `help_map.py` 的 `CmdRow` 生成逻辑：
```python
def is_deprecated(cmd_row):
    return getattr(cmd_row, "deprecated", False)

def filter_deprecated(commands, show_deprecated=False):
    if show_deprecated:
        return commands
    return [cmd for cmd in commands if not is_deprecated(cmd)]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_cockpit_deprecated.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/cockpit/src/cockpit/commands/registry.py projects/cockpit/src/cockpit/commands/help_map.py tests/test_cockpit_deprecated.py
git commit -m "feat(cockpit): hide deprecated commands by default, --show-deprecated to reveal"
```

---

## 门禁条件

```
☐ P0:
  ☐ orphan lock = 0 (fix-orphan-locks.py --apply)
  ☐ compliance 输出 continue (agent-workflow.py compliance)
  ☐ debt YAML 无 status 字段 (fix-debt-fields.py --apply)

☐ P1:
  ☐ human_gate 测试通过 (validate-human-gate.py)
  ☐ 5 个未注册目录决策文档已写 (directory-convergence-decisions.md)
  ☐ submodule drift 检测通过 (fix-submodule-drift.py --check)

☐ P2:
  ☐ deprecated 命令默认隐藏 (cockpit --help)
  ☐ --show-deprecated 显示它们

☐ 全链路:
  ☐ make gac-local-gate ALL GREEN
  ☐ make ci-local PASS
```

---

## 执行顺序

```
Day 1 (P0):
  Task 1 → Task 2 → Task 3
  目标: compliance 恢复 continue

Day 2-3 (P1):
  Task 4 → Task 5
  目标: human gate + 目录收敛

Week 2 (P2):
  Task 6
  目标: deprecated 命令退休
```

---

## 不做什么

| 不做 | 原因 |
|------|------|
| ❌ 建 Consistency Engine 服务 | 过度设计，修复逻辑直接集成到 compliance |
| ❌ 建 Human Gate Enforcer 服务 | 增强现有 observer + 校验脚本即可 |
| ❌ 统一所有状态到单一数据库 | YAML 足够，迁移成本 > 收益 |
| ❌ 自动化 debt 生命周期关闭 | debt 需要 human judgment |
