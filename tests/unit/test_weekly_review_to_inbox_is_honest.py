"""`bin/gac/weekly-review.py --to-inbox` 必须是**诚实**的：不落地就明说并指路。

契约：`bin/gac/weekly-review.py` 的 docstring / help 里写「--to-inbox  Push to inbox」，
但原实现只打印 `✓ Weekly review pushed to inbox` 而**不写任何文件**（全文件唯一的
`write_text` 在 `--generate` 里）。**假成功比空着更糟** —— 调用方会以为周报已进
cockpit inbox，而 inbox 侧永远收不到。

本用例钉住：即使 REVIEW_FILE 存在（原实现的「成功」分支条件），`--to-inbox` 也必须
返回非零、不得出现「pushed to inbox」字样、并点名接线的替代实现。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "weekly-review.py"


def _load(monkeypatch):
    spec = importlib.util.spec_from_file_location("gac_weekly_review_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "gac_weekly_review_under_test", module)
    spec.loader.exec_module(module)
    return module


def test_to_inbox_refuses_and_points_at_the_real_tool(monkeypatch, tmp_path, capsys) -> None:
    """REVIEW_FILE 存在（原实现的「成功」前提）时也必须拒绝。"""
    module = _load(monkeypatch)
    review_file = tmp_path / "weekly-review-latest.json"
    review_file.write_text(json.dumps({"week": 46, "year": 2026}), encoding="utf-8")
    monkeypatch.setattr(module, "REVIEW_FILE", review_file)
    monkeypatch.setattr(sys, "argv", ["weekly-review.py", "--to-inbox"])

    rc = module.main()
    out = capsys.readouterr().out

    assert rc != 0, out
    assert "pushed to inbox" not in out, out
    assert "bin/ssot/weekly-review.py --post-inbox" in out, out


def test_to_inbox_claims_no_inbox_write(monkeypatch, tmp_path, capsys) -> None:
    """反证：帮助文本声称会 push，而实现不写 —— 帮助文本必须与实现对齐。"""
    module = _load(monkeypatch)
    review_file = tmp_path / "weekly-review-latest.json"
    review_file.write_text(json.dumps({"week": 46}), encoding="utf-8")
    monkeypatch.setattr(module, "REVIEW_FILE", review_file)
    monkeypatch.setattr(sys, "argv", ["weekly-review.py", "--to-inbox"])
    module.main()
    out = capsys.readouterr().out
    # 只要还在声称「已推送」，就是回归。
    assert "✓" not in out, out


def test_generate_writes_the_review_file(monkeypatch, tmp_path, capsys) -> None:
    """对照：`--generate` 是真的落盘的 —— 否则本文件的拒绝就失去了意义。"""
    module = _load(monkeypatch)
    review_file = tmp_path / "weekly-review-latest.json"
    monkeypatch.setattr(module, "REVIEW_FILE", review_file)
    monkeypatch.setattr(module, "_run_cmd", lambda cmd: {"ok": True, "stub": True})
    monkeypatch.setattr(sys, "argv", ["weekly-review.py", "--generate"])

    rc = module.main()
    out = capsys.readouterr().out

    assert rc == 0, out
    assert review_file.is_file(), "generate 必须真的写 REVIEW_FILE"
    payload = json.loads(review_file.read_text(encoding="utf-8"))
    assert {"generated_at", "week", "year", "system_health"} <= set(payload), payload
