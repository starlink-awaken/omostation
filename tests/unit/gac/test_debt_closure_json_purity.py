"""check-debt-closure-discipline `--json` 的 stdout 纯净性 — 回归测试.

债: DEBT-CLOSURE-CHECK-JSON-STDOUT-POLLUTED
`scan_gate_level_enum()` 把 gate_level 分布统计 print 到 stdout，`--json` 模式下
它排在 JSON 报告之前 ⇒ `--json | json 解析` 一律失败（机器读数不可用）。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "bin/gac/check-debt-closure-discipline.py"


def _load():
    spec = importlib.util.spec_from_file_location("debt_closure_json_purity", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["debt_closure_json_purity"] = mod
    spec.loader.exec_module(mod)
    return mod


def _item(d: Path, name: str, **fields) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v!r}" if isinstance(v, str) else f"{k}: {v}"
             for k, v in fields.items()]
    p = d / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_distribution_line_goes_to_stderr(tmp_path, capsys):
    """统计行换流到 stderr，不丢弃、不污染 stdout."""
    d = tmp_path / "items"
    _item(d, "a.yaml", id="A", gate_level="watchlist")
    _item(d, "b.yaml", id="B", gate_level="P1")
    tool = _load()
    findings = tool.scan_gate_level_enum(d)
    captured = capsys.readouterr()
    assert len(findings) == 1, "值域外 gate_level 仍要被报出"
    assert captured.out == "", f"stdout 被污染: {captured.out!r}"
    assert "gate_level 分布" in captured.err, "换流不等于丢弃"


def test_json_mode_stdout_is_machine_parseable(tmp_path):
    """端到端复现注册症状：把 --json 的 stdout 直接喂给 json 解析器."""
    items = tmp_path / ".omo" / "debt" / "items"
    items.mkdir(parents=True)
    _item(items, "a.yaml", id="A", gate_level="P1")
    proc = subprocess.run([sys.executable, str(TOOL), "--json"],
                          cwd=tmp_path, capture_output=True, text=True)
    report = json.loads(proc.stdout)
    assert report["gate_level_enum"], "值域违约要进 JSON 报告"
    assert "gate_level 分布" in proc.stderr
