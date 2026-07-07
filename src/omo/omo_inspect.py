"""omo inspect — 统一检查入口.

聚合以下检查为一站式审查:
1. lint schemas — schema 校验
2. validate completeness — .omo 目录完整性
3. validate references — 关键文件引用完整性
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from omo.omo_validate import validate_completeness, validate_references


def _check_schemas() -> dict:
    """检查 schema 注册表完整性."""
    from omo.omo_lint_schemas import cmd_lint_schemas

    try:
        rc = cmd_lint_schemas()
        if rc == 0:
            return {"id": "schemas", "status": "ok", "detail": "all schemas valid"}
        return {"id": "schemas", "status": "fail", "detail": "schema validation failed"}
    except Exception as e:
        return {"id": "schemas", "status": "error", "detail": str(e)}


def _check_completeness() -> dict:
    """检查 .omo 目录完整性."""
    result = validate_completeness()
    missing = result.get("missing", [])
    if missing:
        return {
            "id": "completeness",
            "status": "warn",
            "detail": f"{len(missing)} dirs missing: {', '.join(missing)}",
        }
    return {
        "id": "completeness",
        "status": "ok",
        "detail": f"{result['covered']}/{result['total_dirs']} dirs covered",
    }


def _check_references() -> dict:
    """检查关键文件引用完整性."""
    issues = validate_references()
    if issues:
        return {
            "id": "references",
            "status": "fail",
            "detail": f"{len(issues)} missing key files",
        }
    return {"id": "references", "status": "ok", "detail": "all key files present"}


def _check_god_module() -> dict:
    """检查 god module (文件过大)."""
    from omo.omo_lint_god_module import cmd_lint_god_module

    try:
        rc = cmd_lint_god_module()
        if rc == 0:
            return {
                "id": "god-module",
                "status": "ok",
                "detail": "no god modules detected",
            }
        return {"id": "god-module", "status": "warn", "detail": "god module detected"}
    except Exception as e:
        return {"id": "god-module", "status": "error", "detail": str(e)}


def cmd_inspect(json_output: bool = False) -> int:
    """运行统一检查."""
    checks = [
        _check_completeness,
        _check_references,
        _check_schemas,
        _check_god_module,
    ]

    results = []
    for check_fn in checks:
        try:
            results.append(check_fn())
        except Exception as e:
            results.append(
                {"id": check_fn.__name__, "status": "error", "detail": str(e)}
            )

    ok_count = sum(1 for r in results if r["status"] == "ok")
    warn_count = sum(1 for r in results if r["status"] == "warn")
    fail_count = sum(1 for r in results if r["status"] == "fail")
    error_count = sum(1 for r in results if r["status"] == "error")

    if json_output:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "checks": results,
                    "summary": {
                        "total": len(results),
                        "ok": ok_count,
                        "warn": warn_count,
                        "fail": fail_count,
                        "error": error_count,
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print("=== omo inspect ===\n")
        for r in results:
            icon = {"ok": "OK", "warn": "WARN", "fail": "FAIL", "error": "ERR"}.get(
                r["status"], "?"
            )
            print(f"  [{icon}] {r['id']}: {r['detail']}")
        print(
            f"\nSummary: {ok_count} ok, {warn_count} warn, {fail_count} fail, {error_count} error"
        )

    if fail_count > 0 or error_count > 0:
        return 1
    return 0
