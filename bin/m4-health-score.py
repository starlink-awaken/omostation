#!/usr/bin/env python3
"""M4 Health Score — 量化 M4 元模型闭环状态

设计: 不重复 mof-bootstrap.py 的 PASS/FAIL, 但补充:
  - 量化分数 (0-100)
  - 历史快照对比
  - 与 ADR-0132 §8 关闭标准对齐

输出:
  - stdout: 人类可读分数
  - .omo/_derived/m4-health.json: JSON 派生面 (ADR-0129 范式, gitignored)
  - 与 OMO health_score (system.yaml) 平行, 不替代

分数规则 (100 = 完美):
  + mof-validate 通过率 (60%)
  + 5-check strict 全 PASS (30%)
  + 8/4/4 映射完整 (5%)
  + 9 ADR 全 ACCEPTED (5%)

用法:
    uv run --with "pyyaml" python bin/m4-health-score.py
    uv run --with "pyyaml" python bin/m4-health-score.py --json
    uv run --with "pyyaml" python bin/m4-health-score.py --emit   # 写派生面
    uv run --with "pyyaml" python bin/m4-health-score.py --compare  # 与上次对比
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


WS = Path(__file__).resolve().parents[1]
DERIVED_PATH = WS / "projects/ecos/.omo/_derived/m4-health.json"


def _run(cmd: list[str], cwd: Path = WS, timeout: int = 120) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def _git(*args: str, cwd: Path = WS) -> str:
    rc, out, _ = _run(["git", *args], cwd=cwd)
    return out.strip() if rc == 0 else ""


def score_mof_validate() -> tuple[int, int, float]:
    """mof-validate 通过率: 0-60 分"""
    rc, out, _ = _run([
        "uv", "run", "--with", "pyyaml", "python",
        "projects/ecos/src/ecos/ssot/tools/mof-validate.py",
    ], timeout=180)
    for line in out.splitlines():
        if "节点:" in line:
            parts = line.split("|")
            passed = int(parts[1].split(":")[1].strip())
            total = int(parts[0].split(":")[1].strip())
            return passed, total, passed / total * 60
    return 0, 1, 0.0


def score_4check_strict() -> tuple[bool, float]:
    """5-check strict 全 PASS: 30 分 (check_5 是 Round 3a 新增)"""
    rc, out, _ = _run([
        "uv", "run", "--with", "pyyaml", "python",
        "bin/mof-bootstrap.py", "all",
    ], timeout=60)
    passed = rc == 0
    return passed, 30.0 if passed else 0.0


def score_meta_mapping() -> tuple[bool, float]:
    """8+4+4 映射完整: 5 分"""
    import tempfile
    code = '''
import sys
sys.path.insert(0, "projects/ecos/src")
from ecos.l0.ssot.mof_bridge import M3MetaLoader
from ecos.l0.ssot.meta_model import MetaType
loader = M3MetaLoader.get_instance()
for mt in MetaType:
    assert loader.meta_type_to_m3(mt) is not None, f"{mt.name} 缺映射"
print("all 8 mapped")
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(code)
        tmp = f.name
    try:
        rc, _, err = _run(["uv", "run", "--with", "pyyaml", "python", tmp], timeout=30)
    finally:
        Path(tmp).unlink()
    return rc == 0, 5.0 if rc == 0 else 0.0


def score_adr_accepted() -> tuple[int, int, float]:
    """8 个 ADR 全 ACCEPTED: 5 分 (按比例给分)"""
    index = WS / ".omo/_knowledge/decisions/INDEX.md"
    if not index.exists():
        return 0, 8, 0.0
    content = index.read_text()
    # 找 0132..0139 (M4 系列)
    m4_adrs = ["0132", "0133", "0134", "0135", "0136", "0137", "0138", "0139"]
    ac = 0
    for n in m4_adrs:
        # INDEX 行格式: "| 0132 | TITLE | ACCEPTED | ..."
        prefix = f"| {n} |"
        for line in content.splitlines():
            if line.startswith(prefix) and "ACCEPTED" in line:
                ac += 1
                break
    rate = ac / len(m4_adrs)
    return ac, len(m4_adrs), rate * 5


def score_40_tests() -> tuple[int, int, float]:
    """40 回归测试 — 回放最近 m4-health.json 派生面 (避免循环依赖)

    注意: 跑 `python bin/m4-health-score.py` 时不应递归子进程跑
    `tests/integration/m4_metamodel/run_all.py`, 否则形成无限递归。
    实际执行顺序: 开发者先跑 tests 写 m4-health.json, 再跑 score 读它。
    bonus 字段表示测试套件质量, 不参与 overall_score 计算。
    """
    if not DERIVED_PATH.exists():
        return 0, 40, 0.0
    import json as _json
    data = _json.loads(DERIVED_PATH.read_text())
    bonus = data.get("bonus", {}).get("regression_tests_40", {})
    p = bonus.get("passed", 0)
    t = bonus.get("total", 40)
    return p, t, p / t * 100 if t else 0.0


def score_40_tests_live() -> tuple[int, int, float]:
    """实际跑 tests (CLI 单独命令, 不在 compute_health 内嵌)"""
    rc, out, _ = _run([
        "uv", "run", "--with", "pyyaml", "python",
        "tests/integration/m4_metamodel/run_all.py",
    ], timeout=300)
    m = re.search(r"(\d+)/(\d+) PASS", out)
    if not m:
        return 0, 40, 0.0
    p, t = int(m.group(1)), int(m.group(2))
    return p, t, p / t * 100


def compute_health() -> dict:
    """计算 M4 Health Score + 所有分量"""
    passed, total, mof60 = score_mof_validate()
    check4, c430 = score_4check_strict()
    meta_ok, meta5 = score_meta_mapping()
    ac, total9, adr5 = score_adr_accepted()
    p40, t40, tests_rate = score_40_tests()

    main_total = mof60 + c430 + meta5 + adr5
    overall = round(min(main_total, 100), 2)

    return {
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": str(WS),
        "git_sha": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "metrics": {
            "mof_validate": {
                "passed": passed,
                "total": total,
                "rate": round(passed / total * 100, 2),
                "score": round(mof60, 2),
                "weight": 60,
            },
            "five_check_strict": {
                "all_pass": check4,
                "score": c430,
                "weight": 30,
            },
            "meta_mapping_8x4x4": {
                "all_mapped": meta_ok,
                "score": meta5,
                "weight": 5,
            },
            "adr_accepted_9": {
                "accepted": ac,
                "total": total9,
                "score": round(adr5, 2),
                "weight": 5,
            },
        },
        "bonus": {
            "regression_tests_40": {
                "passed": p40,
                "total": t40,
                "rate": round(tests_rate, 2),
            },
        },
        "overall_score": overall,
        "adrs": {
            "main": ["ADR-0132 (M4 upgrade)", "ADR-0133 (L0 constraints v2)",
                     "ADR-0134 (M3-meta bridge)", "ADR-0135 (derived plane)",
                     "ADR-0136 (P5 4-gap closure)", "ADR-0137 (plane relocation)",
                     "ADR-0138 (MetaElement promotion)", "ADR-0139 (8-stage reject)"],
            "closed_when": "overall_score == 100 AND all main ADRs ACCEPTED",
        },
    }


def print_human(h: dict) -> None:
    m = h["metrics"]
    print(f"# M4 Health Score ({h['generated_at']})")
    print(f"  branch: {h['branch']}  sha: {h['git_sha'][:8]}")
    print(f"  overall: {h['overall_score']}/100")
    print()
    print(f"  mof-validate:  {m['mof_validate']['passed']}/{m['mof_validate']['total']}"
          f"  ({m['mof_validate']['rate']}%)  →  {m['mof_validate']['score']}/{m['mof_validate']['weight']}")
    print(f"  5-check strict: {'PASS' if m['five_check_strict']['all_pass'] else 'FAIL'}"
          f"  →  {m['five_check_strict']['score']}/{m['five_check_strict']['weight']}")
    print(f"  meta mapping:   {m['meta_mapping_8x4x4']['score']}/{m['meta_mapping_8x4x4']['weight']}")
    print(f"  ADR accepted:   {m['adr_accepted_9']['accepted']}/{m['adr_accepted_9']['total']}"
          f"  →  {m['adr_accepted_9']['score']}/{m['adr_accepted_9']['weight']}")
    print()
    bonus = h["bonus"]
    print(f"  bonus: regression tests {bonus['regression_tests_40']['passed']}/{bonus['regression_tests_40']['total']}"
          f"  ({bonus['regression_tests_40']['rate']}%)")


def compare_with_previous(current: dict) -> None:
    """与上次派生面 score 对比"""
    if not DERIVED_PATH.exists():
        print("无上次快照, 无法对比")
        return
    previous = json.loads(DERIVED_PATH.read_text())
    prev_score = previous.get("overall_score", 0)
    cur_score = current["overall_score"]
    delta = cur_score - prev_score
    direction = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
    print(f"对比: {prev_score} → {cur_score}  ({direction} {abs(delta):+.2f})")
    if delta < 0:
        print("⚠️  退化! 立即 round-trip 验证")
    elif delta > 0:
        print("✅ 改进")


def emit(h: dict, path: Path = DERIVED_PATH) -> None:
    """写派生面 JSON"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(h, ensure_ascii=False, indent=2, default=str))
    print(f"✅ 派生面 {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    parser.add_argument("--emit", action="store_true", help="写派生面 (默认路径)")
    parser.add_argument("--compare", action="store_true", help="与上次派生面对比")
    parser.add_argument("--with-live-tests", action="store_true",
                        help="实际跑 40 tests 覆盖 bonus 字段")
    parser.add_argument("--path", type=Path, default=DERIVED_PATH, help="派生面路径")
    args = parser.parse_args()

    # 可选: 先跑 live tests 把结果填进 bonus
    if args.with_live_tests:
        live_p, live_t, _ = score_40_tests_live()
        DERIVED_PATH.parent.mkdir(parents=True, exist_ok=True)
        seed = {
            "version": "1.0.0",
            "bonus": {"regression_tests_40": {
                "passed": live_p, "total": live_t,
                "rate": round(live_p / live_t * 100, 2) if live_t else 0,
            }}
        }
        DERIVED_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2))

    h = compute_health()

    if args.json:
        print(json.dumps(h, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.compare:
        print_human(h)
        print()
        compare_with_previous(h)
        return 0

    print_human(h)
    print()

    if args.emit:
        emit(h, args.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
