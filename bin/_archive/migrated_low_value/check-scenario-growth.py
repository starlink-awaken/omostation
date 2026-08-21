#!/usr/bin/env python3
"""check-scenario-growth: 拦截无真实证据的构造场景/检测器新增 (R2, Q1 装门).

P86 Q1 终止条件的可执行落地 (P3 红线延伸, B1' 标准可执行).
"靠写文档代替装门 = 本轮已证无效" → 本 check 是 gate, 不是文档.

规则:
  - 每个 ADV*/GEN-ADV* 对抗场景必须声明 `real_occurrence_evidence` (非空, 真实发生证据)
  - 无证据 → 存量进 baseline grace (warn), 新增 (非 baseline) → BLOCKING
  - 阻止 W11+ 及以后无证据 ADV 自动进入

baseline 模式 (照搬 check-work-landed M2):
  - 生成: python3 bin/gac/check-scenario-growth.py --dump-baseline > baseline-scenario-growth.txt
  - 存量无证据 ADV 进 grace, 新增无证据 → blocking
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = WORKSPACE / ".omo/_delivery/collab-scenarios"
BASELINE_FILE = WORKSPACE / ".omo/_truth/registry/baseline-scenario-growth.txt"
# T2: ADV 编号上限锁死 + detector 增长门 (防 W14 detector 形态绕过)
SCENARIO_LIB = WORKSPACE / "bin/collab/scenario_lib.py"
ADV_CAP = 185  # ABCD STOP freeze: stock max  # T2: 编号空间冻结, 新增须人类批准
DETECTOR_BASELINE_FILE = WORKSPACE / ".omo/_truth/registry/baseline-scenario-detectors.txt"


def _load_yaml(path: Path) -> dict:
    try:
        docs = list(yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader))
    except Exception as exc:  # K3: 不静默
        print(f"[warn] {path.name}: {exc}", file=sys.stderr)
        return {}
    for d in docs:
        if isinstance(d, dict) and "id" in d:
            return d
    return docs[-1] if docs and isinstance(docs[-1], dict) else {}


def _adv_files() -> list[Path]:
    if not SCENARIOS_DIR.is_dir():
        return []
    files = list(SCENARIOS_DIR.glob("ADV*.yaml")) + list(SCENARIOS_DIR.glob("GEN-ADV-*.yaml"))
    return sorted(set(files))


def _has_real_evidence(scenario: dict) -> bool:
    """real_occurrence_evidence 非空 (list/str, 非空)."""
    ev = scenario.get("real_occurrence_evidence")
    if not ev:
        return False
    if isinstance(ev, list):
        return len(ev) > 0
    return bool(str(ev).strip())


def _load_baseline() -> set[str]:
    if not BASELINE_FILE.is_file():
        return set()
    return {
        line.strip()
        for line in BASELINE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def _adv_number(path: Path) -> int | None:
    """从文件名解析 ADV 编号 (ADV25-xxx → 25)."""
    import re
    m = re.search(r"ADV(\d+)", path.name)
    return int(m.group(1)) if m else None


def _count_detectors() -> int:
    """数 scenario_lib.py 的 _synthesize_* / _handle_* 检测器函数 (T2 detector 门)."""
    if not SCENARIO_LIB.is_file():
        return 0
    import re
    txt = SCENARIO_LIB.read_text(encoding="utf-8")
    return len(re.findall(r"^def _(?:synthesize|handle)_\w+", txt, re.MULTILINE))


def _load_detector_baseline() -> int:
    """detector 基线数 (当前已落地, 新增 → blocking)."""
    if not DETECTOR_BASELINE_FILE.is_file():
        return 0
    try:
        return int(DETECTOR_BASELINE_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--dump-baseline",
        action="store_true",
        help="dump 当前无真实证据的 ADV id (baseline grace 清单)",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="override workspace root (tests / dry-run)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="baseline grace 也算 fail (CI 模式)",
    )
    args = parser.parse_args(argv)

    global WORKSPACE, SCENARIOS_DIR, BASELINE_FILE, SCENARIO_LIB, DETECTOR_BASELINE_FILE
    if args.workspace:
        WORKSPACE = Path(args.workspace).resolve()
        SCENARIOS_DIR = WORKSPACE / ".omo/_delivery/collab-scenarios"
        BASELINE_FILE = WORKSPACE / ".omo/_truth/registry/baseline-scenario-growth.txt"
        SCENARIO_LIB = WORKSPACE / "bin/collab/scenario_lib.py"
        DETECTOR_BASELINE_FILE = WORKSPACE / ".omo/_truth/registry/baseline-scenario-detectors.txt"

    advs = [(p, _load_yaml(p)) for p in _adv_files()]

    if args.dump_baseline:
        for p, sc in advs:
            if sc and not _has_real_evidence(sc):
                print(sc.get("id") or p.stem)
        return 0

    baseline = _load_baseline()
    findings: list[dict] = []
    summary = {"checked": 0, "passed": 0, "warn": 0, "blocking": 0}

    # T2: ADV 编号上限门 (锁死空间, >77 → blocking; W2: 存量超 cap 进 baseline grace)
    for p, sc in advs:
        n = _adv_number(p)
        if n is not None and n > ADV_CAP:
            aid = (sc or {}).get("id") or p.stem
            if aid in baseline:
                findings.append({
                    "id": p.name,
                    "kind": "adv_cap_grace",
                    "message": f"ADV 编号 {n} > 上限 {ADV_CAP} (baseline grace, 存量不追溯, W2)",
                })
                summary["warn"] += 1
            else:
                findings.append({
                    "id": p.name,
                    "kind": "adv_cap_exceeded",
                    "message": f"ADV 编号 {n} > 上限 {ADV_CAP} (T2 锁死: 新增须人类批准)",
                })
                summary["blocking"] += 1

    # T2: detector 增长门 (scenario_lib _synthesize_*/_handle_* 超 baseline → blocking)
    detector_n = _count_detectors()
    detector_baseline = _load_detector_baseline()
    if detector_baseline and detector_n > detector_baseline:
        findings.append({
            "id": f"scenario_lib detectors: {detector_n} > baseline {detector_baseline}",
            "kind": "detector_growth_blocking",
            "message": f"detector 数 {detector_n} 超 baseline {detector_baseline} (T2: W14 detector 形态也拦, 新增须人类派单)",
        })
        summary["blocking"] += 1

    for p, sc in advs:
        if not sc:
            continue
        summary["checked"] += 1
        aid = sc.get("id") or p.stem
        if _has_real_evidence(sc):
            summary["passed"] += 1
            continue
        # 无真实证据
        # W2 baseline 标准: 存量 grace 永远 warn (不阻断, 不论 strict), 新增 (非 baseline) blocking
        # (旧版 strict 把 baseline 也 blocking = 存量锁死新门, 违 W2 "按 baseline 标准处理存量")
        if aid in baseline:
            findings.append({
                "id": aid,
                "kind": "no_evidence_grace",
                "message": "无 real_occurrence_evidence (baseline grace, 存量不追溯)",
            })
            summary["warn"] += 1
        else:
            findings.append({
                "id": aid,
                "kind": "no_evidence_blocking",
                "message": "新增 ADV 无 real_occurrence_evidence (R2 门: 须真实发生证据才进, Q1 终止条件)",
            })
            summary["blocking"] += 1

    ok = summary["blocking"] == 0
    report = {"ok": ok, "summary": summary, "findings": findings}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-scenario-growth: {'PASS' if ok else 'FAIL'}")
        print(
            f"  checked={summary['checked']} passed={summary['passed']} "
            f"warn={summary['warn']} blocking={summary['blocking']}"
        )
        for f in findings:
            print(f"  - {f['id']} [{f['kind']}] {f.get('message', '')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
