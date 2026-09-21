"""主仓测试集可收集性守卫 (P85 配套).

防"孤儿测试"腐烂: CI 只跑 ~11 个主仓测试文件, 余下 ~353 个存在
"不运行 → 引用已删文件/落后契约 无人知" 的盲区。

2026-09-21 实测: 4 个文件 collection error 即让 `pytest tests/` 整体
Interrupted (后由 #4132 修复)。本守卫把该类腐化变成可机械检测的 gate。

契约:
1. 干净态 → exit 0
2. 仓内腐化 (引用仓内已删文件) → exit 1, 且归类为 repo_errors
3. 环境依赖缺失 → 报告但不 FAIL (不阻塞本地开发)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "bin" / "gac" / "check-test-collection.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_test_collection", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_classify_env_vs_repo() -> None:
    """分类器: 第三方缺失 = env; 仓内文件缺失 / 语法错 = repo。"""
    gate = _load()
    assert gate._classify("ModuleNotFoundError: No module named 'aiosqlite'") == "env"
    assert gate._classify("FileNotFoundError: [Errno 2] ... '/x/bin/gone.py'") == "repo"
    assert gate._classify("SyntaxError: invalid syntax") == "repo"
    # 仓内顶层名的 import 失败 = 仓内腐化 (回归: 曾因 return 位置错误全判 env)
    assert gate._classify("ModuleNotFoundError: No module named 'bin.gac.gone_xyz'") == "repo"
    assert gate._classify("ModuleNotFoundError: No module named 'projects.omo.nope'") == "repo"
    # 回归: CI 上 env 错误曾使 ok=False (误判 FAIL) —— 第三方包名须识别为 env
    assert gate._classify("ImportError: simulated: fastapi unavailable") == "env"
    assert gate._classify("ModuleNotFoundError: No module named 'rich'") == "env"


def test_env_only_errors_do_not_fail_the_gate(tmp_path: Path) -> None:
    """核心回归: 仅环境依赖缺失时不得 FAIL (CI 上 6 个 env 错误曾致 gate 红)。

    契约: ok 只取决于 repo_errors, 与 pytest 原始 returncode 无关 ——
    pytest 因 collection error 退出非 0, 但那不代表仓内腐化。
    """
    d = tmp_path / "t"
    d.mkdir()
    # 引用一个不存在的第三方包 (非仓内顶层名)
    (d / "test_env.py").write_text(
        "import absolutely_not_a_real_pkg_zzz\n\ndef test_x():\n    assert True\n",
        encoding="utf-8",
    )
    gate = _load()
    result = gate.collect([str(d)])
    assert result["ok"] is False, "pytest 因 collection error 退出非 0"
    # 但分类后应为 env, 不产生 repo_errors
    assert gate._classify(result["errors"][0]["reason"]) == "env"


def test_clean_fixture_collects_with_exit_zero(tmp_path: Path) -> None:
    """干净测试 → 收集成功且 exit 0。"""
    d = tmp_path / "t"
    d.mkdir()
    (d / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    gate = _load()
    result = gate.collect([str(d)])
    assert result["ok"] is True
    assert result["collected"] == 1
    assert result["errors"] == []


def test_repo_rot_is_reported_as_error(tmp_path: Path) -> None:
    """仓内腐化 (import 不存在的仓内模块) → 被收集为 error 且非 ok。"""
    d = tmp_path / "t"
    d.mkdir()
    (d / "test_rot.py").write_text(
        "import definitely_not_a_real_module_xyz\n\ndef test_x():\n    assert True\n",
        encoding="utf-8",
    )
    gate = _load()
    result = gate.collect([str(d)])
    assert result["ok"] is False
    assert result["errors"], "腐化文件应产生 collection error"


def test_live_repo_collection_is_clean() -> None:
    """实测主仓: 允许环境性跳过, 但不得有仓内腐化。

    CI 的 actions/checkout 带 `submodules: recursive`, 故 CI 上应为 0 error。
    本地若子模块未 init 可能出现环境性条目 —— 由 degraded_env 处理。
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=WORKSPACE,
        timeout=900,
    )
    report = json.loads(proc.stdout)
    assert report["status"] in {"pass", "pass_with_env_skips", "env_skip"}, report
    assert report["repo_errors"] == [], f"存在仓内腐化: {report['repo_errors']}"
    assert report["collected"], "应收集到测试"
    assert proc.returncode == 0


def test_missing_path_in_uninit_submodule_is_env() -> None:
    """指向未物化子模块的缺失 = 环境性 (开发者不必拉齐全部子模块)。"""
    gate = _load()
    reason = (
        "FileNotFoundError: [Errno 2] No such file or directory: "
        "'/ws/projects/omlxc/src/omlxc/dataplane/embedding_mps.py'"
    )
    assert gate._missing_path_in_uninit_submodule(reason, ["projects/omlxc"]) is True
    # 不在子模块内 → 仍按仓内腐化
    other = "FileNotFoundError: [Errno 2] No such file or directory: '/ws/bin/gac/gone.py'"
    assert gate._missing_path_in_uninit_submodule(other, ["projects/omlxc"]) is False
