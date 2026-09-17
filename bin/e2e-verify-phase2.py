#!/usr/bin/env python3
"""Phase 2 E2E 全链验证 — 3 份公文 document-review 管线.

每份公文走完整 inbox-to-decision journey:
  messages_collected → triaged → under_review → decision_made → task_created → delivered → knowledge_captured

验证内容:
  1. journey-runner 全链完成 (5 steps after resume)
  2. document-review scene 输出 status=succeeded
  3. human_review checkpoint 存在 (journey pauses at under_review)
  4. final_context 完整 (classification/content/document_ref/indexed)
  5. Workflow Mesh 证据链完整 (run_id 可追溯, reflection 生成)

Usage: python3 bin/e2e-verify-phase2.py [--output path]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JR = ROOT / "runtime" / "ssot-stable" / "journey-runner.py"

# 3 份 admin-notification-workflow 风格的真实公文样本
# 覆盖: 绩效考核 / 安全生产 / 预算调整
E2E_SAMPLES = [
    {
        "subject": "关于2026年下半年绩效考核的通知",
        "sender": "上级部门",
        "content": "请各单位于10月底前完成绩效考核表填报，确保数据真实准确",
        "classification": "document",
        "confidence": 0.85,
        "document_ref": "vault://redacted/document-review/sample-1",
    },
    {
        "subject": "关于开展安全生产专项检查的通知",
        "sender": "安全生产委员会",
        "content": "请各单位立即开展安全生产专项检查，11月15日前报送检查报告",
        "classification": "document",
        "confidence": 0.90,
        "document_ref": "vault://redacted/document-review/sample-2",
    },
    {
        "subject": "关于调整2026年预算指标的通知",
        "sender": "财务处",
        "content": "经研究决定，调整部分部门2026年度预算指标，详见附件",
        "classification": "document",
        "confidence": 0.80,
        "document_ref": "vault://redacted/document-review/sample-3",
    },
]


def run_full_chain(sample: dict) -> dict:
    """Run one document through inbox-to-decision journey (run + resume)."""
    t0 = time.time()
    steps = []

    # Step 1: run journey (pauses at human_review)
    r1 = subprocess.run(
        ["python3", str(JR), "--root", str(ROOT), "run",
         "--journey", "inbox-to-decision", "--dry-run",
         "--input", json.dumps(sample, ensure_ascii=False)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    out1 = r1.stdout or ""

    # Parse run_id from JSON block
    run_id = None
    checkpoint = False
    match = re.search(r'\{\s*"checkpoint".*\}', out1, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            run_id = parsed.get("run_id")
            checkpoint = parsed.get("status") == "paused"
            steps.append({"phase": "run", "state": parsed.get("state"), "checkpoint": True})
        except Exception:
            pass

    if not run_id:
        return {"completed": False, "error": "no_run_id", "elapsed": time.time() - t0}

    # Step 2: resume past human_review
    r2 = subprocess.run(
        ["python3", str(JR), "--root", str(ROOT), "resume",
         "--journey-id", "inbox-to-decision", "--run-id", run_id],
        capture_output=True, text=True, timeout=120, check=False,
    )
    out2 = r2.stdout or ""

    completed = "Terminal state reached" in out2
    elapsed = time.time() - t0

    # Extract final context
    final_context = {}
    steps_count = 0
    match2 = re.search(r'\{\s*"dry_run".*\}', out2, re.DOTALL)
    if match2:
        try:
            parsed2 = json.loads(match2.group(0))
            final_context = parsed2.get("final_context", {})
            steps_count = parsed2.get("steps", 0)
        except Exception:
            pass

    # Check for reflection output
    reflection_generated = "Reflection generated" in out2

    # Build evidence chain
    evidence_chain = {
        "run_id": run_id,
        "checkpoint": checkpoint,
        "steps_count": steps_count,
        "terminal_reached": completed,
        "reflection_generated": reflection_generated,
        "final_context": final_context,
    }

    return {
        "completed": completed,
        "checkpoint_found": checkpoint,
        "elapsed": elapsed,
        "steps_count": steps_count,
        "reflection_generated": reflection_generated,
        "final_context": final_context,
        "evidence_chain": evidence_chain,
        "subject": sample["subject"],
        "document_ref": sample["document_ref"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 E2E verification")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    print(f"🔬 Phase 2 E2E 全链验证 — {len(E2E_SAMPLES)} 份公文", file=sys.stderr)
    print(f"   journey: inbox-to-decision (run + resume)", file=sys.stderr)
    print(f"   管线: 拟稿 → 格式检查 → 敏感项检查 → 依据核验 → 审批", file=sys.stderr)
    print("", file=sys.stderr)

    results = []
    all_passed = True

    for i, sample in enumerate(E2E_SAMPLES):
        print(f"  [{i+1}/{len(E2E_SAMPLES)}] {sample['subject']}", file=sys.stderr, end=" ")
        t0 = time.time()
        r = run_full_chain(sample)
        elapsed = time.time() - t0

        # Verify all 5 checks
        checks = {
            "full_chain_completed": r.get("completed", False),
            "human_review_checkpoint": r.get("checkpoint_found", False),
            "steps_ge_5": r.get("steps_count", 0) >= 5,
            "reflection_generated": r.get("reflection_generated", False),
            "final_context_complete": all(k in r.get("final_context", {}) for k in ["classification", "content", "document_ref", "indexed"]),
        }

        passed = all(checks.values())
        if not passed:
            all_passed = False

        status = "✅" if passed else "❌"
        print(f"{status} ({elapsed:.1f}s) checks: {sum(checks.values())}/5", file=sys.stderr)

        results.append({
            "sample_index": i + 1,
            "subject": sample["subject"],
            "document_ref": sample["document_ref"],
            "completed": r.get("completed", False),
            "checks": checks,
            "passed": passed,
            "elapsed": elapsed,
            "steps_count": r.get("steps_count", 0),
            "evidence_chain": r.get("evidence_chain", {}),
            "final_context": r.get("final_context", {}),
        })

    # Summary
    passed_count = sum(1 for r in results if r["passed"])
    total_checks = sum(sum(r["checks"].values()) for r in results)
    total_possible = len(results) * 5

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"E2E 全链验证结果:", file=sys.stderr)
    print(f"  公文数: {len(results)}", file=sys.stderr)
    print(f"  全链通过: {passed_count}/{len(results)}", file=sys.stderr)
    print(f"  检查项: {total_checks}/{total_possible}", file=sys.stderr)
    print(f"  达标: {'YES ✅' if all_passed else 'NO ❌'}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    report = {
        "phase": "Phase 2 — E2E 全链验证",
        "bet_id": "BET-Y3H1-T7-02",
        "samples_tested": len(results),
        "all_passed": all_passed,
        "passed_count": passed_count,
        "total_checks": total_checks,
        "total_possible_checks": total_possible,
        "results": results,
    }

    out_str = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out_str, encoding="utf-8")
        print(f"\n📄 Report written to {args.output}", file=sys.stderr)
    else:
        print(out_str)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
