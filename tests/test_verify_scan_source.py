"""verify.py 真空合格防护 — 回归测试.

2026-09-19 实证: `verify.py` 扫 `.omo/debt/gap-items/`, 而该目录**不存在**;
`scan()` 里 `if not gap_dir.is_dir(): return checks` 静默返回空 → 下游据 0/0
输出 "✅ 门禁通过: 所有 completed 任务都有 evidence"。

即: 声称用于检测 "resolved but no evidence fraud" 的门禁, **实际什么都没扫**,
且恒真通过。这是"声明/执行鸿沟"的典型实例。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

VERIFY = Path(__file__).resolve().parents[1] / "bin/ssot/verify.py"


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


# ── 源状态探测 ───────────────────────────────────────────


def test_scan_source_missing_returns_minus_one(tmp_path):
    mod = _load()
    d, n = mod.scan_source(tmp_path)
    assert n == -1, "目录缺失应以 -1 表示 (区别于空目录的 0)"
    assert not d.is_dir()


def test_scan_source_empty_dir_returns_zero(tmp_path):
    """空目录是合法的『无 gap-items』, 不得与『目录缺失』混为一谈."""
    mod = _load()
    (tmp_path / ".omo" / "debt" / "gap-items").mkdir(parents=True)
    d, n = mod.scan_source(tmp_path)
    assert n == 0
    assert d.is_dir()


def test_scan_source_counts_files(tmp_path):
    mod = _load()
    g = tmp_path / ".omo" / "debt" / "gap-items"
    g.mkdir(parents=True)
    (g / "a.yaml").write_text("id: A\nlifecycle_state: open\n")
    (g / "b.yaml").write_text("id: B\nlifecycle_state: open\n")
    _, n = mod.scan_source(tmp_path)
    assert n == 2


# ── 真空合格防护 (核心) ──────────────────────────────────


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
    (tmp_path / ".omo" / "debt" / "gap-items").mkdir(parents=True)
    r = _run("--root", str(tmp_path))
    assert r.returncode == 0, f"空目录不应失败: {r.stdout}{r.stderr}"


def test_source_present_with_evidence_passes(tmp_path):
    """有对象且都有证据 → 通过, 且不再是 0/0."""
    g = tmp_path / ".omo" / "debt" / "gap-items"
    g.mkdir(parents=True)
    ev = tmp_path / "proof.txt"
    ev.write_text("evidence\n")
    (g / "a.yaml").write_text(
        "id: A\nlifecycle_state: resolved\nevidence_refs:\n- proof.txt\n")
    r = _run("--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "门禁通过" in r.stdout


def test_real_repo_source_status_is_reported():
    """本仓当前 gap-items/ 缺失 → 防护必须触发 (锁住这个已知状态).

    若未来补齐了该目录, 本测试的断言方向应相应调整 —— 但"源缺失必须失败"
    这条不变量由上面的 test_main_fails_when_source_missing 独立保证。
    """
    mod = _load()
    _, n = mod.scan_source(Path(__file__).resolve().parents[1])
    assert n == -1, (
        "本仓 .omo/debt/gap-items/ 现已存在 —— 请更新本测试, 并确认 verify.py "
        "的扫描源是否已改指向真实债务注册表 (.omo/debt/items/)"
    )
