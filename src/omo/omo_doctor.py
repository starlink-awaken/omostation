"""omo doctor — 统一健康检查入口.

聚合以下检查为一站式诊断:
1. health check — agora 服务探活
2. validate state — .omo 状态一致性
3. audit freshness — X2 freshness 巡检
4. path-acl — Scheme C 5c L1 world-writable 巡检 (ADR-0199, warn-only)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from omo.omo_paths import OMO_ROOT, WORKSPACE_ROOT


def _check_state_freshness() -> dict:
    """检查 system.yaml 是否 stale."""
    system_yaml = OMO_ROOT / "state" / "system.yaml"
    if not system_yaml.exists():
        return {
            "id": "state-freshness",
            "status": "warn",
            "detail": "system.yaml missing",
        }
    import time

    mtime = system_yaml.stat().st_mtime
    age_hours = (time.time() - mtime) / 3600
    if age_hours > 24:
        return {
            "id": "state-freshness",
            "status": "warn",
            "detail": f"system.yaml is {age_hours:.1f}h old (>24h)",
        }
    return {
        "id": "state-freshness",
        "status": "ok",
        "detail": f"system.yaml age: {age_hours:.1f}h",
    }


def _check_key_files() -> dict:
    """检查关键文件是否存在."""
    key_files = [
        "state/system.yaml",
        "state/health.yaml",
        "goals/current.yaml",
        "_truth/INDEX.md",
        "_truth/registry/mof-capabilities.yaml",
        "standards/omo-governance-surfaces.md",
    ]
    missing = []
    for f in key_files:
        if not (OMO_ROOT / f).exists():
            missing.append(f)
    if missing:
        return {
            "id": "key-files",
            "status": "fail",
            "detail": f"missing: {', '.join(missing)}",
        }
    return {
        "id": "key-files",
        "status": "ok",
        "detail": f"{len(key_files)} key files present",
    }


def _check_agora_health() -> dict:
    """检查 agora 服务健康 (简化版, 不做 HTTP 探活)."""
    agora_routes = OMO_ROOT.parent / "projects" / "agora" / "src" / "agora-routes.json"
    if not agora_routes.exists():
        return {
            "id": "agora-health",
            "status": "warn",
            "detail": "agora-routes.json not found",
        }
    return {"id": "agora-health", "status": "ok", "detail": "agora-routes.json present"}


def _check_debt_staleness() -> dict:
    """检查 debt items 是否有 stale 的."""
    from omo.omo_audit_freshness import check_debt_evidence

    result = check_debt_evidence()
    return {
        "id": "debt-evidence",
        "status": "ok" if result["status"] == "ok" else "warn",
        "detail": f"{result['stale']}/{result['total']} stale debt items",
    }


def _check_path_acl() -> dict:
    """Scheme C 5c L1: world-writable / 0777 on governed write plane (warn-only).

    Never mutates host. Daily doctor rhythm surface (ADR-0199).
    """
    from omo.omo_path_acl import run_path_acl_doctor

    # Prefer workspace root that contains .omo (OMO_ROOT parent)
    root = Path(WORKSPACE_ROOT)
    if not (root / ".omo").exists() and OMO_ROOT.exists():
        root = OMO_ROOT.parent

    report = run_path_acl_doctor(root, strict=False)
    warn_findings = [
        f
        for f in (report.get("findings") or [])
        if f.get("kind") in ("world_writable", "mode_777")
        or f.get("severity") in ("warn", "halt")
    ]
    # ignore pure info "ok" / missing_optional
    actionable = [
        f
        for f in warn_findings
        if f.get("kind") in ("world_writable", "mode_777", "stat_error")
    ]
    if not actionable:
        return {
            "id": "path-acl",
            "status": "ok",
            "detail": (
                f"surfaces={report.get('surface_count', 0)} "
                f"no world-writable/0777 (strict={report.get('strict')})"
            ),
            "meta": {
                "warn_count": report.get("warn_count", 0),
                "workspace_root": report.get("workspace_root"),
            },
        }

    paths = ", ".join(f"{f.get('path')}({f.get('kind')})" for f in actionable[:5])
    more = len(actionable) - 5
    detail = f"{len(actionable)} ACL red flag(s): {paths}"
    if more > 0:
        detail += f" +{more} more"
    detail += " · fix: omo acl plan --json"
    return {
        "id": "path-acl",
        "status": "warn",
        "detail": detail,
        "meta": {
            "actionable": actionable,
            "workspace_root": report.get("workspace_root"),
        },
    }


def cmd_doctor(json_output: bool = False) -> int:
    """运行统一健康检查."""
    checks = [
        _check_state_freshness,
        _check_key_files,
        _check_agora_health,
        _check_debt_staleness,
        _check_path_acl,
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
        import json

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
        print("=== omo doctor ===\n")
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
    if warn_count > 0:
        return 0  # warnings are non-blocking
    return 0
