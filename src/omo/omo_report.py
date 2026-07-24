"""omo report — 综合报告生成.

聚合 doctor + inspect + audit 为一站式报告.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from omo.omo_doctor import cmd_doctor


def _run_doctor() -> dict:
    """运行 doctor 检查."""
    import io
    import sys

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        cmd_doctor(json_output=True)
        output = buffer.getvalue()
        return json.loads(output)
    except Exception as e:
        return {"error": str(e)}
    finally:
        sys.stdout = old_stdout


def _run_inspect() -> dict:
    """运行 inspect 检查."""

    from omo.omo_validate import validate_completeness, validate_references

    # Run individual checks directly instead of cmd_inspect
    # to avoid extra output from schema validation
    results = []

    # Completeness
    comp = validate_completeness()
    missing = comp.get("missing", [])
    if missing:
        results.append(
            {
                "id": "completeness",
                "status": "warn",
                "detail": f"{len(missing)} dirs missing",
            }
        )
    else:
        results.append(
            {
                "id": "completeness",
                "status": "ok",
                "detail": f"{comp['covered']}/{comp['total_dirs']} dirs covered",
            }
        )

    # References
    refs = validate_references()
    if refs:
        results.append(
            {
                "id": "references",
                "status": "fail",
                "detail": f"{len(refs)} missing key files",
            }
        )
    else:
        results.append(
            {"id": "references", "status": "ok", "detail": "all key files present"}
        )

    ok_count = sum(1 for r in results if r["status"] == "ok")
    warn_count = sum(1 for r in results if r["status"] == "warn")
    fail_count = sum(1 for r in results if r["status"] == "fail")

    return {
        "checks": results,
        "summary": {
            "total": len(results),
            "ok": ok_count,
            "warn": warn_count,
            "fail": fail_count,
            "error": 0,
        },
    }


def _run_audit_freshness() -> dict:
    """运行 audit freshness 检查."""
    from omo.omo_audit_freshness import (
        check_cross_project_lint,
        check_debt_evidence,
        check_mof_version_bump,
    )

    results = []
    for check_fn in [
        check_debt_evidence,
        check_cross_project_lint,
        check_mof_version_bump,
    ]:
        try:
            results.append(check_fn())
        except Exception as e:
            results.append(
                {"rule_id": check_fn.__name__, "status": "error", "details": str(e)}
            )

    ok_count = sum(1 for r in results if r.get("status") == "ok")
    warn_count = sum(1 for r in results if r.get("status") == "warning")
    error_count = sum(1 for r in results if r.get("status") == "error")

    return {
        "results": results,
        "summary": {
            "rules_total": len(results),
            "ok": ok_count,
            "warn": warn_count,
            "error": error_count,
        },
    }


def cmd_report(output: str | None = None, json_output: bool = False) -> int:
    """生成综合报告."""
    print("Generating omo report...\n")

    sections = []

    # 1. Doctor
    print("Running doctor...")
    doctor = _run_doctor()
    sections.append({"name": "doctor", "result": doctor})

    # 2. Inspect
    print("Running inspect...")
    inspect_result = _run_inspect()
    sections.append({"name": "inspect", "result": inspect_result})

    # 3. Audit freshness
    print("Running audit freshness...")
    freshness = _run_audit_freshness()
    sections.append({"name": "audit-freshness", "result": freshness})

    # Build report
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "sections": sections,
        "summary": {
            "total_sections": len(sections),
            "errors": sum(1 for s in sections if "error" in s.get("result", {})),
        },
    }

    if json_output:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("\n=== omo report ===\n")
        for section in sections:
            name = section["name"]
            result = section["result"]
            if "error" in result:
                print(f"  [ERR] {name}: {result['error']}")
            elif "summary" in result:
                summary = result["summary"]
                ok = summary.get("ok", 0)
                warn = summary.get("warn", 0)
                fail = summary.get("fail", 0)
                print(f"  [OK] {name}: {ok} ok, {warn} warn, {fail} fail")
            else:
                print(f"  [OK] {name}: completed")

        print(
            f"\nSummary: {report['summary']['total_sections']} sections, {report['summary']['errors']} errors"
        )

    if output:
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if not json_output:
            print(f"\nReport written to {out_path}")

    return 0
