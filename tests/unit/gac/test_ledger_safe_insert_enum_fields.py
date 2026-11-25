"""``ledger-safe-insert`` 的枚举/必填字段校验与 ``bet-ledger.py::cmd_lint`` 同口径。

背景（债条目 OMO-DEBT-LEDGER-INSERT-SKIPS-ENUM-CHECKS）：插入器此前只查结构
（binding 四键 / 三轴 / digest / decision_ref），不查 ``meta.status_enum``、
``tracks``、``meta.windows`` 与必填字段，于是一条越界载荷可以「插入 rc=0 →
CI 全绿」—— lint 明明持有这些判据，但 CI 只把它当信息性输出。

判据与被检对象不共享失效模式：这里逐条**篡改一个字段**并要求插入器拒收，
另配一条全字段合法的**正例**（防「一律拒收」的放宽）与一条 candidate 起草态
（lint 对 candidate 本就不强制必填字段）。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "bin" / "gac" / "ledger-safe-insert.py"

STATUS_ENUM = ["candidate", "pending", "in_progress", "review", "done", "blocked", "failed"]
WINDOWS = ["Y1Q4", "Y2Q4"]
TRACKS = {"T1-TRUTH": {"title": "真相与止血"}, "T6-SUBTRACT": {"title": "减法"}}


def _write_case(
    tmp_path: Path,
    *,
    entry_overrides: dict | None = None,
    drop_fields: tuple[str, ...] = (),
) -> tuple[Path, Path]:
    spec = tmp_path / "specs" / "new-bet.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# New BET\n", encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(spec.read_bytes()).hexdigest()

    ledger = tmp_path / "docs" / "plans" / "3y-bet-ledger.yaml"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "bets": [{"id": "BET-OLD", "title": "Old BET"}],
                "campaigns": [],
                "concurrency": {},
                "disciplines": {},
                "gates": {},
                "meta": {"total_bets": 1, "status_enum": STATUS_ENUM, "windows": WINDOWS},
                "milestones": [],
                "objectives": [],
                "retro": {},
                "tracks": TRACKS,
                "vision": {},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    entry = {
        "id": "BET-NEW",
        "track": "T1-TRUTH",
        "window": "Y2Q4",
        "title": "New BET",
        "appetite": "M",
        "status": "in_progress",
        "goal": "把 X 收敛到单一实现",
        "done_when": ["判据 A 在读出侧转绿"],
        "verify": ["python3 bin/gac/check-x.py --json"],
        "workflow": "project-code-change",
        "write_surfaces": ["bin/gac/**"],
        "accepted_specifications": [
            {
                "spec_ref": "repo://specs/new-bet.md",
                "spec_version": "1.0.0",
                "content_digest": digest,
                "decision_ref": "decision://accepted/BET-NEW",
            }
        ],
        "completion_evidence": {
            "axes": {
                "engineering": {"evidence": {}, "status": "NOT_STARTED"},
                "operational": {"evidence": {}, "status": "NOT_PROVEN"},
                "value": {"evidence": {}, "status": "NOT_PROVEN"},
            },
            "overall_state": "evaluating",
            "schema_version": "completion-evidence-matrix/v1",
        },
    }
    for field in drop_fields:
        entry.pop(field, None)
    entry.update(entry_overrides or {})

    entry_path = tmp_path / "entry.yaml"
    entry_path.write_text(yaml.safe_dump(entry, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return ledger, entry_path


def _run(ledger: Path, entry: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--file", str(entry), "--ledger", str(ledger)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_full_entry_is_accepted(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path)

    result = _run(ledger, entry, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    data = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    assert [bet["id"] for bet in data["bets"]] == ["BET-OLD", "BET-NEW"]


def test_candidate_draft_is_accepted_without_full_fields(tmp_path: Path) -> None:
    """candidate 是起草态：lint 本就不强制必填字段与 track/window，插入器同口径。"""
    ledger, entry = _write_case(
        tmp_path,
        entry_overrides={"status": "candidate"},
        drop_fields=("track", "window", "appetite", "goal", "done_when", "verify", "workflow", "write_surfaces"),
    )

    result = _run(ledger, entry, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_rejects_status_outside_enum(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path, entry_overrides={"status": "finished"})
    before = ledger.read_bytes()

    result = _run(ledger, entry, tmp_path)

    assert result.returncode != 0
    assert "非法 status finished" in result.stderr
    assert ledger.read_bytes() == before


def test_rejects_unknown_window(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path, entry_overrides={"window": "Y9Q9"})
    before = ledger.read_bytes()

    result = _run(ledger, entry, tmp_path)

    assert result.returncode != 0
    assert "未知 window Y9Q9" in result.stderr
    assert ledger.read_bytes() == before


def test_rejects_unknown_track(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path, entry_overrides={"track": "no-such-track"})
    before = ledger.read_bytes()

    result = _run(ledger, entry, tmp_path)

    assert result.returncode != 0
    assert "未知 track no-such-track" in result.stderr
    assert ledger.read_bytes() == before


def test_rejects_missing_required_fields(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path, drop_fields=("goal", "done_when", "verify"))
    before = ledger.read_bytes()

    result = _run(ledger, entry, tmp_path)

    assert result.returncode != 0
    for field in ("goal", "done_when", "verify"):
        assert f"缺字段 {field}" in result.stderr
    assert ledger.read_bytes() == before


def test_required_field_list_is_shared_with_lint(tmp_path: Path) -> None:
    """必填字段清单只有一份：lint 与插入器同引用 ``BET_REQUIRED_FIELDS``。

    抄一份的下场是下一次口径漂移；这条用例把「同源」本身钉住。
    """
    ledger_cli = (ROOT / "bin" / "plan" / "bet-ledger.py").read_text(encoding="utf-8")
    inserter = (ROOT / "bin" / "gac" / "ledger-safe-insert.py").read_text(encoding="utf-8")

    assert "BET_REQUIRED_FIELDS = (" in ledger_cli
    assert "required = BET_REQUIRED_FIELDS" in ledger_cli
    assert "_ledger_contract().BET_REQUIRED_FIELDS" in inserter
    assert 'required = ["track"' not in inserter
