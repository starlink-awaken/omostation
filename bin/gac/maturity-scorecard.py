#!/usr/bin/env python3
"""
maturity-scorecard.py — Calculate 6-dimension maturity score.

Usage:
  uv run --with pyyaml python3 bin/gac/maturity-scorecard.py
  uv run --with pyyaml python3 bin/gac/maturity-scorecard.py --json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: str, cwd=None, timeout=120) -> tuple[int, str, str]:
    if cwd is None:
        cwd = REPO_ROOT
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def score_evolvable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/ssot/script-registry.py validate 2>&1")
    combined = (out or err) or ""
    registered = "VALIDATION PASSED" in combined
    # 9 分档: registry 全量登记且无缺失/gap (validate 不报 missing/MISSING)
    no_gaps = registered and "missing" not in combined.lower() and "gap" not in combined.lower()
    score = 9 if no_gaps else (8 if registered else 6)
    if score == 9:
        evidence = "script registry validated with 0 gaps"
    elif score == 8:
        evidence = "script registry validated (has warnings/gaps)"
    else:
        evidence = "script registry has gaps"
    return {
        "dimension": "evolvable",
        "score": score,
        "evidence": evidence,
        "improvement": "Register all scripts and close registry gaps",
    }


def score_iterable() -> dict:
    design_doc = REPO_ROOT / "docs" / "operations" / "90pct-maturity-design.md"
    if not design_doc.exists():
        return {
            "dimension": "iterable",
            "score": 6,
            "evidence": "No phased plan found",
            "improvement": "Create 90pct-maturity-design.md",
        }
    text = design_doc.read_text()
    # 9 分档: 5 阶段路线图完整. 兼容 "Phase 1-2" 合并标记 (含 1 和 2),
    # 也接受独立 "Phase N" 标记.
    def phase_present(n: int) -> bool:
        # 匹配 "Phase N" 或 "Phase N-M" (N <= n <= M)
        return bool(
            re.search(rf"Phase {n}(?!\d)", text)
            or re.search(rf"Phase \d+-{n}\b", text)
        )
    has_all_phases = all(phase_present(i) for i in range(1, 6))
    return {
        "dimension": "iterable",
        "score": 9 if has_all_phases else 8,
        "evidence": "90pct-maturity-design.md exists with 5 phases" if has_all_phases else "90pct-maturity-design.md exists (phases incomplete)",
        "improvement": "Execute Phase 1-5 per design doc",
    }


def score_observable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/compass_radar.py 2>&1 | head -40")
    output = (out or "") or ""
    has_output = rc == 0 and len(output.strip()) > 0
    if not has_output:
        return {
            "dimension": "observable",
            "score": 7,
            "evidence": "compass_radar.py output unclear",
            "improvement": "Integrate new metrics into compass_radar.py",
        }
    # 9 分档: 雷达盘含 ≥6 个独立分布维度 (Priority/Risk/Owner/Phase/Status/...)
    axes = re.findall(r"Distribution:", output)
    has_six_axes = len(axes) >= 6
    return {
        "dimension": "observable",
        "score": 9 if has_six_axes else 8,
        "evidence": f"compass_radar.py radar with {len(axes)}+ axes" if has_six_axes else f"compass_radar.py produces output ({len(axes)} axes)",
        "improvement": "Expand compass_radar to 6+ axes",
    }


def score_traceable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/gac/adr-link-validator.py 2>&1")
    valid_links = rc == 0
    if not valid_links:
        return {
            "dimension": "traceable",
            "score": 6,
            "evidence": "Some ADR links broken",
            "improvement": "Fix broken ADR links",
        }
    # 9 分档: links valid 且 ADR 决策文档数 ≥ 30 (决策覆盖充足)
    adr_dir = REPO_ROOT / ".omo" / "_knowledge" / "decisions"
    adr_count = len(list(adr_dir.glob("*.md"))) if adr_dir.exists() else 0
    deep_coverage = adr_count >= 30
    return {
        "dimension": "traceable",
        "score": 9 if deep_coverage else 8,
        "evidence": f"All ADR links valid, {adr_count} decisions" if deep_coverage else "All ADR links valid",
        "improvement": "Add more ADR decisions",
    }


def score_troubleshootable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/ssot/governance-migration.py --dry-run 2>&1")
    combined = (out or err) or ""
    has_owner = "No changes needed" in combined
    if not has_owner:
        return {
            "dimension": "troubleshootable",
            "score": 6,
            "evidence": "Some checks missing owner fields",
            "improvement": "Complete owner field migration",
        }
    # 9 分档: owner + expected + remediation 全覆盖 (直接查 governance-checks.yaml)
    checks_yaml = REPO_ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    if not checks_yaml.exists():
        return {
            "dimension": "troubleshootable",
            "score": 8,
            "evidence": "All governance checks have owner fields",
            "improvement": "Complete owner field migration",
        }
    try:
        import yaml
        # governance-checks.yaml 是 multi-document. G4 迁移回填的 139 个条目在
        # gac.rules (X1-X4 + GaC 检查器), 另有 checkers/checks 别名兜底.
        checks: list = []
        for doc in yaml.safe_load_all(checks_yaml.read_text()):
            if not doc:
                continue
            if isinstance(doc, list):
                checks.extend(doc)
            elif isinstance(doc, dict):
                checks.extend(doc.get("gac", {}).get("rules", []))
                checks.extend(doc.get("checkers") or doc.get("checks") or [])
        total = len(checks)
        full = sum(
            1 for c in checks
            if c.get("owner") and c.get("expected") and c.get("remediation")
        )
        complete = total > 0 and full == total
    except Exception:
        complete = False
    return {
        "dimension": "troubleshootable",
        "score": 9 if complete else 8,
        "evidence": "All governance checks have owner/expected/remediation fields" if complete else "All governance checks have owner fields",
        "improvement": "Complete remediation field migration",
    }


def score_optimizable() -> dict:
    rc, out, err = run("uv run --with pyyaml python3 bin/gac/drift-sweep.py --json", timeout=60)
    if rc == 0:
        sweep_works = True
        score = 9
        evidence = "drift-sweep.py runs clean (0 failures)"
    elif rc == 1 and "timeout" in (out or err):
        sweep_works = False
        score = 5
        evidence = "drift-sweep.py timed out"
    else:
        sweep_works = True  # Tool works, just has findings
        score = 7
        evidence = "drift-sweep.py runs successfully (has findings)"
    return {
        "dimension": "optimizable",
        "score": score,
        "evidence": evidence,
        "improvement": "Resolve drift-sweep findings",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Maturity scorecard")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    dimensions = [
        score_evolvable(),
        score_iterable(),
        score_observable(),
        score_traceable(),
        score_troubleshootable(),
        score_optimizable(),
    ]

    overall = sum(d["score"] for d in dimensions) / len(dimensions)
    scores = {d["dimension"]: d["score"] for d in dimensions}

    if args.json:
        result = {
            "dimensions": dimensions,
            "overall": round(overall, 1),
            "scores": scores,
            "target": 9.0,
            "gap": round(9.0 - overall, 1),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    print("Architecture Maturity Scorecard")
    print("=" * 50)
    for d in dimensions:
        bar = "█" * d["score"] + "░" * (10 - d["score"])
        print(f"{d['dimension']:<15} [{bar}] {d['score']}/10")
        print(f"                 Evidence: {d['evidence']}")
        print(f"                 Next: {d['improvement']}")
        print()
    print("=" * 50)
    print(f"Overall: {overall:.1f}/10 (target: 9.0/10, gap: {9.0 - overall:.1f})")


if __name__ == "__main__":
    main()
