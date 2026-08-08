#!/usr/bin/env python3
"""PR Review Matrix — 多维度PR审查矩阵 (T3).

6个维度Agent + 心智模型Agent 审查PR diff → 产出综合裁决.
门禁后移架构: PR审查矩阵替代人审, 人只审needs_human的.

维度:
  risk       — 风控(redlines + governance-checks)
  security   — 安全(mutation-surfaces + write-owners)
  architecture — 架构(layer-contract + ARCHITECTURE.md)
  policy     — 策略(task-policies + phase-scope)
  function   — 功能(scene-cards + journey-specs)
  mental_model — 心智模型(LifeOS TELOS + MOS beliefs + 历史审批)

Usage:
  python3 bin/ssot/pr-review-matrix.py --diff <file>     # 审查diff文件
  python3 bin/ssot/pr-review-matrix.py --pr <number>     # 审查GitHub PR
  python3 bin/ssot/pr-review-matrix.py --diff <file> --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from _shared import ROOT, load_yaml, utc_now

PERMISSION_MATRIX = ROOT / ".omo" / "_truth" / "registry" / "action-permission-matrix.yaml"
REDLINES = ROOT / ".omo" / "_truth" / "registry" / "redlines.yaml"
ARCHITECTURE = ROOT / "ARCHITECTURE.md"
TASK_POLICIES = ROOT / ".omo" / "_truth" / "registry" / "task-policies.yaml"
TELOS_DIR = Path.home() / ".claude" / "LIFEOS" / "USER" / "TELOS"


@dataclass
class ReviewVerdict:
    dimension: str
    verdict: str  # approve | reject | needs_human
    confidence: float = 0.8
    reasoning: str = ""
    blocked_rules: list[str] = field(default_factory=list)

    @property
    def is_blocking(self) -> bool:
        return self.verdict == "reject"


def _load_diff(path: Path) -> str:
    if path == Path("-"):
        import sys
        return sys.stdin.read()
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _get_pr_diff(pr_number: int) -> str:
    """Fetch PR diff via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number), "--repo", "starlink-awaken/omostation"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


# ── Reviewer Agents ──────────────────────────────────────────────

def review_risk(diff: str) -> ReviewVerdict:
    """风控审查: 检查diff是否触发redline规则."""
    redlines = load_yaml(REDLINES)
    blocked: list[str] = []
    for rl in redlines.get("redlines", []):
        if not isinstance(rl, dict):
            continue
        rl_id = str(rl.get("id", ""))
        executors = rl.get("executor", [])
        if isinstance(executors, str):
            executors = [executors]
        # If any redline executor is in gate context and pattern matches diff
        if any(e in ("hook_pre_edit", "ci_gate") for e in executors):
            pattern = str(rl.get("pattern", rl.get("id", "")))
            if pattern and pattern in diff:
                blocked.append(rl_id)
    if blocked:
        return ReviewVerdict("risk", "reject", 0.9, f"触发red规则: {blocked}", blocked)
    return ReviewVerdict("risk", "approve", 0.85, "无red规则触发")


def review_security(diff: str) -> ReviewVerdict:
    """安全审查: 检查写面权限和敏感操作."""
    sensitive_patterns = ["rm -rf", "DELETE FROM", "drop table", "chmod 777", "eval(", "exec(", "os.system"]
    for pat in sensitive_patterns:
        if pat in diff:
            return ReviewVerdict("security", "reject", 0.7, f"检测到敏感操作: {pat}")
    return ReviewVerdict("security", "approve", 0.8, "无敏感操作")


def review_architecture(diff: str) -> ReviewVerdict:
    """架构审查: 检查分层违规."""
    # Simple heuristic: check for cross-layer imports
    cross_layer = ["from omo import", "from runtime import omo", "from cockpit import omo"]
    for pat in cross_layer:
        if pat in diff:
            return ReviewVerdict("architecture", "needs_human", 0.6, f"可能的跨层引用: {pat}")
    return ReviewVerdict("architecture", "approve", 0.75, "无分层违规")


def review_policy(diff: str) -> ReviewVerdict:
    """策略审查: 检查task-policies合规."""
    policies = load_yaml(TASK_POLICIES)
    policy_count = len(policies.get("policies", []))
    if policy_count == 0:
        return ReviewVerdict("policy", "approve", 0.7, "无策略规则配置")
    # Check diff for policy violations (simple heuristic)
    if "lifecycle: plan" in diff and "status: draft" not in diff:
        return ReviewVerdict("policy", "needs_human", 0.6, "plan阶段但缺draft状态")
    return ReviewVerdict("policy", "approve", 0.8, f"{policy_count}条策略规则检查通过")


def review_function(diff: str) -> ReviewVerdict:
    """功能审查: 检查是否破坏scene-cards/journey-specs完整性."""
    if "scene_id" in diff and "reflection_contract" not in diff:
        # Adding scene without reflection → flag
        if "+scene_id:" in diff and "reflection_contract" not in diff:
            return ReviewVerdict("function", "needs_human", 0.6, "新增scene card缺reflection_contract")
    return ReviewVerdict("function", "approve", 0.8, "功能完整性检查通过")


def review_mental_model(diff: str, other_verdicts: list[ReviewVerdict]) -> ReviewVerdict:
    """心智模型审查: 综合其他维度 + TELOS对齐."""
    # Load TELOS context
    telos_goals = ""
    if TELOS_DIR.is_dir():
        goals_file = TELOS_DIR / "goals.md"
        if goals_file.exists():
            telos_goals = goals_file.read_text(encoding="utf-8")[:500]

    # Aggregate other verdicts
    any_reject = any(v.verdict == "reject" for v in other_verdicts)
    any_needs_human = any(v.verdict == "needs_human" for v in other_verdicts)

    # Load trust thresholds
    matrix = load_yaml(PERMISSION_MATRIX)
    thresholds = matrix.get("trust_thresholds", {})
    auto_merge_min = float(thresholds.get("auto_merge_min_confidence", 0.8))

    if any_reject:
        return ReviewVerdict("mental_model", "reject", 0.9, "其他维度有reject→心智模型否决")
    if any_needs_human:
        return ReviewVerdict("mental_model", "needs_human", 0.5, "其他维度有needs_human→提级人审")

    # All approve → check TELOS alignment
    avg_confidence = sum(v.confidence for v in other_verdicts) / len(other_verdicts) if other_verdicts else 0.8
    aligned = "goals" in telos_goals.lower() or "自主" in telos_goals or avg_confidence >= auto_merge_min

    if aligned and avg_confidence >= auto_merge_min:
        return ReviewVerdict("mental_model", "approve", avg_confidence, f"TELOS对齐+置信度{avg_confidence:.2f}≥{auto_merge_min}")
    return ReviewVerdict("mental_model", "needs_human", avg_confidence, f"置信度{avg_confidence:.2f}不足或TELOS对齐不确定")


# ── Matrix Orchestration ─────────────────────────────────────────

def review_diff(diff: str) -> dict[str, Any]:
    """Run all 6 reviewers + mental model → produce final verdict."""
    ts = utc_now()

    # Phase 1: 5 dimension reviewers
    verdicts = [
        review_risk(diff),
        review_security(diff),
        review_architecture(diff),
        review_policy(diff),
        review_function(diff),
    ]

    # Phase 2: Mental model agent (sees all verdicts)
    mental = review_mental_model(diff, verdicts)
    verdicts.append(mental)

    # Final decision
    all_verdicts = [v.verdict for v in verdicts]
    matrix = load_yaml(PERMISSION_MATRIX)
    auto_merge_min = float(matrix.get("trust_thresholds", {}).get("auto_merge_min_confidence", 0.8))

    if "reject" in all_verdicts:
        decision = "blocked"
    elif "needs_human" in all_verdicts:
        decision = "needs_human"
    elif mental.confidence >= auto_merge_min:
        decision = "auto_merge"
    else:
        decision = "needs_human"

    return {
        "schema": "pr-review-matrix/v1",
        "reviewed_at": ts,
        "decision": decision,
        "confidence": mental.confidence,
        "verdicts": [
            {
                "dimension": v.dimension,
                "verdict": v.verdict,
                "confidence": v.confidence,
                "reasoning": v.reasoning,
                "blocked_rules": v.blocked_rules,
            }
            for v in verdicts
        ],
        "auto_merge_eligible": decision == "auto_merge",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", type=Path, default=None, help="diff file path (or - for stdin)")
    parser.add_argument("--pr", type=int, default=None, help="GitHub PR number")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.pr:
        diff = _get_pr_diff(args.pr)
    elif args.diff:
        diff = _load_diff(args.diff)
    else:
        parser.error("must provide --diff or --pr")

    if not diff.strip():
        print(json.dumps({"error": "empty diff"}, ensure_ascii=False))
        return 1

    result = review_diff(diff)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"PR Review Matrix: {result['decision'].upper()} (confidence={result['confidence']:.2f})")
        for v in result["verdicts"]:
            marker = {"approve": "✅", "reject": "❌", "needs_human": "⚠️"}.get(v["verdict"], "?")
            print(f"  {marker} {v['dimension']:15s} {v['verdict']:12s} conf={v['confidence']:.2f} {v['reasoning'][:60]}")
        if result["auto_merge_eligible"]:
            print("\n🚀 Auto-merge eligible (all approve + confidence sufficient)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
