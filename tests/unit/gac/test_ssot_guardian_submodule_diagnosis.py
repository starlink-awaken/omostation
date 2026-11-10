"""ssot-guardian `_check_submodules` 的方向诊断 (2026-11-10 实证: 陈旧检出被念成"未 bump 的提交")。

判定不变是本文件的主断言: '+' 行的 count、severity、FAIL 一律照旧, 只有诊断措辞按方向分开。
"""

import importlib.util
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN = REPO_ROOT / "bin" / "ssot" / "ssot-guardian.py"
DRIFT_SCRIPT = REPO_ROOT / "bin" / "gac" / "check-submodule-pointer-drift.py"

AHEAD_NOTE = "子仓库有未 bump 到根仓库的提交; 需先提交子仓库再更新根指针"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _guardian():
    return _load(GUARDIAN, "ssot_guardian_under_test")


def _drift_helper(root: Path):
    """方向判具的真实副本, 但 REPO_ROOT 指到临时父仓, 让测试用真 git 对象而不是 mock。"""
    module = _load(DRIFT_SCRIPT, "drift_helper_under_test")
    module.REPO_ROOT = root
    return module


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _check(monkeypatch, root: Path, *, with_helper: bool = True) -> dict:
    guardian = _guardian()
    monkeypatch.setattr(guardian, "WORKSPACE_ROOT", root)
    monkeypatch.setattr(
        guardian,
        "_drift_helper",
        (lambda: _drift_helper(root)) if with_helper else (lambda: None),
    )
    return guardian._check_submodules()


def _parent_with_submodule(tmp_path: Path) -> Path:
    """父仓 + file:// 子仓 (v1, v2), 根仓指针钉在 v2。"""
    sub = tmp_path / "sub"
    sub.mkdir()
    _git(sub, "init", "-q", "--initial-branch=main")
    _git(sub, "config", "user.email", "t@x")
    _git(sub, "config", "user.name", "t")
    (sub / "f.md").write_text("v1", encoding="utf-8")
    _git(sub, "add", ".")
    _git(sub, "commit", "-q", "-m", "sub v1")
    (sub / "f.md").write_text("v2", encoding="utf-8")
    _git(sub, "add", ".")
    _git(sub, "commit", "-q", "-m", "sub v2")

    parent = tmp_path / "parent"
    parent.mkdir()
    _git(parent, "init", "-q", "--initial-branch=main")
    _git(parent, "config", "user.email", "t@x")
    _git(parent, "config", "user.name", "t")
    _git(parent, "-c", "protocol.file.allow=always", "submodule", "add", str(sub), "sub")
    _git(parent, "commit", "-q", "-m", "pin v2")
    return parent


def test_stale_checkout_is_not_read_as_unbumped_commit(monkeypatch, tmp_path: Path) -> None:
    """检出落后于指针 = 陈旧检出: 仍算 drift, 但不能再念成"未 bump 的提交"。"""
    parent = _parent_with_submodule(tmp_path)
    pin = _git(parent, "rev-parse", "HEAD:sub")
    v1 = _git(parent / "sub", "rev-parse", f"{pin}~1")
    _git(parent / "sub", "checkout", "-q", v1)

    out = _check(monkeypatch, parent)

    assert out["count"] == 1, "判定不变: 陈旧检出照样计入 drift"
    entry = out["dirty"][0]
    assert entry["direction"] == "stale_checkout"
    assert entry["sha"] == v1
    assert "陈旧检出" in entry["diagnosis"]
    assert "git submodule update --init" in entry["diagnosis"]
    assert "未 bump" not in entry["diagnosis"]
    assert _guardian()._submodule_drift_note(out["dirty"]) == _guardian().SUBMODULE_DIRECTIONS["stale_checkout"]


def test_ahead_checkout_keeps_the_original_wording(monkeypatch, tmp_path: Path) -> None:
    """真·未 bump: 子仓 HEAD 走在指针之前, 诊断必须仍是原来那句话, 一字不差。"""
    parent = _parent_with_submodule(tmp_path)
    (parent / "sub" / "f.md").write_text("v3", encoding="utf-8")
    _git(parent / "sub", "add", ".")
    _git(parent / "sub", "commit", "-q", "-m", "sub v3")

    out = _check(monkeypatch, parent)

    assert out["count"] == 1
    assert out["dirty"][0]["direction"] == "checkout_ahead"
    assert _guardian()._submodule_drift_note(out["dirty"]) == AHEAD_NOTE


def test_missing_objects_degrade_to_unverifiable_without_changing_count(monkeypatch, tmp_path: Path) -> None:
    """浅检出/对象库残缺时不许猜方向: 降级为 unverifiable, count 与条目形状不受影响。"""
    parent = _parent_with_submodule(tmp_path)
    guardian = _guardian()
    monkeypatch.setattr(guardian, "WORKSPACE_ROOT", parent)
    monkeypatch.setattr(guardian, "_drift_helper", lambda: _drift_helper(parent))
    absent = "0" * 40
    monkeypatch.setattr(
        guardian,
        "_run",
        lambda cmd, check=True: subprocess.CompletedProcess(
            cmd, 0, stdout=f"+{absent} sub (heads/main)\n", stderr=""
        ),
    )

    out = guardian._check_submodules()

    assert out["count"] == 1, "判定不变: 测不出方向也照样报 drift"
    entry = out["dirty"][0]
    assert entry["direction"] == "unverifiable"
    assert entry["sha"] == absent


def test_helper_unavailable_keeps_verdict_and_entry_shape(monkeypatch, tmp_path: Path) -> None:
    """方向判具载不进时 (脚本缺失/异常) 原样报告 '+', 不吞掉 drift。"""
    parent = _parent_with_submodule(tmp_path)
    pin = _git(parent, "rev-parse", "HEAD:sub")
    _git(parent / "sub", "checkout", "-q", f"{pin}~1")

    out = _check(monkeypatch, parent, with_helper=False)

    assert out["count"] == 1
    entry = out["dirty"][0]
    assert entry["direction"] == "unverifiable"
    assert {"sha", "path", "ref"} <= set(entry), "print/JSON 消费方依赖这三个键, 新增键只能附加"


def test_clean_checkout_reports_no_drift(monkeypatch, tmp_path: Path) -> None:
    """指针与检出一致时不产生条目, 新代码不会凭空造出 drift。"""
    assert _check(monkeypatch, _parent_with_submodule(tmp_path)) == {"dirty": [], "count": 0}
