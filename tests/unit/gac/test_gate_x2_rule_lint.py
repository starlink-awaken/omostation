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


def _load_tool():
    spec = importlib.util.spec_from_file_location("x2_rule_lint", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["x2_rule_lint"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ignored_runtime_targets_are_not_warned(tmp_path: Path) -> None:
    """被 gitignore 的运行态目标在干净检出里本就不存在, 不算失真。

    2026-11-28 实证: 四条 X2 规则的目标全部「0 匹配」, 但其中三条
    (`.omo/evidence/`、`.omo/_delivery/**`、`.omo/debt/*`) 是运行态产物,
    旧判据把它们一并报成 warn, 制造噪声。
    """
    mod = _load_tool()
    (tmp_path / ".gitignore").write_text(
        ".omo/evidence\n.omo/_delivery/*\n.omo/debt/*\n.omo/state/runtime/*\n", encoding="utf-8"
    )
    patterns = mod._ignore_patterns(tmp_path)
    assert mod.is_ignored(".omo/evidence/", patterns)
    assert mod.is_ignored(".omo/_delivery/adr-drift-apply-history.jsonl", patterns)
    assert mod.is_ignored(".omo/debt/dashboard/current.yaml", patterns)
    assert mod.is_ignored(".omo/state/runtime/some-runtime-artifact.json", patterns)
    assert not mod.is_ignored("src/omo/real.py", patterns)


def test_missing_target_warns_only_when_not_ignored(tmp_path: Path) -> None:
    """正反一对: 缺席且未被忽略 -> warn; 缺席但被忽略 -> 不 warn。"""
    mod = _load_tool()
    (tmp_path / ".gitignore").write_text(".omo/state/runtime/*\n", encoding="utf-8")
    rule_warn = {
        "rule_id": "X2-FRESH-DEMO",
        "target": "projects/gone/crontab",
        "freshness": {"threshold_days": 7, "action": "warn"},
    }
    rule_ok = {
        "rule_id": "X2-FRESH-RUNTIME",
        "target": ".omo/state/runtime/dashboard.json",
        "freshness": {"threshold_days": 7, "action": "warn"},
    }
    issues = mod.lint_rules([rule_warn], tmp_path)
    assert [i["severity"] for i in issues if "0 匹配" in i["msg"]] == ["warn"]
    assert not [i for i in mod.lint_rules([rule_ok], tmp_path) if "0 匹配" in i["msg"]]


def test_repo_rules_have_no_target_warnings() -> None:
    """对本仓实际规则集跑一遍: target glob 的 warn 必须为 0（2026-11-28 起）。"""
    mod = _load_tool()
    rules = mod.load_rules(ROOT / ".omo" / "_truth" / "x2-freshness-rules.yaml")
    issues = mod.lint_rules(rules, ROOT)
    assert not [i for i in issues if "0 匹配" in i["msg"]], issues
