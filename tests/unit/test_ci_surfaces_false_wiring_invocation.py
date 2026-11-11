"""「被 workflow 执行」= 出现**调用**形态，不是「文本里提过」。

缺陷（2026-11-11 自证）：false-wiring 判据用 `tool in text`，于是路径过滤器、
ruff 参数表、注释里的同路径提及都被当成执行。实测漏报：
`bin/gac/documents_domain_jobs.py` 声明由 `phase-gate-enforce.yml` 执行，
而该 workflow 只在**路径过滤器**（`bin/gac/documents_domain_jobs.py|\`）与
**ruff 参数表**里出现它，全仓没有任何 `python3|bash … documents_domain_jobs.py`
调用形态 —— 这条假声明因此长期不漏报。

判据：`WIRED_COMMAND_RE` 要求解释器（python3/bash/sh/zsh/uv run）后跟工具路径，
并允许 `../../` 前缀（governance-verify 的 cwd 在 projects/omo）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-ci-surfaces.py"


def _load():
    spec = importlib.util.spec_from_file_location("ci_surfaces_invoc_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def test_invocation_forms_are_recognized() -> None:
    """各种真实调用形态都要认出来。"""
    assert MODULE._invoked_tools("python3 bin/gac/x.py") == {"bin/gac/x.py"}
    assert MODULE._invoked_tools("python bin/ssot/y.py --check") == {"bin/ssot/y.py"}
    assert MODULE._invoked_tools("bash bin/gac/z.sh") == {"bin/gac/z.sh"}
    assert MODULE._invoked_tools("uv run --with pytest python -m pytest tests") == set()
    # governance-verify 的 cwd 在 projects/omo ⇒ 工具以 ../../ 调用
    assert MODULE._invoked_tools("python3 ../../bin/ssot/governance_closed_loop.py") == {
        "bin/ssot/governance_closed_loop.py"
    }


def test_mentions_are_not_invocations() -> None:
    """反例保护: 路径过滤器 / ruff 参数 / 注释里的提及不算执行。"""
    assert MODULE._invoked_tools("bin/gac/documents_domain_jobs.py|\\") == set()
    assert MODULE._invoked_tools("          bin/gac/documents_domain_jobs.py") == set()
    assert MODULE._invoked_tools("          # bin/ssot/check-interfaces.py 从未提交进本仓") == set()
    assert MODULE._invoked_tools("ruff check bin/gac/documents_domain_jobs.py") == set()


def test_mentioning_workflow_does_not_satisfy_declaration() -> None:
    """假声明的实况: phase-gate-enforce.yml 提及但从不执行 documents_domain_jobs.py。"""
    wf = (ROOT / ".github" / "workflows" / "phase-gate-enforce.yml").read_text(encoding="utf-8", errors="ignore")
    tool = "bin/gac/documents_domain_jobs.py"
    assert tool in wf, "前提变了: 该 workflow 已不再提及此工具"
    assert tool not in MODULE._invoked_tools(wf), "提及被当成了执行"


def _surface_case(monkeypatch, tmp_path: Path, workflow_text: str) -> list[str]:
    """合成一个「声明了 workflow 的 surface」, 跑 check_ci_surfaces 取 warnings。"""
    (tmp_path / "wf.yml").write_text(workflow_text, encoding="utf-8")
    monkeypatch.setattr(MODULE, "WORKFLOWS_DIR", tmp_path)

    def fake_load(path):
        if Path(path).name == "ci-surfaces.yaml":
            return {
                "surfaces": [
                    {
                        "id": "x",
                        "tool": "bin/gac/fake-mention-only.py",
                        "workflow": "wf.yml",
                        "gate": False,
                        "triggers": [],
                        "status": "active",
                    }
                ]
            }
        return {}

    monkeypatch.setattr(MODULE, "_load_yaml", fake_load)
    return MODULE.check_ci_surfaces()["warnings"]


def test_mention_only_declaration_is_flagged(monkeypatch, tmp_path) -> None:
    """端到端: workflow 只在 ruff 参数里提到该工具 ⇒ 必须报 false-wiring。"""
    warnings = _surface_case(monkeypatch, tmp_path, "jobs:\n  x:\n    steps:\n      - run: ruff check bin/gac/fake-mention-only.py\n")
    assert any("fake-mention-only" in w and "false-wiring" in w for w in warnings), warnings


def test_real_invocation_is_not_flagged(monkeypatch, tmp_path) -> None:
    """反例保护: 真的调用该工具 ⇒ 不得报 false-wiring。"""
    warnings = _surface_case(
        monkeypatch, tmp_path, "jobs:\n  x:\n    steps:\n      - run: python3 bin/gac/fake-mention-only.py --check\n"
    )
    assert not any("fake-mention-only" in w and "false-wiring" in w for w in warnings), warnings
