"""ADR-0080 D1 的 `x2-rule-lint` 必须真的接在门禁上。

背景: ADR-0080 D1 把 `x2-rule-lint` 列为 4 个必接的 pre-commit 钩子之一, 理由是
「P83-P85 新增的治理工具均无集成, 治理质量靠 agent 自觉跑」。但该 ADR 写的机制
(`.pre-commit-config.yaml`) 在本仓是**声明表不是生效面** (见该文件顶部: 本仓
`core.hooksPath=.githooks`), 真正的本地门禁是 `gac-local-gate` —— 于是这条要求
在本面落空。同批 4 个里 `adr-coverage` / `governance-dashboard` 已由 sgf-policy
纳进门禁, `x2-rule-lint` 与 `mof-m2-coverage` 没有 (2026-11-22 接线前者)。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "bin" / "gac" / "gac-local-gate.py"
TOOL = ROOT / "bin" / "gac" / "x2-rule-lint.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("gac_local_gate_x2", GATE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gac_local_gate_x2"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_gate_registers_x2_rule_lint():
    gate = _load_gate()
    entries = [g for g in gate.GATES_LIST if g.get("id") == "x2-rule-lint"]
    assert len(entries) == 1, f"门禁里找不到 x2-rule-lint: {[g.get('id') for g in gate.GATES_LIST]}"
    assert entries[0]["command"] == ["bin/gac/x2-rule-lint.py"]


def test_tool_is_read_only_and_currently_clean():
    """接线前先确认它只读、且当前常规档是绿的 —— 否则接线那一刻就把门禁弄红。"""
    src = TOOL.read_text(encoding="utf-8")
    for banned in ("write_text", "open(", "subprocess", "os.remove", "shutil"):
        assert banned not in src, f"x2-rule-lint 不是只读工具 (出现 {banned})"
    r = subprocess.run(
        [sys.executable, str(TOOL)], cwd=str(ROOT),
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, f"常规档应 exit 0 (ADR 只要求 error 级阻塞):\n{r.stdout}\n{r.stderr}"


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
