#!/usr/bin/env python3
"""BET-Y2Q4-T10-238 — evidence-freshness 的读侧根平面。

钉三件事：读侧与写侧解析同一个目录（ISC-1）、生成支路不豁免分数（ISC-2/ISC-3）、
未声明 profile 时逐字节复现历史路径（ISC-4）。ISC-5 由 PRE_FIX_SOURCE 的变异对照承担：
同一注入下改造前必须 PASS、改造后必须 FAIL —— 否则「绿」只说明装置没命中。

PRE_FIX_SOURCE 是缺陷形状的冻结副本（改造前本体），不是第二份实现：它只为变异对照存在，
test_pre_fix_fixture_still_carries_the_defect 钉住它没被顺手改干净。
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

CHECKER = Path(__file__).resolve().parents[2] / "bin" / "gac" / "check-evidence-freshness.py"
REPO_ROOT_LIB = Path(__file__).resolve().parents[2] / "bin" / "lib" / "repo_root.py"
EVIDENCE_REL = Path(".omo") / "_delivery" / "evidence-smoke"

PRE_FIX_SOURCE = '''"""legacy (pre BET-Y2Q4-T10-238): read side anchored at the checkout, import time."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = WORKSPACE / ".omo" / "_delivery" / "evidence-smoke"
MAX_AGE = timedelta(days=7)
MIN_SCORE = 90.0


def _latest_report():
    if not EVIDENCE_DIR.exists():
        return None
    files = sorted(EVIDENCE_DIR.glob("*.json"), reverse=True)
    return files[0] if files else None


def _run_evidence_smoke():
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "bin" / "gac" / "evidence-smoke.py"), "--json"],
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
        timeout=60,
    )
    raw = result.stdout
    start = raw.find("{")
    if start < 0:
        return {"ok": False, "error": "no JSON in output"}
    return json.loads(raw[start:])


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report_path = _latest_report()
    now = datetime.now(UTC)
    violations = []
    score = 0.0
    age_days = -1

    if report_path:
        mtime = datetime.fromtimestamp(report_path.stat().st_mtime, tz=UTC)
        age_days = (now - mtime).days
        try:
            with open(report_path) as f:
                report = json.load(f)
            score = report.get("evidence_health_score", 0)
        except (json.JSONDecodeError, OSError):
            score = 0
        if age_days > MAX_AGE.days:
            violations.append({"type": "stale_report", "detail": f"report age {age_days}d"})
        if score < MIN_SCORE:
            violations.append({"type": "low_score", "detail": f"score {score} < {MIN_SCORE} min"})
    else:
        report = _run_evidence_smoke()
        score = report.get("evidence_health_score", 0)
        age_days = 0
        if report.get("error"):
            violations.append({"type": "generation_failed", "detail": report["error"]})

    ok = len(violations) == 0
    if args.json:
        print(json.dumps({"ok": ok, "score": score, "age_days": age_days, "violations": violations}, indent=2))
    else:
        print(f"check-evidence-freshness: {'PASS' if ok else 'FAIL'} (score={score}, age={age_days}d)")
    return 0 if ok else 1
'''


def _load(source_text: str, checkout: Path, filename: str):
    target = checkout / "bin" / "gac" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source_text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def _fixture(checkout: Path, state_root: Path | None, *, legacy: bool = False):
    """把检查器装载到一棵合成树上：repo_root 由 fixture 供给，profile env 逐例钉死。

    checkout 必须是已 resolve 的路径 —— 检查器经 code_root() 反推检出根时带 .resolve()，
    两侧写法不同会让断言比较两个同名不同串的目录（macOS 的 /var → /private/var）。
    """
    assert checkout == checkout.resolve(), "fixture checkout 根必须已 resolve"
    saved_repo_root = sys.modules.pop("repo_root", None)
    saved_path = list(sys.path)
    saved_env = {key: os.environ.get(key) for key in ("OMOSTATION_STATE_ROOT", "OMOSTATION_ROOT", "OMO_EVENT_LEDGER_DB")}
    try:
        lib_dir = checkout / "bin" / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT_LIB, lib_dir / "repo_root.py")
        spec = importlib.util.spec_from_file_location("repo_root", lib_dir / "repo_root.py")
        assert spec is not None and spec.loader is not None
        seeded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seeded)
        sys.modules["repo_root"] = seeded
        for key in ("OMOSTATION_ROOT", "OMO_EVENT_LEDGER_DB", "OMOSTATION_STATE_ROOT"):
            os.environ.pop(key, None)
        if state_root is not None:
            os.environ["OMOSTATION_STATE_ROOT"] = str(state_root)
        if legacy:
            yield _load(PRE_FIX_SOURCE, checkout, "legacy_check_evidence_freshness.py")
        else:
            yield _load(CHECKER.read_text(encoding="utf-8"), checkout, "check_evidence_freshness_under_test.py")
    finally:
        sys.path[:] = saved_path
        if saved_repo_root is None:
            sys.modules.pop("repo_root", None)
        else:
            sys.modules["repo_root"] = saved_repo_root
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _materialize(report_dir: Path, *, score: float, age: timedelta) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "2026-01-01.json"
    path.write_text(json.dumps({"evidence_health_score": score}), encoding="utf-8")
    stamp = datetime.now(UTC) - age
    os.utime(path, (stamp.timestamp(), stamp.timestamp()))
    return path


def _run_json(module, capsys) -> tuple[int, dict]:
    rc = module.main(["--json"])
    out = capsys.readouterr().out
    start = out.find("{")
    assert start >= 0, f"检查器没有输出 JSON：{out!r}"
    return rc, json.loads(out[start:])


def _violation_types(payload: dict) -> list[str]:
    return [v["type"] for v in payload["violations"]]


def test_import_time_checkout_anchor_is_gone_and_detector_is_not_a_no_op():
    """ISC-5 自证：detector 必须点名改造前的形状，否则空绿只说明装置没命中。"""
    import ast

    def import_time_anchors(source: str) -> list[str]:
        hits = []
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and "__file__" in ast.dump(node.value):
                hits.append(",".join(getattr(target, "id", "?") for target in node.targets))
        return hits

    current = import_time_anchors(CHECKER.read_text(encoding="utf-8"))
    assert current == [], f"读侧仍在 import 时刻反推检出根: {current}"
    assert "WORKSPACE" in import_time_anchors(PRE_FIX_SOURCE)


def test_pre_fix_fixture_still_carries_the_defect():
    """变异对照的前提：冻结副本里「生成支路不比分数」那条洞还在。"""
    assert "MAX_AGE = timedelta(days=7)" in PRE_FIX_SOURCE
    assert "MIN_SCORE = 90.0" in PRE_FIX_SOURCE
    generation_branch = PRE_FIX_SOURCE[PRE_FIX_SOURCE.index("        report = _run_evidence_smoke()") :]
    assert "MIN_SCORE" not in generation_branch


def test_reader_lands_on_the_writers_tree(tmp_path, capsys):
    """ISC-1 正向落点：只物化在 state 根的陈旧报告，必须被读出它自己的真实年龄。"""
    checkout = (tmp_path / "checkout").resolve()
    state = tmp_path / "state"
    stale = _materialize(state / EVIDENCE_REL, score=95.0, age=timedelta(days=8))
    with _fixture(checkout, state) as checker:
        def must_not_generate() -> dict:
            raise AssertionError("检查器解析错了根，掉进生成支路")

        checker._run_evidence_smoke = must_not_generate
        rc, payload = _run_json(checker, capsys)
    assert rc == 1
    assert payload["age_days"] == 8
    assert payload["report_path"] == str(stale)
    assert payload["evidence_dir"] == str(state / EVIDENCE_REL)
    assert _violation_types(payload) == ["stale_report"]


def test_generation_does_not_waive_the_score(tmp_path, capsys):
    """ISC-2：生成落到了读路径 ⇒ 同一 MIN_SCORE 判据照跑；改造前同一注入必须 PASS。"""
    checkout = (tmp_path / "checkout").resolve()
    state = tmp_path / "state"
    with _fixture(checkout, state) as checker:
        def low_score_run() -> dict:
            _materialize(checker._evidence_dir(), score=42.0, age=timedelta(0))
            return {"evidence_health_score": 42.0}

        checker._run_evidence_smoke = low_score_run
        rc, payload = _run_json(checker, capsys)
    assert rc == 1
    assert _violation_types(payload) == ["low_score"]

    with _fixture(checkout, state, legacy=True) as legacy:
        legacy._run_evidence_smoke = lambda: {"evidence_health_score": 42.0}
        legacy_rc, legacy_payload = _run_json(legacy, capsys)
    assert legacy_rc == 0, "改造前若不再 PASS，对照就失去了意义"
    assert legacy_payload["violations"] == []


def test_split_becomes_visible_instead_of_tolerated(tmp_path, capsys):
    """ISC-3：生成成功而读路径看不见 ⇒ evidence_unreadable；改造前同一注入静默 PASS。"""
    checkout = (tmp_path / "checkout").resolve()
    state = tmp_path / "state"
    with _fixture(checkout, state) as checker:
        checker._run_evidence_smoke = lambda: {"evidence_health_score": 99.0}
        rc, payload = _run_json(checker, capsys)
        resolved_dir = checker._evidence_dir()
    assert rc == 1
    assert _violation_types(payload) == ["evidence_unreadable"]
    assert resolved_dir == state / EVIDENCE_REL

    with _fixture(checkout, state, legacy=True) as legacy:
        legacy._run_evidence_smoke = lambda: {"evidence_health_score": 99.0}
        legacy_rc, legacy_payload = _run_json(legacy, capsys)
    assert legacy_rc == 0 and legacy_payload["ok"] is True


def test_generation_failure_is_reported_once(tmp_path, capsys):
    """没测到分数时不补一条 low_score —— 失败原因只说一次。"""
    checkout = (tmp_path / "checkout").resolve()
    state = tmp_path / "state"
    with _fixture(checkout, state) as checker:
        checker._run_evidence_smoke = lambda: {"ok": False, "error": "no JSON in output"}
        rc, payload = _run_json(checker, capsys)
    assert rc == 1
    assert _violation_types(payload) == ["generation_failed"]


def test_no_profile_resolves_the_historical_path_byte_for_byte(tmp_path):
    """ISC-4：未声明 profile 时读侧字符串 == <checkout>/.omo/_delivery/evidence-smoke。"""
    checkout = (tmp_path / "checkout").resolve()
    with _fixture(checkout, None) as checker:
        assert str(checker._evidence_dir()) == str(checkout / EVIDENCE_REL)
        assert str(checker.EVIDENCE_RELATIVE_DIR) == ".omo/_delivery/evidence-smoke"
        assert checker.MAX_AGE == timedelta(days=7)
        assert checker.MIN_SCORE == 90.0


def test_subprocess_targets_the_checkout_code_root(tmp_path):
    """脚本路径与 cwd 仍取检出侧代码根，且不传 env=（profile 靠继承传下去）。"""
    checkout = (tmp_path / "checkout").resolve()
    state = tmp_path / "state"
    seen: list[dict] = []

    def fake_run(argv, **kwargs):
        seen.append({"argv": list(argv), "kwargs": dict(kwargs)})
        return SimpleNamespace(stdout="", returncode=1)

    with _fixture(checkout, state) as checker:
        checker.subprocess = SimpleNamespace(run=fake_run)
        report = checker._run_evidence_smoke()
    assert report == {"ok": False, "error": "no JSON in output"}
    assert seen[0]["argv"][1] == str(checkout / "bin" / "gac" / "evidence-smoke.py")
    assert seen[0]["kwargs"]["cwd"] == str(checkout)
    assert "env" not in seen[0]["kwargs"]


def test_fixture_is_hermetic_against_the_host_profile_root(tmp_path):
    """fixture 的检出根不得由 host 的 ~/Workspace 决定（AGENTS.md §7 host 泄漏条）。"""
    checkout = (tmp_path / "checkout").resolve()
    with _fixture(checkout, None) as checker:
        resolved = str(checker._evidence_dir())
    assert resolved.startswith(str(tmp_path.resolve())), resolved
    assert "/Workspace" not in resolved


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q", "-p", "no:randomly"]))
