"""Tests for omo lint schemas (Round 15 P0 — schema 写时契约静态校验).

覆盖:
  1. _check_module_append_has_schema: 合规模块返回空 list
  2. _check_module_append_has_schema: 故意违规模块返回违规位置
  3. _check_module_append_has_schema: 解析失败的源码不抛 (返回 parse error)
  4. cmd_lint_schemas: 6/6 CONSUMER_MODULES 都合规 (生产代码)
  5. cmd_lint_schemas: 退出码 0 = pass

设计:
  - 直接调 _check_module_append_has_schema 走单元测试, 避免 subprocess
  - 写 1 个临时 .py 文件 (tmp_path 内) 含故意违规, 验证检测能力
"""
from __future__ import annotations

import sys
from pathlib import Path

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


# ── 1. 合规模块: 返回空 list ──────────────────────────────


def test_check_module_append_has_schema_passes_for_compliant_module(tmp_path):
    """合规模块 (所有 .append() 都传 schema=) 应返回空 list."""
    from omo.omo_lint import _check_module_append_has_schema

    good = tmp_path / "good_consumer.py"
    good.write_text(
        '''
from omo.omo_io import AppendOnlyLog
from omo.omo_io_schemas import OmoAuditRecord

def record():
    AppendOnlyLog("/tmp/x.jsonl").append(
        {"ts": "2026-06-09T00:00:00Z", "action": "a", "actor": "u"},
        schema=OmoAuditRecord,
    )
''',
        encoding="utf-8",
    )
    violations = _check_module_append_has_schema(good)
    assert violations == [], f"expected no violations, got {violations}"


# ── 2. 故意违规模块: 返回违规位置 ──────────────────────────


def test_check_module_append_has_schema_detects_missing_schema(tmp_path):
    """故意写一个 .append() 不传 schema=, 应被检测出 1 处违规."""
    from omo.omo_lint import _check_module_append_has_schema

    bad = tmp_path / "bad_consumer.py"
    bad.write_text(
        '''
from omo.omo_io import AppendOnlyLog

def record():
    AppendOnlyLog("/tmp/x.jsonl").append({"ts": "2026-06-09T00:00:00Z"})
''',
        encoding="utf-8",
    )
    violations = _check_module_append_has_schema(bad)
    assert len(violations) == 1, f"expected 1 violation, got {len(violations)}"
    line, snippet = violations[0]
    assert line > 0
    assert "append" in snippet


# ── 3. parse error: 不抛, 返回 parse error 标记 ────────


def test_check_module_append_has_schema_handles_syntax_error(tmp_path):
    """syntax error 的源码不应抛, 应返回 [(0, parse error message)]."""
    from omo.omo_lint import _check_module_append_has_schema

    broken = tmp_path / "broken.py"
    broken.write_text("def record(:\n    pass\n", encoding="utf-8")  # syntax error

    violations = _check_module_append_has_schema(broken)
    assert len(violations) == 1
    line, msg = violations[0]
    assert line == 0
    assert "parse error" in msg


# ── 4. cmd_lint_schemas: 6 个 CONSUMER_MODULES 全合规 ──


def test_cmd_lint_schemas_passes_for_real_consumer_modules(capsys):
    """6 个真实 consumer 模块 (omo_audit/sync/alert/event/history/trail) 全合规."""
    from omo.omo_lint import cmd_lint_schemas

    rc = cmd_lint_schemas()
    assert rc == 0, "real consumer modules should all pass schema= 校验"

    captured = capsys.readouterr()
    # 6 个模块都打印 "✅"
    assert captured.out.count("✅") >= 6
    # 没有 "❌"
    assert "❌" not in captured.out
    # 最终汇总 pass
    assert "pass" in captured.out


# ── 5. CONSUMER_MODULES 列表是 7 个 (全 7 consumer 覆盖) ──


def test_consumer_modules_list_covers_all_seven():
    """CONSUMER_MODULES 是 7 个 (Round 17 P0 +6 omo_bos_metrics, Round 18 P0 +7 omo_history)."""
    from omo.omo_lint import CONSUMER_MODULES

    assert len(CONSUMER_MODULES) == 7
    assert "omo_audit.py" in CONSUMER_MODULES
    assert "omo_bos_metrics.py" in CONSUMER_MODULES  # Round 17 P0
    assert "omo_history.py" in CONSUMER_MODULES     # Round 18 P0 (append_entry 收严)
    assert "omo_sync.py" in CONSUMER_MODULES
    assert "omo_alert.py" in CONSUMER_MODULES
    assert "omo_event.py" in CONSUMER_MODULES
    assert "omo_trail.py" in CONSUMER_MODULES


# ── 6. CLI 集成: omo.cli lint schemas 退出码 0 ─────────


def test_cli_lint_schemas_subprocess():
    """`python -m omo.cli lint schemas` 退出码 0 (生产代码全合规)."""
    import subprocess
    OMO_PROJ = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, "-m", "omo.cli", "lint", "schemas"],
        capture_output=True, text=True, timeout=15,
        cwd=str(OMO_PROJ),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "pass" in r.stdout


# ── 7. Round 21 P0 新规则: SCHEMA_REGISTRY 完整性 ─────


def test_check_schema_registry_integrity_passes_for_real_schemas():
    """SCHEMA_REGISTRY 8 schema 全部继承 ZTimestampModel + 至少 1 必填字段."""
    from omo.omo_lint import _check_schema_registry_integrity

    issues = _check_schema_registry_integrity()
    assert issues == [], f"expected no issues, got {issues}"


def test_check_schema_registry_integrity_detects_missing_z_timestamp(tmp_path, monkeypatch):
    """故意加 1 个非 ZTimestampModel schema, 应被检测出 'missing-z-timestamp'."""
    from omo.omo_io_schemas import SCHEMA_REGISTRY, OmoTrailRecord
    from pydantic import BaseModel

    # 在 SCHEMA_REGISTRY 临时加 1 个不继承 ZTimestampModel 的 schema
    class FakeNotZ(BaseModel):
        ts: str  # 没 Z 校验

    monkeypatch.setitem(SCHEMA_REGISTRY, "fake_not_z", FakeNotZ)
    try:
        from omo.omo_lint import _check_schema_registry_integrity
        issues = _check_schema_registry_integrity()
        # 找到 fake_not_z 的 missing-z-timestamp 违规
        z_issues = [i for i in issues if i[0] == "fake_not_z" and i[1] == "missing-z-timestamp"]
        assert len(z_issues) == 1, f"expected 1 missing-z-timestamp for fake_not_z, got {z_issues}"
    finally:
        # 清理 (monkeypatch 自动还原 setitem, 但显式 del 更稳)
        SCHEMA_REGISTRY.pop("fake_not_z", None)


def test_check_schema_registry_integrity_detects_empty_required(tmp_path, monkeypatch):
    """故意加 1 个全 Optional 的 schema, 应被检测出 'no-required-fields'."""
    from omo.omo_io_schemas import SCHEMA_REGISTRY, ZTimestampModel
    from pydantic import Field

    class FakeEmpty(ZTimestampModel):
        # 全 Optional = 空架子
        ts: str = ""  # 默认值, 非必填

    monkeypatch.setitem(SCHEMA_REGISTRY, "fake_empty", FakeEmpty)
    try:
        from omo.omo_lint import _check_schema_registry_integrity
        issues = _check_schema_registry_integrity()
        empty_issues = [i for i in issues if i[0] == "fake_empty" and i[1] == "no-required-fields"]
        assert len(empty_issues) == 1, f"expected 1 no-required-fields for fake_empty, got {empty_issues}"
    finally:
        SCHEMA_REGISTRY.pop("fake_empty", None)


# ── 8. CLI 集成: omo.cli lint schemas 打印 SCHEMA_REGISTRY 完整性 ──


def test_cli_lint_schemas_prints_schema_registry_check():
    """omo.cli lint schemas 输出含 'SCHEMA_REGISTRY 完整性' 段."""
    import subprocess
    OMO_PROJ = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, "-m", "omo.cli", "lint", "schemas"],
        capture_output=True, text=True, timeout=15,
        cwd=str(OMO_PROJ),
    )
    assert r.returncode == 0
    assert "SCHEMA_REGISTRY 完整性" in r.stdout
    assert "8/8 schema 守 Z-suffix + 必填字段" in r.stdout


# ── 9. Round 29 P0 新规则: __all__ 完整性 ─────────────


def test_check_all_schemas_exported_passes_for_real_schemas():
    """omo_io_schemas.__all__ 包含 8 schema class 全名."""
    from omo.omo_lint import _check_all_schemas_exported

    issues = _check_all_schemas_exported()
    assert issues == [], f"expected no issues, got {issues}"


def test_check_all_schemas_exported_detects_missing_class(monkeypatch):
    """故意从 __all__ 删 1 个 schema class, 应被检测出 'missing-from-all'."""
    from omo.omo_io_schemas import SCHEMA_REGISTRY
    from omo import omo_io_schemas

    # 临时备份 + 删 1 个 class 名
    original = omo_io_schemas.__all__
    new_all = [n for n in original if n != "OmoAuditRecord"]
    monkeypatch.setattr(omo_io_schemas, "__all__", new_all)
    try:
        from omo.omo_lint import _check_all_schemas_exported
        issues = _check_all_schemas_exported()
        audit_issues = [i for i in issues if i[0] == "OmoAuditRecord" and i[1] == "missing-from-all"]
        assert len(audit_issues) == 1, f"expected 1 missing-from-all for OmoAuditRecord, got {audit_issues}"
    finally:
        monkeypatch.setattr(omo_io_schemas, "__all__", original)


# ── 10. Round 30 P0 新规则: consumer SRP 互不依赖 ─────


def test_check_cross_module_srp_passes_for_real_consumers():
    """7 consumer 互不依赖 (仅依赖底层 SSOT), 0 SRP 违规."""
    from omo.omo_lint import _check_cross_module_srp

    issues = _check_cross_module_srp()
    assert issues == [], f"expected no SRP violations, got {issues}"


def test_check_cross_module_srp_whitelist_omo_audit_utility():
    """白名单 omo_audit 工具 (e.g. _utc_now) 不算 SRP 违规.

    实际: omo_history / omo_bos_metrics / omo_sync / omo_trail 等多个 consumer 用了
    omo.omo_audit._utc_now — 这是白名单允许的 (跨模块工具函数共享).
    """
    from omo.omo_lint import _check_cross_module_srp

    issues = _check_cross_module_srp()
    # 任何含 'omo_audit' 违规都说明白名单失效
    audit_violations = [i for i in issues if "omo_audit" in str(i)]
    assert len(audit_violations) == 0, f"omo_audit 应在白名单, got violations: {audit_violations}"


def test_check_cross_module_srp_passes_for_real_consumers():
    """7 consumer 互不依赖 (仅依赖底层 SSOT), 0 SRP 违规."""
    from omo.omo_lint import _check_cross_module_srp

    issues = _check_cross_module_srp()
    assert issues == [], f"expected no SRP violations, got {issues}"


def test_check_cross_module_srp_whitelist_omo_audit_utility():
    """白名单 omo_audit 工具 (e.g. _utc_now) 不算 SRP 违规.

    实际: omo_history / omo_bos_metrics / omo_sync / omo_trail 等多个 consumer 用了
    omo.omo_audit._utc_now — 这是白名单允许的 (跨模块工具函数共享).
    """
    from omo.omo_lint import _check_cross_module_srp

    issues = _check_cross_module_srp()
    # 任何含 'omo_audit' 违规都说明白名单失效
    audit_violations = [i for i in issues if "omo_audit" in str(i)]
    assert len(audit_violations) == 0, f"omo_audit 应在白名单, got violations: {audit_violations}"
