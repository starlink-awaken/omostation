#!/usr/bin/env python3
"""check-evidence-freshness: verify evidence-smoke report is recent.

Reads the report the writer (bin/gac/evidence-smoke.py) lands, checks it is within
7 days and scores >= 90. If nothing is readable, generates one and judges that
generation by the same criteria.

Output:
  - exit 0 = evidence fresh and healthy
  - exit 1 = report too old, score too low, generation failed, or the generated
    report is not readable at the path this checker resolves
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# ADR-0456 B5 / BET-Y2Q4-T10-238: 读侧根必须与写侧逐表达式同形且在调用时刻求值。
# 写侧是 evidence-smoke.py:111 `_output_dir()` = state_root() / ".omo/_delivery/evidence-smoke";
# 本模块此前在 import 时刻由 __file__ 反推检出根，声明 profile 后读者永远命中不到写者产物，
# 于是每次运行都走生成支路 —— 把「首跑必绿」放大成「每跑必绿」。
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from repo_root import code_root  # noqa: E402
from repo_root import state_root as runtime_state_root  # noqa: E402

EVIDENCE_RELATIVE_DIR = Path(".omo") / "_delivery" / "evidence-smoke"
MAX_AGE = timedelta(days=7)
MIN_SCORE = 90.0


def _evidence_dir() -> Path:
    """读侧证据目录 = 写侧 `_output_dir()`；两者只在「同一表达式」时才是同一个目录。"""
    return runtime_state_root() / EVIDENCE_RELATIVE_DIR


def _latest_report() -> Path | None:
    """Return the path to the latest evidence-smoke JSON report."""
    evidence_dir = _evidence_dir()
    if not evidence_dir.exists():
        return None
    files = sorted(evidence_dir.glob("*.json"), reverse=True)
    return files[0] if files else None


def _read_report(report_path: Path, now: datetime) -> tuple[float, int]:
    """Return (score, age_days) measured from the file itself."""
    mtime = datetime.fromtimestamp(report_path.stat().st_mtime, tz=UTC)
    try:
        with open(report_path) as f:
            score = float(json.load(f).get("evidence_health_score", 0))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        score = 0.0
    return score, (now - mtime).days


def _run_evidence_smoke() -> dict:
    """Run evidence-smoke and return the parsed report.

    脚本路径与 cwd 取检出侧代码根（读的是仓内代码），落盘根由子进程自己按 profile 解析
    （这里不传 env=，profile 靠继承传下去）。
    """
    workspace = code_root()
    result = subprocess.run(
        [sys.executable, str(workspace / "bin" / "gac" / "evidence-smoke.py"), "--json"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Parse JSON from stdout (may have non-JSON prefix)
    raw = result.stdout
    start = raw.find("{")
    if start < 0:
        return {"ok": False, "error": "no JSON in output"}
    return json.loads(raw[start:])


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    violations: list[dict] = []
    score = 0.0
    age_days = -1

    report_path = _latest_report()
    measured = report_path is not None
    if report_path is None:
        # No report readable at this root — generate one (a clean CI checkout has none).
        # Generating is not a waiver: the same two criteria are applied below.
        generated = _run_evidence_smoke()
        if generated.get("error"):
            violations.append({"type": "generation_failed", "detail": generated["error"]})
        else:
            measured = True
            report_path = _latest_report()
            if report_path is None:
                # 生成成功而读路径上没有那份产物：写者与读者不在这棵树上。
                # 静默 PASS 就是本 BET 要修的洞，所以把它报成一条判据。
                violations.append(
                    {
                        "type": "evidence_unreadable",
                        "detail": (
                            f"evidence-smoke returned a score but no report is readable at {_evidence_dir()}"
                        ),
                    }
                )
                score = float(generated.get("evidence_health_score", 0) or 0)
                age_days = 0

    if report_path is not None:
        score, age_days = _read_report(report_path, now)

    if measured:
        if age_days > MAX_AGE.days:
            violations.append(
                {
                    "type": "stale_report",
                    "detail": f"report age {age_days}d > {MAX_AGE.days}d max",
                }
            )
        if score < MIN_SCORE:
            violations.append(
                {
                    "type": "low_score",
                    "detail": f"score {score} < {MIN_SCORE} min",
                }
            )

    ok = len(violations) == 0

    if args.json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "score": score,
                    "age_days": age_days,
                    "max_age_days": MAX_AGE.days,
                    "evidence_dir": str(_evidence_dir()),
                    "report_path": str(report_path) if report_path else None,
                    "violations": violations,
                },
                indent=2,
            )
        )
    else:
        status = "PASS" if ok else "FAIL"
        print(f"check-evidence-freshness: {status} (score={score}, age={age_days}d)")
        for v in violations:
            print(f"  VIOLATION: {v['type']} — {v['detail']}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
