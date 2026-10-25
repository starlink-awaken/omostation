"""check-work-landed 的 BET 落地兜底回归测试 (2026-10-25)

背景: run yaml 自己声明的落地凭证 (中间 SHA / 被取代的 PR) 失效时, 检查器
曾把 13 条已完成的 BET 判成 missing_landing:blocking。实际工作早已通过后续
PR 落地 —— 凭证在 main 的提交信息里 (squash 合并写作 "标题 (#NNNN)")。

本测试钉住两件事:
  1. 兜底能识别「工作确实已落地」的 run (不误报)
  2. 兜底**不掩盖**真滞留: BET 在 main 无任何痕迹时仍必须判 blocking

第 2 点比第 1 点重要 —— 兜底一旦放宽就会变成「永不报警」的门。
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "check-work-landed.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_work_landed", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_run(runs_dir: Path, run_id: str, *, bet: str | None, sha: str) -> None:
    bet_line = f"bet_id: {bet}\n" if bet else ""
    (runs_dir / f"{run_id}.yaml").write_text(
        f"""run_id: {run_id}
workflow_id: project-code-change
status: ok
actor: test
created_at: '2026-09-01T00:00:00Z'
updated_at: '2026-09-01T00:00:00Z'
{bet_line}evidence:
- landed as {sha}
""",
        encoding="utf-8",
    )


@pytest.fixture()
def checker(tmp_path, monkeypatch, capsys):
    module = _load_module()
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(module, "RUNS_DIR", runs)
    yield module, runs


def _run_main(module) -> dict:
    buf: list[str] = []
    real = sys.stdout
    sys.stdout = type("Cap", (), {"write": lambda self, s: buf.append(s), "flush": lambda self: None})()
    try:
        module.main(["--json"])
    finally:
        sys.stdout = real
    return json.loads("".join(buf))


class TestBetLandingFallback:
    def test_fake_bet_with_no_main_trace_stays_blocking(self, checker):
        """BET id 在 main 完全没有痕迹 -> 必须仍判 blocking (兜底不掩盖真滞留)。"""
        module, runs = checker
        _write_run(
            runs,
            "20260901T000000Z-project-code-change-aaaaaaaa",
            bet="BET-Y2Q9-ZZZ-999",
            sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        )
        report = _run_main(module)
        assert report["summary"]["blocking"] == 1
        assert report["findings"][0]["kind"] == "missing_landing:blocking"

    def test_nonexistent_bet_stays_blocking(self, checker):
        """虚构 BET -> 仍 blocking。"""
        module, runs = checker
        _write_run(
            runs,
            "20260901T000001Z-project-code-change-bbbbbbbb",
            bet="BET-NOT-EXIST-12345",
            sha="cafecafecafecafecafecafecafecafecafe",
        )
        report = _run_main(module)
        assert report["summary"]["blocking"] == 1

    def test_run_without_bet_id_stays_blocking(self, checker):
        """无 bet_id 的 run 不走兜底 -> 仍 blocking。"""
        module, runs = checker
        _write_run(
            runs,
            "20260901T000003Z-project-code-change-dddddddd",
            bet=None,
            sha="2222222222222222222222222222222222222222",
        )
        report = _run_main(module)
        assert report["summary"]["blocking"] == 1

    def test_real_bet_with_main_commit_is_settled(self, checker):
        """真实 BET 且 main 有其提交 -> 判 settled (不再误报)。"""
        module, runs = checker
        # BET-Y2Q3-T9-01 在 origin/main 有提交 (PR #4304), 与生产历史一致
        _write_run(
            runs,
            "20260901T000002Z-project-code-change-cccccccc",
            bet="BET-Y2Q3-T9-01",
            sha="1111111111111111111111111111111111111111",
        )
        report = _run_main(module)
        assert report["summary"]["blocking"] == 0
        assert report["summary"]["settled"] == 1
        assert report["findings"] == []

    def test_bet_log_refs_extracts_pr_from_main(self, checker):
        """_bet_log_refs 能从 main 提交信息里取出已合并 PR 号。"""
        module, _ = checker
        refs = module._bet_log_refs("BET-Y2Q3-T9-01")
        assert refs, "应能从 origin/main 提交信息里提取到 PR 号"
        assert any(r.startswith("pr:") for r in refs)
