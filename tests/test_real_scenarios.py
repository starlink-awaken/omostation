#!/usr/bin/env python3
"""Real Scenario Test — 真实场景验证."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def run_cmd(cmd: list[str]) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        return {"ok": result.returncode == 0, "stdout": result.stdout.strip()[:300], "stderr": result.stderr.strip()[:100]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def scenario_document_review() -> dict:
    """场景: 公文审查."""
    print("\n=== 场景: 公文审查 ===")
    results = {"scenario": "document-review", "steps": []}

    doc_content = "关于进一步加强网络安全工作的通知\n各部门：\n1.提高安全意识\n2.完善防护措施"
    fd, doc_path = tempfile.mkstemp(suffix=".md")
    doc_file = Path(doc_path)
    doc_file.write_text(doc_content, encoding="utf-8")
    os.close(fd)
    results["steps"].append({"name": "create_document", "ok": True})

    r = run_cmd(["python3", str(REPO / "bin/gac/signal-scene-connector.py"), "--scene", "document-review"])
    results["steps"].append({"name": "trigger_scene", **r})

    r = run_cmd(["python3", str(REPO / "bin/gac/value-tracker.py"), "--record", "20", "--task", "doc-review"])
    results["steps"].append({"name": "record_value", **r})

    doc_file.unlink(missing_ok=True)
    results["passed"] = sum(1 for s in results["steps"] if s.get("ok"))
    results["total"] = len(results["steps"])
    return results


def scenario_meeting_minutes() -> dict:
    """场景: 会议纪要."""
    print("\n=== 场景: 会议纪要 ===")
    results = {"scenario": "meeting-minutes", "steps": []}

    r = run_cmd(["python3", str(REPO / "bin/gac/signal-scene-connector.py"), "--scene", "meeting-supervision"])
    results["steps"].append({"name": "trigger_scene", **r})

    r = run_cmd(["python3", str(REPO / "bin/gac/value-tracker.py"), "--record", "45", "--task", "meeting-minutes"])
    results["steps"].append({"name": "record_value", **r})

    results["passed"] = sum(1 for s in results["steps"] if s.get("ok"))
    results["total"] = len(results["steps"])
    return results


def scenario_research_digest() -> dict:
    """场景: 研究资料."""
    print("\n=== 场景: 研究资料 ===")
    results = {"scenario": "research-digest", "steps": []}

    r = run_cmd(["python3", str(REPO / "bin/gac/signal-scene-connector.py"), "--scene", "research-pipeline"])
    results["steps"].append({"name": "trigger_scene", **r})

    r = run_cmd(["python3", str(REPO / "bin/gac/value-tracker.py"), "--record", "60", "--task", "research-digest"])
    results["steps"].append({"name": "record_value", **r})

    results["passed"] = sum(1 for s in results["steps"] if s.get("ok"))
    results["total"] = len(results["steps"])
    return results


def run_all_scenarios() -> dict:
    print("=" * 50)
    print("真实场景验证")
    print("=" * 50)

    scenarios = [scenario_document_review, scenario_meeting_minutes, scenario_research_digest]
    all_results = []
    for func in scenarios:
        result = func()
        all_results.append(result)
        print(f"  {result['scenario']}: {result['passed']}/{result['total']}")

    total_passed = sum(r["passed"] for r in all_results)
    total_steps = sum(r["total"] for r in all_results)
    rate = round(total_passed / total_steps * 100, 1) if total_steps else 0
    print(f"\n总体: {rate}% ({total_passed}/{total_steps})")

    return {"success_rate": rate, "scenarios": all_results}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Real Scenario Test")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scenario", choices=["document-review", "meeting-minutes", "research-digest"])
    args = parser.parse_args()

    if args.all:
        result = run_all_scenarios()
        return 0 if result["success_rate"] >= 70 else 1

    if args.scenario:
        m = {"document-review": scenario_document_review, "meeting-minutes": scenario_meeting_minutes, "research-digest": scenario_research_digest}
        result = m[args.scenario]()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
