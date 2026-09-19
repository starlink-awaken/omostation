"""verify.py 校验源收敛 + 真空合格防护 — 回归测试.

2026-09-19 两件事:
 1. verify.py 原扫 `.omo/debt/gap-items/` —— 该目录**从未入过 git**; scan()
    `if not gap_dir.is_dir(): return checks` 静默返回空, 下游据 0/0 报
    "✅ 门禁通过", 而其 docstring 声称检测 "resolved but no evidence fraud"。
 2. 收敛到**真实债务注册表** `.omo/debt/items/`。收敛前量化发现: 仅认路径型
    evidence_refs 会对 19 个终态项**全量误报** (债务 schema 以文本型
    resolution_evidence 为主), 故同步扩展 _shared.check_evidence。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "bin/ssot/verify.py"


def _load():
    sys.path.insert(0, str(VERIFY.parent))  # 让它能 import _shared
    spec = importlib.util.spec_from_file_location("verify_mod", VERIFY)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(VERIFY), *args],
                          capture_output=True, text=True, check=False)


def _registry(tmp_path: Path) -> Path:
    d = tmp_path / ".omo" / "debt" / "items"
    d.mkdir(parents=True)
    return d


# ── 收敛: 扫描源指向真实注册表 ───────────────────────────


def test_scan_source_points_to_real_registry():
    """收敛断言: 校验源是 .omo/debt/items, 不再是幽灵 gap-items."""
    mod = _load()
    assert str(mod.GAP_ITEMS_REL) == ".omo/debt/items", (
        "校验源应为真实债务注册表; gap-items 从未存在过")


def test_real_registry_is_actually_scanned():
    """核心: 本仓终态项必须被真实扫到 (不再是 0/0)."""
    mod = _load()
    _, n = mod.scan_source(ROOT)
    assert n > 0, "真实注册表应被扫到, 不得为 0/0"
    checks = mod.scan(ROOT)
    assert len(checks) == n
    assert any(c.is_completed for c in checks), "应有终态项被识别"


def test_closed_counts_as_completed():
    """债务注册表用 closed; 它必须与 resolved 一样算完成."""
    mod = _load()
    for state in ("resolved", "completed", "closed"):
        c = mod.TaskCheck(id="X", title="", phase="?", priority="?",
                          state=state, evidence_count=1, evidence_ok=True)
        assert c.is_completed, f"{state} 应算完成"
        assert c.is_verified, f"{state} + evidence 应算已验证"


# ── 证据扩展 (避免全量误报) ──────────────────────────────


def test_text_evidence_accepted(tmp_path):
    """文本型 resolution_evidence 应被接受为证据 (债务 schema 以它为主)."""
    mod = _load()
    _, ok = mod.check_evidence({"resolution_evidence": "已修复 (PR #1)"}, tmp_path)
    assert ok is True
    _, ok2 = mod.check_evidence({"closed_evidence": "S1 auto-close"}, tmp_path)
    assert ok2 is True


def test_pending_placeholder_is_not_evidence(tmp_path):
    mod = _load()
    _, ok = mod.check_evidence({"resolution_evidence": "<pending>"}, tmp_path)
    assert ok is False, "<pending> 是占位符不是证据"


def test_total_absence_of_evidence_is_flagged(tmp_path):
    """核心负向: 终态但完全没有证据 → 必须检出 (门禁的真实价值)."""
    mod = _load()
    _, ok = mod.check_evidence({"lifecycle_state": "resolved"}, tmp_path)
    assert ok is False


def test_path_evidence_still_works(tmp_path):
    mod = _load()
    (tmp_path / "proof.txt").write_text("x\n")
    _, ok = mod.check_evidence({"evidence_refs": ["proof.txt"]}, tmp_path)
    assert ok is True


# ── 真空合格防护 (源缺失 = config 错误) ──────────────────


def test_scan_source_missing_returns_minus_one(tmp_path):
    mod = _load()
    d, n = mod.scan_source(tmp_path)
    assert n == -1, "目录缺失应以 -1 表示 (区别于空目录的 0)"
    assert not d.is_dir()


def test_main_fails_when_source_missing(tmp_path):
    """核心: 校验源缺失 → 必须失败, 不得报『门禁通过』."""
    r = _run("--root", str(tmp_path))
    assert r.returncode == 1, "源缺失时必须以非零退出"
    assert "校验源不存在" in (r.stderr + r.stdout)
    # 注意: 错误说明文本里会**引用**"门禁通过"这个词作为解释, 故断言完整的通过结论句
    assert "✅ 门禁通过: 所有 completed 任务都有 evidence." not in (r.stdout + r.stderr), \
        "不得再输出真空合格结论"


def test_json_mode_reports_error_and_fails(tmp_path):
    r = _run("--root", str(tmp_path), "--json")
    assert r.returncode == 1
    payload = json.loads(r.stdout)
    assert payload["error"] == "scan_source_missing"
    assert payload["source_exists"] is False
    assert payload["verdict"] == "unknown", "不得声称通过, 应为 unknown"


def test_empty_source_dir_still_passes(tmp_path):
    """空目录 = 无对象可校验 → 合法通过 (不误报)."""
    _registry(tmp_path)
    r = _run("--root", str(tmp_path))
    assert r.returncode == 0, f"空目录不应失败: {r.stdout}{r.stderr}"


def test_source_present_with_evidence_passes(tmp_path):
    """有对象且都有证据 → 通过, 且不再是 0/0."""
    g = _registry(tmp_path)
    ev = tmp_path / "proof.txt"
    ev.write_text("evidence\n")
    (g / "a.yaml").write_text(
        "id: A\nlifecycle_state: resolved\nevidence_refs:\n- proof.txt\n")
    r = _run("--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1/1" in r.stdout, "应真实扫到 1 个对象, 不再是 0/0"


# ── 端到端: 门禁真的会拦 ─────────────────────────────────


def test_gate_flags_resolved_without_evidence(tmp_path):
    """端到端: 放一个无证据的 resolved 项 → 门禁必须失败."""
    d = _registry(tmp_path)
    (d / "a.yaml").write_text("id: A\ntitle: T\nlifecycle_state: resolved\n")
    r = _run("--root", str(tmp_path))
    assert r.returncode == 1, f"无证据的完成项必须被拦: {r.stdout}{r.stderr}"


def test_gate_passes_resolved_with_text_evidence(tmp_path):
    """端到端: 有文本证据的 resolved 项 → 通过."""
    d = _registry(tmp_path)
    (d / "a.yaml").write_text(
        "id: A\ntitle: T\nlifecycle_state: resolved\nresolution_evidence: 已修复\n")
    r = _run("--root", str(tmp_path))
    assert r.returncode == 0, f"有证据不应失败: {r.stdout}{r.stderr}"
