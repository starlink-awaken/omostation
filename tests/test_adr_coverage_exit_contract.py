"""ADR coverage 退出码契约 (P85 / ADR-0367 C4).

Regression: `adr-coverage` 在 sgf-policy.yaml 中被声明为「阻断性」，但此前
`--json` 分支 `return 0` 早退 —— 而 `--json` 正是 gate 里的调用形态。于是
`gac-local-gate.py` 的

    hard_fails = [r for r in results if not r["ok"] and r["name"] not in SOFT_CHECKS]
    ok = len(hard_fails) == 0

永远看不到该检查失败，使 ADR 编号重复 / INDEX 失配零成本进入 main。
实证：缺陷提交 ec7c8f538 上 adr-coverage 报 2 项 findings，gate 却是 success。

契约：**任何调用形态**（含 `--json`）都必须在 issues>0 时返回非零。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "adr" / "adr-coverage.py"

# REQUIRED_FRONTMATTER = ["status", "lifecycle", "owner", "last-reviewed"]
_FM = "---\nid: {id}\nstatus: accepted\nlifecycle: spec\nowner: t\nlast-reviewed: '2026-01-01'\n---\n"
_INDEX_ROW = "- {id}: {slug} — | 2026-01-01 | t | {file}\n"


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _run(decisions: Path, index: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--decisions",
            str(decisions),
            "--index",
            str(index),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _fixture(tmp_path: Path, ids: list[tuple[str, str]]) -> tuple[Path, Path]:
    """ids = [(adr_id, filename_stem)]; INDEX 收录全部文件。"""
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    rows = []
    for adr_id, stem in ids:
        _write(decisions / f"{stem}.md", _FM.format(id=adr_id) + f"# {adr_id}: {stem}\n")
        rows.append(_INDEX_ROW.format(id=adr_id, slug=stem.split("-", 1)[1], file=f"{stem}.md"))
    index = decisions / "INDEX.md"
    _write(index, "".join(rows))
    return decisions, index


def test_clean_fixture_json_exits_zero(tmp_path: Path) -> None:
    decisions, index = _fixture(tmp_path, [("ADR-0400", "0400-alpha"), ("ADR-0401", "0401-beta")])
    proc = _run(decisions, index, "--json")
    payload = json.loads(proc.stdout)
    assert payload["frontmatter_issues"] == []
    assert payload["missing_numbers"] == []
    assert payload["files_not_in_index"] == []
    assert proc.returncode == 0, f"clean fixture must exit 0, got {proc.returncode}"


def test_duplicate_number_json_exits_nonzero(tmp_path: Path) -> None:
    """核心回归：--json 早退曾使重复编号无法被 gate 捕获。"""
    decisions, index = _fixture(tmp_path, [("ADR-0400", "0400-alpha"), ("ADR-0400", "0400-beta")])
    proc = _run(decisions, index, "--json")
    payload = json.loads(proc.stdout)  # JSON 输出必须保留
    assert payload["duplicate_numbers"] == [400]
    assert proc.returncode != 0, "--json must not mask findings from the gate"


def test_unindexed_file_json_exits_nonzero(tmp_path: Path) -> None:
    """INDEX 失配（#4110 的实际缺陷形态）也必须非零。"""
    decisions, index = _fixture(tmp_path, [("ADR-0400", "0400-alpha")])
    _write(decisions / "0401-orphan.md", _FM.format(id="ADR-0401") + "# ADR-0401: orphan\n")
    proc = _run(decisions, index, "--json")
    payload = json.loads(proc.stdout)
    assert payload["files_not_in_index"] == ["0401-orphan.md"]
    assert proc.returncode != 0


def test_iteration_is_bounded(tmp_path: Path) -> None:
    """护栏：helper 曾因误编辑变成自我递归，防回归。"""
    decisions, index = _fixture(tmp_path, [("ADR-0400", "0400-alpha")])
    proc = _run(decisions, index, "--json")
    assert "RecursionError" not in proc.stderr
    assert proc.returncode == 0
