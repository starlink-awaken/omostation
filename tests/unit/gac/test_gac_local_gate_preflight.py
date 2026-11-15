"""门禁的「检出是否备齐」结构化 preflight。

契约来源：2026-11-15 实测 —— `gac-local-gate --strict` 在 `origin/main` 的 fresh
worktree（不 init 子模块、不物化生成态）上 **16/87 hard fail**，逐条定性后
**16/16 都是缺输入**（15 条子模块未初始化 + 1 条生成态未物化）；同一份 295 条
BOS 声明在 canonical 检出上是 `score 94.0 / gap 0`，在 fresh worktree 上是
`62.6 / gap 184`。

`preflight` 字段**不改变** `hard_fails` 与退出码：它只把「这棵树没备齐」变成
机器可读的信号，让缺输入造成的红不再与真缺陷同形。
"""

from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-local-gate.py"


def _load():
    spec = importlib.util.spec_from_file_location("gac_local_gate_preflight", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_subprocess(monkeypatch: pytest.MonkeyPatch, module, stdout: str) -> None:
    class _Proc:
        def __init__(self, out: str) -> None:
            self.stdout = out

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: _Proc(stdout))


def test_uninitialized_submodules_parses_dash_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    _fake_subprocess(
        monkeypatch,
        module,
        "-aaaaaaa projects/agora (heads/main)\n"
        " bbbbbbb projects/ecos (heads/main)\n"
        "-ccccccc projects/omo (heads/main)\n",
    )
    assert module._uninitialized_submodules() == ["projects/agora", "projects/omo"]


def test_uninitialized_submodules_empty_when_all_checked_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load()
    _fake_subprocess(monkeypatch, module, " aaaaaaa projects/ecos (heads/main)\n")
    assert module._uninitialized_submodules() == []


def test_preflight_incomplete_when_inputs_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "SGF_POLICY_YAML", module.WORKSPACE / "does-not-exist.yaml")
    monkeypatch.setattr(module, "_uninitialized_submodules", lambda: ["projects/agora"])
    monkeypatch.setattr(module, "GENERATED_INPUTS", (module.WORKSPACE / "absent.yaml",))

    report = module.preflight_report()

    assert report["complete"] is False
    assert report["sgf_policy_loaded"] is False
    assert report["uninitialized_submodules"] == ["projects/agora"]
    assert report["missing_generated_inputs"] == [str(module.WORKSPACE / "absent.yaml")]
    assert len(report["reasons"]) == 3  # policy + 子模块 + 生成态，三条都在


def test_preflight_complete_when_inputs_present(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    existing = module.WORKSPACE / "README.md"
    monkeypatch.setattr(module, "SGF_POLICY_YAML", existing)
    monkeypatch.setattr(module, "_uninitialized_submodules", lambda: [])
    monkeypatch.setattr(module, "GENERATED_INPUTS", (Path("README.md"),))

    report = module.preflight_report()

    assert report["complete"] is True
    assert report["reasons"] == []


def test_run_gate_carries_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "gate_checks", lambda *a, **k: ())
    monkeypatch.setattr(module, "run_checks", lambda checks: [])
    monkeypatch.setattr(module, "change_lane_files_for_scope", lambda *a, **k: [])
    monkeypatch.setattr(module, "_read_state_fingerprint", lambda: {})
    monkeypatch.setattr(module, "_check_drift", lambda snap: None)
    monkeypatch.setattr(module, "_update_drift_topic", lambda report, drift: None)
    monkeypatch.setattr(module, "extract_finding_topics", lambda results: [])
    monkeypatch.setattr(module, "preflight_report", lambda: {"complete": False, "reasons": ["x"]})

    report = module.run_gate(scope="files", files=["README.md"], strict=True)

    assert report["preflight"] == {"complete": False, "reasons": ["x"]}
    # preflight 不得改变判定语义：没有 hard_fails 时门仍是绿的
    assert report["ok"] is True


def test_print_human_banner_only_when_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    base = {
        "ok": True,
        "scope": "files",
        "change_lane_files": [],
        "checks": [],
        "hard_fails": [],
        "soft_warns": [],
        "finding_topics": [],
    }

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        module.print_human({**base, "preflight": {"complete": True, "reasons": []}})
    assert "检出未备齐" not in err.getvalue()

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        module.print_human(
            {**base, "preflight": {"complete": False, "reasons": ["子模块未初始化: projects/agora"]}}
        )
    assert "检出未备齐" in err.getvalue()
    assert "projects/agora" in err.getvalue()
