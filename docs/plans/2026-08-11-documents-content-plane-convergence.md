---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# Documents Content Plane Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Documents 收敛成“内容 + 宪法 + 领域声明 + 已接受证据”，并把可执行 KEMS 能力、运行状态和派生存储统一归位 Workspace。

**Architecture:** 先扩展现有 l4-kernel，不创建新项目。l4-kernel 提供只读、确定性的内容面分类与 T8 审计；Cockpit 作为唯一人机入口调用该审计；legacy l4 执行入口默认 fail closed；Documents 中与 Workspace 完全重复的 KEMS 实现降级为薄桥。物理删除和批量搬迁留到消费者清零后的下一波。

**Tech Stack:** Python 3.13、pytest、uv、l4-kernel Harness、Cockpit CLI、GaC Agent Workflow。

## Global Constraints

- Documents 是 canonical content plane，不是 workflow/runtime/state SSOT。
- 正式 KEMS runtime 只允许位于 Kairon/KOS；执行只经 OMO + Workflow Mesh + Runtime。
- l4-kernel 只拥有契约、编译、路径策略和 Harness，不拥有索引、模型评估或 worker execution。
- 不创建第二 KEMS 项目、第二 CLI 平台或第二 workflow engine。
- 本轮不删除 Documents 文件，不批量移动目录；只做可回滚的审计、fail-closed 和薄桥收敛。
- 路径必须通过环境变量覆盖；不得新增 `/Users/xiamingxing/...` 硬编码。
- 每个生产行为改动必须遵循 RED → GREEN；测试先失败，再写最小实现。
- 未获得新的明确确认前，不执行 `git commit`、`git push`、PR 或 merge。

---

### Task 1: l4-kernel 内容面分类与 T8 审计

**Files:**
- Create: `projects/l4-kernel/src/l4_kernel/content_plane.py`
- Create: `projects/l4-kernel/tests/test_content_plane.py`
- Modify: `projects/l4-kernel/src/l4_kernel/harness.py`
- Modify: `projects/l4-kernel/src/l4_kernel/harness_profiles.py`
- Modify: `projects/l4-kernel/src/l4_kernel/cli.py`
- Modify: `projects/l4-kernel/tests/test_harness.py`
- Modify: `projects/l4-kernel/tests/test_cli_contracts.py`

**Interfaces:**
- Produces: `classify_artifact(root: Path, path: Path) -> ArtifactClassification`
- Produces: `audit_content_plane(root: Path) -> ContentPlaneReport`
- Produces: `l4-kernel content audit ROOT --json`
- Produces: opt-in Harness gate `T8`; Phase 0 default profiles暂不启用 T8，避免存量债务直接锁死所有域。

- [ ] **Step 1: Write failing unit tests for deterministic classification**

```python
def test_classifies_contract_content_runtime_projection_and_cache(tmp_path: Path) -> None:
    files = {
        "DOMAIN.yaml": "contract",
        "_knowledge/note.md": "content",
        "_control/executors/run.py": "runtime",
        "_control/STATE.md": "projection",
        "_runtime/cache.sqlite": "cache",
    }
    for relative, expected in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        assert classify_artifact(tmp_path, path).kind == expected
```

- [ ] **Step 2: Run tests and verify RED**

Run: `uv run --group dev pytest tests/test_content_plane.py -q`

Expected: collection fails because `l4_kernel.content_plane` does not exist.

- [ ] **Step 3: Implement the minimal classifier and report model**

```python
@dataclass(frozen=True, slots=True)
class ArtifactClassification:
    path: Path
    relative_path: str
    kind: str
    reason: str

@dataclass(frozen=True, slots=True)
class ContentPlaneReport:
    root: Path
    artifacts: tuple[ArtifactClassification, ...]

    @property
    def violations(self) -> tuple[ArtifactClassification, ...]:
        return tuple(item for item in self.artifacts if item.kind in {"runtime", "cache"})

    @property
    def ok(self) -> bool:
        return not self.violations
```

Classification precedence must be: cache → runtime → projection → contract → content. Scan with `Path.rglob("*")`, do not follow directory symlinks, and sort by POSIX relative path.

- [ ] **Step 4: Run classification tests and verify GREEN**

Run: `uv run --group dev pytest tests/test_content_plane.py -q`

Expected: PASS.

- [ ] **Step 5: Write failing tests for CLI and T8 integration**

```python
def test_content_audit_json_fails_closed_on_runtime_artifact(tmp_path, monkeypatch, capsys):
    script = tmp_path / "_runtime" / "run.py"
    script.parent.mkdir()
    script.write_text("print('x')", encoding="utf-8")
    code, payload = invoke(monkeypatch, capsys, "content", "audit", str(tmp_path), "--json")
    assert code == 1
    assert payload["ok"] is False
    assert payload["data"]["counts"]["runtime"] == 1

def test_t8_reports_content_plane_violation(tmp_path: Path) -> None:
    (tmp_path / "run.py").write_text("print('x')", encoding="utf-8")
    health = HarnessRunner().run(make_manifest(tmp_path), ("T8",))
    assert health.ok is False
    assert health.issues[0].code == "L4-CONTENT-008"
```

- [ ] **Step 6: Run integration tests and verify RED**

Run: `uv run --group dev pytest tests/test_cli_contracts.py tests/test_harness.py -q`

Expected: FAIL because CLI `content audit` and gate `T8` do not exist.

- [ ] **Step 7: Wire CLI and opt-in T8 gate**

`cmd_content()` must return exit 2 for usage/root errors, exit 1 when runtime/cache violations exist, and exit 0 when only content/contracts/projections exist. The JSON envelope must always include `data.root`, `data.counts`, `data.violations`, and `data.artifacts`.

`HarnessRunner._gate_t8()` maps runtime findings to `L4-CONTENT-008`, cache findings to `L4-CONTENT-009`, and projection findings to warning `L4-CONTENT-010`. Add `T8` to supported `GATES`, but do not add it to `PROFILE_GATES` in this wave.

- [ ] **Step 8: Run focused and full l4-kernel tests**

Run: `uv run --group dev pytest tests/test_content_plane.py tests/test_cli_contracts.py tests/test_harness.py -q`

Expected: PASS.

Run: `uv run --group dev pytest tests/ -q`

Expected: PASS with only the pre-existing opt-in integration skips.

---

### Task 2: l4-kernel legacy 执行面 fail closed

**Files:**
- Modify: `projects/l4-kernel/src/l4_kernel/cli.py`
- Modify: `projects/l4-kernel/src/l4_kernel/plugins.py`
- Modify: `projects/l4-kernel/src/l4_kernel/workflows.py`
- Modify: `projects/l4-kernel/src/l4_kernel/mcp_server.py`
- Modify: `projects/l4-kernel/tests/test_cli_contracts.py`
- Modify: `projects/l4-kernel/tests/test_plugins.py`
- Modify: `projects/l4-kernel/tests/test_workflows.py`
- Modify: `projects/l4-kernel/tests/test_mcp_server.py`

**Interfaces:**
- Produces: stable `L4-EXECUTION-012` denial envelope for legacy execution.
- Preserves: `skill list/show` and `workflow list/show` read-only inspection.
- Changes: CLI、MCP、`ScenarioEngine.run_*` and ten no-op functional actions can no longer return success.

- [ ] **Step 1: Write failing tests for denied CLI execution**

```python
@pytest.mark.parametrize("surface", [("skill", "run"), ("workflow", "run")])
def test_legacy_execution_surfaces_fail_closed(surface, monkeypatch, capsys):
    code, payload = invoke(monkeypatch, capsys, *surface, "sample", "asset")
    assert code == 1
    assert payload["error"]["code"] == "L4-EXECUTION-012"
    assert payload["error"]["authority"] == "omo"
```

- [ ] **Step 2: Write failing tests for no-op plugin actions**

```python
@pytest.mark.parametrize("name", [
    "knowledge_index", "knowledge_search", "knowledge_categorize",
    "entity_register", "entity_review", "entity_update",
    "storage_archive", "storage_cleanup", "cross_domain_sync", "cross_domain_notify",
])
def test_functional_legacy_actions_fail_closed(name, tmp_path):
    action = DocumentKemsPlugin().get_actions()[name]
    result = action(tmp_path)
    assert result["status"] == "deprecated"
    assert result["ok"] is False
    assert result["error"]["code"] == "L4-EXECUTION-012"
```

- [ ] **Step 3: Run tests and verify RED**

Run: `uv run --group dev pytest tests/test_cli_contracts.py tests/test_plugins.py -q`

Expected: FAIL because current surfaces execute or return `status=ok`.

- [ ] **Step 4: Implement one shared denial builder**

```python
def legacy_execution_denied(surface: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "deprecated",
        "error": {
            "code": "L4-EXECUTION-012",
            "message": "L4 is a declarative content plane; dispatch execution through OMO",
            "surface": surface,
            "authority": "omo",
        },
    }
```

Read-only review/evaluate functions remain available. All methods that previously returned success without an observable state transition call the shared builder.

- [ ] **Step 5: Run focused and full tests**

Run: `uv run --group dev pytest tests/test_cli_contracts.py tests/test_plugins.py -q`

Expected: PASS.

Run: `uv run --group dev pytest tests/ -q`

Expected: PASS.

---

### Task 3: Cockpit KEMS scan 收敛到 l4-kernel content audit

**Files:**
- Modify: `projects/cockpit/src/cockpit/commands/kems.py`
- Create: `projects/cockpit/src/cockpit/tests/test_kems_command.py`

**Interfaces:**
- Consumes: `l4-kernel content audit ROOT --json` from Task 1.
- Produces: `cockpit kems scan` as the only human-facing Documents content-plane audit entry.
- Configuration: `L4_DOCUMENTS_ROOT`, default `Path.home() / "Documents"`.

- [ ] **Step 1: Write failing command construction test**

```python
def test_kems_scan_delegates_to_content_plane_audit(monkeypatch, tmp_path):
    monkeypatch.setenv("L4_DOCUMENTS_ROOT", str(tmp_path))
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append((cmd, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert cmd_kems_scan(argparse.Namespace()) == 0
    cmd, kwargs = seen[0]
    assert cmd[-5:] == ["l4_kernel.cli", "content", "audit", str(tmp_path), "--json"]
```

- [ ] **Step 2: Run test and verify RED**

Run: `uv run pytest src/cockpit/tests/test_kems_command.py -q`

Expected: FAIL because current command delegates to nonexistent `l4_kernel.cli kems scan`.

- [ ] **Step 3: Implement minimal delegation**

Use `os.environ.get("L4_DOCUMENTS_ROOT")`, `Path.home() / "Documents"` fallback, and `subprocess.run(..., check=False)`. Preserve the child exit code so the audit remains fail closed.

- [ ] **Step 4: Run focused and project tests**

Run: `uv run pytest src/cockpit/tests/test_kems_command.py -q`

Expected: PASS.

Run: `uv run pytest src/cockpit/tests/ -q`

Expected: PASS.

---

### Task 4: Documents 薄桥与迁移台账

**Files:**
- Modify: `/Users/xiamingxing/Documents/@公共/_runtime/kems-materialize.py`
- Modify: `/Users/xiamingxing/Documents/@学习进化/_knowledge/10-systems/KEMS/README.md`
- Create: `docs/reports/2026-08-11-documents-content-plane-migration-inventory.md`

**Interfaces:**
- Consumes: `projects/runtime/scripts/kems-materialize.py` (byte-identical existing owner before replacement).
- Produces: a thin compatibility bridge at the old Documents path.
- Produces: inventory with `content | contract | runtime | projection | cache | bridge` classification and destination owner.

- [ ] **Step 1: Record duplicate evidence before replacing the Documents copy**

Run:

```bash
shasum -a 256 "/Users/xiamingxing/Documents/@公共/_runtime/kems-materialize.py" \
  "projects/runtime/scripts/kems-materialize.py"
diff -u "/Users/xiamingxing/Documents/@公共/_runtime/kems-materialize.py" \
  "projects/runtime/scripts/kems-materialize.py"
```

Expected: identical SHA-256 and empty diff.

- [ ] **Step 2: Replace duplicate implementation with an env-driven thin bridge**

```python
#!/usr/bin/env python3
"""Compatibility bridge to the Workspace-owned KEMS materializer."""

from __future__ import annotations

import os
import sys
from pathlib import Path

workspace = Path(os.environ.get("BOS_WORKSPACE_ROOT", Path.home() / "Workspace")).expanduser()
target = workspace / "projects" / "runtime" / "scripts" / "kems-materialize.py"
if not target.is_file():
    raise SystemExit(f"Workspace KEMS materializer unavailable: {target}")
os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])
```

- [ ] **Step 3: Update KEMS README authority wording**

The README must state:

- Documents KEMS is methodology/Profile/ontology/rubric SSOT only.
- `@学习进化/_control/executors/`, KEMS `_runtime/`, KEMS MCP, and `@公共/_runtime/kems*` are legacy execution surfaces pending bridge/retirement.
- Formal runtime points to Kairon/KOS, execution to OMO + Workflow Mesh + Runtime, human entry to Cockpit.
- Historical version claims are historical capability records, not live runtime truth.

- [ ] **Step 4: Generate and review migration inventory**

Run:

```bash
uv run --directory ".subtrees/l4-kernel" python -m l4_kernel.cli \
  content audit "/Users/xiamingxing/Documents" --json
```

Expected: exit 1 while legacy runtime/cache debt remains. Record exact counts and representative paths in the report; do not call the Documents tree clean.

- [ ] **Step 5: Verify the compatibility bridge without materializing data**

Run:

```bash
BOS_WORKSPACE_ROOT="/Users/xiamingxing/ws-documents-content-plane-convergence" \
python3 "/Users/xiamingxing/Documents/@公共/_runtime/kems-materialize.py" --help
```

Expected: Runtime-owned script help and exit 0; no graph DB or Documents write.

---

### Task 5: Cross-project verification and governed closeout

**Files:**
- Review only: root diff, l4-kernel diff, cockpit diff, Documents non-Git diff evidence.

- [ ] **Step 1: Run l4-kernel tests and lint**

Run: `uv run --group dev pytest tests/ -q`

Run: `uv run --group dev ruff check src tests`

Expected: PASS.

- [ ] **Step 2: Run Cockpit focused/full tests and lint**

Run: `uv run pytest src/cockpit/tests/test_kems_command.py -q`

Run: `uv run pytest src/cockpit/tests/ -q`

Run: `uv run ruff check src/cockpit/commands/kems.py src/cockpit/tests/test_kems_command.py`

Expected: PASS.

- [ ] **Step 3: Run Workspace contract gates**

Run: `make check-layers`

Run: `make doc-ssot-lint`

Run: `make ssot-guardian`

Expected: PASS or report exact pre-existing blockers without hiding them.

- [ ] **Step 4: Verify the governed workflow**

Run:

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" verify \
  "20260811T023138Z-project-code-change-fefc8423" --from-diff --execute
```

Expected: verification evidence recorded for the claimed paths.

- [ ] **Step 5: Stop before commit**

Review `git status --short`, `git diff --stat`, submodule diffs and the non-Git Documents changes. Do not commit, push, submit PR or merge until the user explicitly confirms those operations.
