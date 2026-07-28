"""System map API — router, top-level builders and routes.

Helper layers live in api_system_map_catalog / _io_commands / _status (god-module SRP split).
Public API (build_system_map, build_source_ref_preview, _project_* status fns) re-exported here.
"""

from __future__ import annotations

import json
import re
import socket
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query

from cockpit import compat

router = APIRouter()

SYSTEM_MAP_SOURCE = Path(__file__).resolve()
CATALOG_SOURCE = SYSTEM_MAP_SOURCE.parent / "api_system_map_catalog.py"

from cockpit.web.api_system_map_catalog import (
    CAPABILITY_TO_PAGE,
    CLI_ENTRYPOINTS,
    COCKPIT_PAGES,
    NEXT_CONFIGS,
    OPERATING_PLAYBOOKS,
    PACKAGE_MANIFESTS,
    PAGE_CAPABILITY_LINKS,
    PAGE_OPERATOR_ACTION_METADATA,
    PAGE_OPERATOR_ACTIONS,
    PAGE_PROJECT_LINKS,
    PROJECT_COVERAGE_DIMENSIONS,
    PROJECT_DOC_FILES,
    PROJECT_PORT_ALIASES,
    PROJECT_TO_PAGE,
    ROADMAP_ITEMS,
    SERVICE_ENTRYPOINTS,
    STATIC_FRONTEND_MARKERS,
    USAGE_PATHS,
    VITE_CONFIGS,
)
from cockpit.web.api_system_map_io_commands import (
    MAX_SOURCE_PREVIEW_BYTES,
    _command_with_cwd,
    _exists_any,
    _first_action,
    _first_matching_command,
    _is_port_listening,
    _line_number,
    _package_scripts,
    _parse_source_ref_target,
    _path_state,
    _port_probe_command,
    _port_registry_search_command,
    _project_actions,
    _project_inventory_command,
    _project_ports,
    _project_start_command,
    _project_triage_commands,
    _project_verify_command,
    _read_json,
    _read_text,
    _read_text_lossy,
    _read_yaml,
    _recover_port_registry,
    _source_ref,
    _source_ref_for_id,
    _triage_command,
    _triage_task_posture,
    _workflow_evidence_search_command,
    build_source_ref_preview,
)
from cockpit.web.api_system_map_status import (
    _build_layers,
    _commands_from_agents,
    _coverage_check,
    _latest_controlled_verification,
    _latest_project_verification,
    _parse_capability_domains,
    _parse_markdown_rows,
    _project_coverage_checks,
    _project_diagnostics,
    _project_operational_status,
    _project_path,
    _project_portfolio_state,
    _project_runtime_status,
    _project_source_location,
    _project_source_refs,
    _project_workflow_lifecycle,
    _read_package_manifest,
    _resolved_physical_location,
    _runtime_profile,
)
from cockpit.web.router_health import router_health_snapshot


def _build_projects(
    registry: dict[str, Any], port_registry: dict[str, Any], registry_path: Path, port_registry_path: Path
) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for project_id, project_data in (registry.get("projects") or {}).items():
        if not isinstance(project_data, dict):
            continue
        page_id = PROJECT_TO_PAGE.get(project_id, "SystemMap")
        project_path = _project_path(project_id, project_data)
        operational = _project_operational_status(project_id, project_data, project_path)
        runtime = _project_runtime_status(project_id, project_data, operational, port_registry, port_registry_path)
        project = {
            "id": project_id,
            "layer": project_data.get("layer", "unknown"),
            "stack": project_data.get("stack", "unknown"),
            "role": project_data.get("role", ""),
            "cockpit_page": page_id,
            "coverage": "native" if page_id != "SystemMap" or project_id.startswith("cockpit") else "orientation",
            "path": str(project_path),
            "source_location": str(_project_source_location({**project_data, "id": project_id}) or project_path),
            "exists": project_path.exists(),
            "operational": operational,
            "runtime": runtime,
            "workflow": _project_workflow_lifecycle(project_id),
            "source_refs": _project_source_refs(project_id, project_path, registry_path, runtime["ports"]),
            "actions": _project_actions(project_id, project_path, page_id, operational),
        }
        project["triage_commands"] = _project_triage_commands(project)
        project["coverage_checks"] = _project_coverage_checks(project)
        project["diagnostics"] = _project_diagnostics(project)
        project["portfolio"] = _project_portfolio_state(project)
        projects.append(project)
    return projects


def _build_domain_apps_summary() -> dict[str, Any]:
    try:
        from cockpit.web.api_domain_apps import build_domain_apps

        payload = build_domain_apps()
    except Exception:
        return {
            "status": "unavailable",
            "strategy": "Cockpit is the L3 entry; L4 domains keep SSOT and vertical app ownership.",
            "summary": {
                "total": 0,
                "ready": 0,
                "needs_attention": 0,
                "running": 0,
                "stopped": 0,
                "high_risk": 0,
                "external_mounts": 0,
                "security_passed": 0,
                "security_warn": 0,
                "security_failed": 1,
                "security_blocking": 1,
                "security_attention_apps": 1,
                "score": 0,
                "security_posture": "blocked",
            },
            "items": [],
            "attention_items": [
                {
                    "id": "domain-apps-api",
                    "name": "Domain Apps API",
                    "health": "unavailable",
                    "runtime_status": "unknown",
                    "risk_level": "high",
                    "security_posture": "blocked",
                    "next_action": "修复 /api/domain-apps 后再判断领域写入能力是否可挂载。",
                }
            ],
            "next_action": "修复 /api/domain-apps 后再判断领域写入能力是否可挂载。",
        }

    summary = payload.get("summary", {})
    items = []
    for item in payload.get("items", []):
        security_summary = item.get("security_summary", {})
        capabilities = item.get("capabilities", {})
        runtime = item.get("runtime", {})
        items.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "domain": item.get("domain"),
                "kind": item.get("kind"),
                "integration_mode": item.get("integration_mode"),
                "risk_level": item.get("risk_level"),
                "health": item.get("health"),
                "runtime_status": runtime.get("status", "unknown"),
                "launch_url": (item.get("links") or {}).get("launch_url"),
                "api_url": (item.get("links") or {}).get("api_url"),
                "security_posture": security_summary.get("posture", "unknown"),
                "security_attention": int(security_summary.get("attention") or 0),
                "security_failed": int(security_summary.get("failed") or 0),
                "read_capabilities": capabilities.get("read", []),
                "write_capabilities": capabilities.get("write", []),
                "action_count": len(item.get("actions") or []),
                "next_action": _domain_app_next_action(item),
            }
        )

    total = int(summary.get("total") or 0)
    ready = int(summary.get("ready") or 0)
    running = int(summary.get("running") or 0)
    attention_apps = int(summary.get("security_attention_apps") or 0)
    failed = int(summary.get("security_failed") or 0)
    warn = int(summary.get("security_warn") or 0)
    health_score = (ready / total) * 40 if total else 0
    runtime_score = (running / total) * 20 if total else 0
    security_score = ((total - attention_apps) / total) * 30 if total else 0
    mount_score = 10 if total else 0
    score = round(health_score + runtime_score + security_score + mount_score)
    status = "blocked" if failed else "attention" if warn or attention_apps else "watch" if running < total else "ready"
    attention_items = [
        item
        for item in items
        if item["health"] != "ready" or item["runtime_status"] == "stopped" or item["security_posture"] != "passed"
    ]
    enriched_summary = {
        **summary,
        "score": score,
        "security_posture": "blocked" if failed else "attention" if warn or attention_apps else "passed",
    }
    next_action = "保持领域应用健康、安全门和启动命令新鲜。"
    if status == "blocked":
        next_action = "先修复领域应用安全失败项，再开放写入或反向代理能力。"
    elif status == "attention":
        next_action = "处理领域应用安全警告和健康提醒，避免 Cockpit 挂载不可信能力。"
    elif status == "watch":
        next_action = "启动或验证停止的领域服务，让应用中心从入口变成日用能力。"

    return {
        "status": status,
        "strategy": payload.get("strategy", ""),
        "summary": enriched_summary,
        "items": items,
        "attention_items": attention_items[:5],
        "next_action": next_action,
    }


def _domain_app_next_action(item: dict[str, Any]) -> str:
    security_summary = item.get("security_summary", {})
    if int(security_summary.get("failed") or 0):
        return "修复失败的安全检查后再开放写入或自动化动作。"
    if int(security_summary.get("warn") or 0):
        return "清理安全警告，让领域应用进入可挂载状态。"
    if item.get("health") != "ready":
        return "补齐应用根、SSOT 或构建数据，让健康状态回到 ready。"
    if (item.get("runtime") or {}).get("status") == "stopped":
        return "按登记启动命令拉起服务或确认它只需要按需启动。"
    return "保持 SSOT、验证命令和安全门证据新鲜。"


def _domain_app_security_gap(domain_apps: dict[str, Any]) -> dict[str, str] | None:
    summary = domain_apps.get("summary", {})
    failed = int(summary.get("security_failed") or 0)
    warn = int(summary.get("security_warn") or 0)
    if domain_apps.get("status") == "unavailable":
        return {
            "id": "domain-app-write-gates",
            "severity": "medium",
            "title": "领域应用安全门状态不可读",
            "evidence": "SystemMap 无法读取 DomainApps 安全矩阵。",
            "next": "修复 /api/domain-apps 后再判断领域写入能力是否可挂载。",
        }
    if failed == 0 and warn == 0:
        return None

    attention_apps = [item["id"] for item in domain_apps.get("items", []) if item.get("security_posture") != "passed"]
    return {
        "id": "domain-app-write-gates",
        "severity": "high" if failed else "medium",
        "title": "领域应用写入能力仍需安全门",
        "evidence": f"应用中心安全矩阵仍有 {failed} 个失败、{warn} 个警告：{', '.join(attention_apps)}。",
        "next": "在 DomainApps 消除 warn/fail 项后，再考虑写回、反向代理或自动执行动作。",
    }


def _project_focus_queue(
    projects: list[dict[str, Any]],
    queue_id: str,
    title: str,
    severity: str,
    reason: str,
    matcher: Any,
) -> dict[str, Any]:
    matched = [project for project in projects if matcher(project)]
    return {
        "id": queue_id,
        "title": title,
        "severity": severity,
        "reason": reason,
        "count": len(matched),
        "project_ids": [project["id"] for project in matched],
        "top_projects": [
            {
                "id": project["id"],
                "diagnostics": project.get("diagnostics", [])[:2],
            }
            for project in matched[:4]
        ],
    }


def _build_project_focus(projects: list[dict[str, Any]]) -> dict[str, Any]:
    queues = [
        _project_focus_queue(
            projects,
            "needs-action",
            "需要动作",
            "high",
            "项目不是 ready、需要常驻但未监听/未登记，或验证失败/暂无验证。",
            lambda project: (
                project.get("operational", {}).get("status") != "ready"
                or project.get("runtime", {}).get("status") in {"stopped", "unobserved"}
                or project.get("runtime", {}).get("latest_verification", {}).get("status") in {"failed", "unknown"}
            ),
        ),
        _project_focus_queue(
            projects,
            "operational-gap",
            "目录/文档缺口",
            "medium",
            "项目目录、文档、manifest 或命令登记仍未补齐。",
            lambda project: project.get("operational", {}).get("status") != "ready",
        ),
        _project_focus_queue(
            projects,
            "runtime-gap",
            "运行未就绪",
            "medium",
            "项目需要常驻服务，但端口未监听或尚未登记可观测端口。",
            lambda project: project.get("runtime", {}).get("status") in {"stopped", "unobserved"},
        ),
        _project_focus_queue(
            projects,
            "verification-gap",
            "验证待补证",
            "medium",
            "最近验证失败，或当前连可复制验证方案都还没有。",
            lambda project: (
                project.get("runtime", {}).get("latest_verification", {}).get("status") in {"failed", "unknown"}
            ),
        ),
        _project_focus_queue(
            projects,
            "verification-ready",
            "可验证未留证",
            "low",
            "项目已经登记验证命令，但还缺最近一次 workflow 证据。",
            lambda project: project.get("runtime", {}).get("latest_verification", {}).get("status") == "documented",
        ),
        _project_focus_queue(
            projects,
            "ready-and-running",
            "可日用项目",
            "low",
            "目录状态 ready，且运行中或已明确无需常驻服务。",
            lambda project: (
                project.get("operational", {}).get("status") == "ready"
                and project.get("runtime", {}).get("status") in {"running", "not_applicable"}
                and project.get("runtime", {}).get("latest_verification", {}).get("status")
                in {"verified", "documented"}
            ),
        ),
    ]
    queue_lookup = {queue["id"]: queue for queue in queues}
    return {
        "queues": queues,
        "summary": {
            "needs_action": queue_lookup["needs-action"]["count"],
            "operational_gap": queue_lookup["operational-gap"]["count"],
            "runtime_gap": queue_lookup["runtime-gap"]["count"],
            "verification_gap": queue_lookup["verification-gap"]["count"],
            "verification_ready": queue_lookup["verification-ready"]["count"],
            "ready_and_running": queue_lookup["ready-and-running"]["count"],
        },
    }


def _project_triage_queue(
    projects: list[dict[str, Any]],
    queue_id: str,
    title: str,
    severity: str,
    reason: str,
    category: str,
) -> dict[str, Any]:
    commands = [
        command
        for project in projects
        for command in project.get("triage_commands", [])
        if command.get("category") == category
    ]
    status_counts = {
        status: sum(1 for command in commands if (command.get("task") or {}).get("status") == status)
        for status in ("planned", "active", "succeeded", "failed", "completed")
    }
    queued = sum(status_counts.values())
    return {
        "id": queue_id,
        "title": title,
        "severity": severity,
        "reason": reason,
        "count": len(commands),
        "queued": queued,
        "active": status_counts["active"],
        "succeeded": status_counts["succeeded"],
        "failed": status_counts["failed"],
        "project_ids": sorted({command["project_id"] for command in commands}),
        "commands": commands[:8],
    }


def _build_project_triage(projects: list[dict[str, Any]]) -> dict[str, Any]:
    queues = [
        _project_triage_queue(
            projects,
            "runtime",
            "运行排查",
            "medium",
            "端口未监听、缺少端口登记或需要人工启动确认的项目。",
            "runtime",
        ),
        _project_triage_queue(
            projects,
            "verification",
            "验证排查",
            "high",
            "最近验证失败，或当前缺少可复制验证方案的项目。",
            "verification",
        ),
        _project_triage_queue(
            projects,
            "coverage",
            "清单排查",
            "medium",
            "项目文档、命令或 manifest 不完整的项目。",
            "coverage",
        ),
    ]
    return {
        "queues": queues,
        "summary": {
            "total_commands": sum(queue["count"] for queue in queues),
            "runtime_commands": queues[0]["count"],
            "verification_commands": queues[1]["count"],
            "coverage_commands": queues[2]["count"],
            "queued_commands": sum(queue["queued"] for queue in queues),
            "active_commands": sum(queue["active"] for queue in queues),
            "succeeded_commands": sum(queue["succeeded"] for queue in queues),
            "failed_commands": sum(queue["failed"] for queue in queues),
        },
    }


def _build_project_capability_coverage(projects: list[dict[str, Any]]) -> dict[str, Any]:
    total_projects = len(projects)
    dimension_summary: list[dict[str, Any]] = []

    for dimension in PROJECT_COVERAGE_DIMENSIONS:
        checks = [
            (project, next(check for check in project.get("coverage_checks", []) if check["id"] == dimension["id"]))
            for project in projects
        ]
        ready = sum(1 for _, check in checks if check["status"] == "ready")
        warning = sum(1 for _, check in checks if check["status"] == "warning")
        failed = sum(1 for _, check in checks if check["status"] == "failed")
        score = round((ready / total_projects) * 100) if total_projects else 0
        status = "ready" if warning == 0 and failed == 0 else "warning" if failed == 0 else "failed"
        attention_projects = [
            {
                "id": project["id"],
                "status": check["status"],
                "next_action": check["next_action"],
            }
            for project, check in checks
            if check["status"] != "ready"
        ][:4]

        dimension_summary.append(
            {
                "id": dimension["id"],
                "title": dimension["title"],
                "description": dimension["description"],
                "status": status,
                "ready": ready,
                "warning": warning,
                "failed": failed,
                "score": score,
                "attention_projects": attention_projects,
            }
        )

    total_cells = total_projects * len(PROJECT_COVERAGE_DIMENSIONS)
    ready_cells = sum(
        1 for project in projects for check in project.get("coverage_checks", []) if check["status"] == "ready"
    )
    warning_cells = sum(
        1 for project in projects for check in project.get("coverage_checks", []) if check["status"] == "warning"
    )
    failed_cells = sum(
        1 for project in projects for check in project.get("coverage_checks", []) if check["status"] == "failed"
    )

    weakest_dimensions = sorted(
        dimension_summary,
        key=lambda item: (item["score"], -item["failed"], -item["warning"], item["title"]),
    )[:3]

    return {
        "dimensions": list(PROJECT_COVERAGE_DIMENSIONS),
        "dimension_summary": dimension_summary,
        "weakest_dimensions": weakest_dimensions,
        "matrix": [
            {
                "project_id": project["id"],
                "layer": project["layer"],
                "cockpit_page": project["cockpit_page"],
                "ready": sum(1 for check in project.get("coverage_checks", []) if check["status"] == "ready"),
                "warning": sum(1 for check in project.get("coverage_checks", []) if check["status"] == "warning"),
                "failed": sum(1 for check in project.get("coverage_checks", []) if check["status"] == "failed"),
                "checks": project.get("coverage_checks", []),
            }
            for project in projects
        ],
        "summary": {
            "projects": total_projects,
            "dimensions": len(PROJECT_COVERAGE_DIMENSIONS),
            "total_cells": total_cells,
            "ready_cells": ready_cells,
            "warning_cells": warning_cells,
            "failed_cells": failed_cells,
            "score": round((ready_cells / total_cells) * 100) if total_cells else 0,
        },
    }


def _build_project_portfolio(
    projects: list[dict[str, Any]], project_capability_coverage: dict[str, Any]
) -> dict[str, Any]:
    bucket_defs = (
        ("blocked", "阻塞项目", "high", "验证失败、目录缺失或多个能力维度失败，需要优先处理。"),
        ("at_risk", "风险项目", "medium", "运行、文档、命令或探针存在缺口，影响稳定日用。"),
        ("watch", "观察项目", "medium", "存在提醒项或活跃工作流，短期需要跟进。"),
        ("healthy", "健康项目", "low", "核心覆盖维度已经就绪，保持证据新鲜即可。"),
    )
    buckets = []
    for bucket_id, title, severity, reason in bucket_defs:
        matched = [project for project in projects if project.get("portfolio", {}).get("status") == bucket_id]
        buckets.append(
            {
                "id": bucket_id,
                "title": title,
                "severity": severity,
                "reason": reason,
                "count": len(matched),
                "project_ids": [project["id"] for project in matched],
            }
        )

    status_rank = {"blocked": 0, "at_risk": 1, "watch": 2, "healthy": 3}
    priority_source = sorted(
        projects,
        key=lambda project: (
            status_rank.get(project.get("portfolio", {}).get("status"), 9),
            project.get("portfolio", {}).get("score", 0),
            -project.get("portfolio", {}).get("failed", 0),
            -project.get("portfolio", {}).get("warning", 0),
            project["id"],
        ),
    )
    priority_projects = [
        {
            "id": project["id"],
            "layer": project["layer"],
            "cockpit_page": project["cockpit_page"],
            "score": project.get("portfolio", {}).get("score", 0),
            "status": project.get("portfolio", {}).get("status", "unknown"),
            "primary_gap": project.get("portfolio", {}).get("primary_gap", ""),
            "next_action": project.get("portfolio", {}).get("next_action", ""),
            "failed": project.get("portfolio", {}).get("failed", 0),
            "warning": project.get("portfolio", {}).get("warning", 0),
            "runtime_status": project.get("runtime", {}).get("status", "unknown"),
            "verification_status": project.get("runtime", {}).get("latest_verification", {}).get("status", "unknown"),
            "non_ready_dimensions": project.get("portfolio", {}).get("non_ready_dimensions", []),
            "triage_commands": len(project.get("triage_commands") or []),
        }
        for project in priority_source
        if project.get("portfolio", {}).get("status") != "healthy"
    ][:8]

    if not priority_projects:
        priority_projects = [
            {
                "id": project["id"],
                "layer": project["layer"],
                "cockpit_page": project["cockpit_page"],
                "score": project.get("portfolio", {}).get("score", 0),
                "status": project.get("portfolio", {}).get("status", "healthy"),
                "primary_gap": project.get("portfolio", {}).get("primary_gap", "状态可日用"),
                "next_action": project.get("portfolio", {}).get("next_action", "保持项目状态同步。"),
                "failed": 0,
                "warning": project.get("portfolio", {}).get("warning", 0),
                "runtime_status": project.get("runtime", {}).get("status", "unknown"),
                "verification_status": project.get("runtime", {})
                .get("latest_verification", {})
                .get("status", "unknown"),
                "non_ready_dimensions": project.get("portfolio", {}).get("non_ready_dimensions", []),
                "triage_commands": len(project.get("triage_commands") or []),
            }
            for project in priority_source[:4]
        ]

    blocked = next(bucket for bucket in buckets if bucket["id"] == "blocked")
    at_risk = next(bucket for bucket in buckets if bucket["id"] == "at_risk")
    watch = next(bucket for bucket in buckets if bucket["id"] == "watch")
    score = project_capability_coverage.get("summary", {}).get("score", 0)
    posture = (
        "blocked" if blocked["count"] else "at_risk" if at_risk["count"] else "watch" if watch["count"] else "healthy"
    )

    return {
        "summary": {
            "score": score,
            "status": posture,
            "projects": len(projects),
            "blocked": blocked["count"],
            "at_risk": at_risk["count"],
            "watch": watch["count"],
            "healthy": next(bucket for bucket in buckets if bucket["id"] == "healthy")["count"],
            "priority_projects": len(priority_projects),
            "weakest_dimensions": len(project_capability_coverage.get("weakest_dimensions") or []),
        },
        "buckets": buckets,
        "priority_projects": priority_projects,
        "weakest_dimensions": project_capability_coverage.get("weakest_dimensions") or [],
    }


def _build_gap_list(
    projects: list[dict[str, Any]],
    feature_domains: list[dict[str, Any]],
    domain_apps: dict[str, Any],
    project_capability_coverage: dict[str, Any] | None = None,
    router_health: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    orientation_only = [project["id"] for project in projects if project["coverage"] == "orientation"]
    operational_gaps = [
        project["id"] for project in projects if project.get("operational", {}).get("status") != "ready"
    ]
    gaps = []
    domain_gap = _domain_app_security_gap(domain_apps)
    if domain_gap:
        gaps.append(domain_gap)
    if orientation_only or operational_gaps:
        gaps.append(
            {
                "id": "project-native-surface",
                "severity": "medium",
                "title": "部分项目仍需补齐状态面",
                "evidence": ", ".join(sorted(set(orientation_only + operational_gaps))),
                "next": "优先补齐高频项目的文档、命令、构建清单和运行探针。",
            }
        )
    if not feature_domains:
        gaps.append(
            {
                "id": "capability-map-unavailable",
                "severity": "high",
                "title": "能力地图不可读",
                "evidence": "docs/FUNCTIONAL-CAPABILITY-MAP.md 未能解析出能力域。",
                "next": "修复能力地图格式或提供机器可读 registry。",
            }
        )

    unavailable_routers = [
        item.get("module", "unknown")
        for item in (router_health or {}).get("items", [])
        if item.get("status") != "loaded"
    ]
    if unavailable_routers:
        gaps.append(
            {
                "id": "router-module-degradation",
                "severity": "high",
                "title": "部分 Cockpit 路由模块未加载",
                "evidence": ", ".join(str(module) for module in unavailable_routers),
                "next": "补齐缺失依赖或修复模块导入，再重新加载对应能力面。",
            }
        )

    for dimension in (project_capability_coverage or {}).get("weakest_dimensions") or []:
        if dimension.get("status") not in {"failed", "warning"}:
            continue
        attention_projects = dimension.get("attention_projects") or []
        evidence = ", ".join(item.get("id", "unknown") for item in attention_projects[:8]) or "项目矩阵"
        gap_id = f"project-{dimension.get('id', 'coverage')}-evidence"
        if any(gap.get("id") == gap_id for gap in gaps):
            continue
        gaps.append(
            {
                "id": gap_id,
                "severity": "high" if dimension.get("status") == "failed" else "medium",
                "title": f"项目{dimension.get('title', '覆盖')}不足",
                "evidence": evidence,
                "next": dimension.get("description") or dimension.get("next_action") or "补齐该项目维度的可验证证据。",
            }
        )
    return gaps


def _build_roadmap() -> dict[str, Any]:
    lane_labels = {
        "now": "现在补",
        "next": "下一步",
        "later": "后续增强",
    }
    lanes = []
    existing_items = list(ROADMAP_ITEMS)
    covered_pages = {item.get("cockpit_page") for item in existing_items}
    # Every page needs an explicit evolution contract.  Keep generated
    # contracts planned until a page has a real acceptance entry in the
    # curated roadmap; otherwise maturity silently treats missing planning as
    # a healthy page.
    generated_page_contracts = [
        {
            "id": f"page-contract-{page['id'].lower()}",
            "priority": "P1",
            "stage": "next",
            "status": "planned",
            "title": f"补齐{page['title']}页面运营契约",
            "domain": "page-coverage",
            "cockpit_page": page["id"],
            "problem": f"{page['title']}已有 Cockpit 入口，但页面对象、动作、证据和下一步建设还没有独立的路线项。",
            "actions": (
                "把页面数据源、可用动作、验证证据和使用路径绑定到同一份页面契约。",
                "为页面补一个可重复执行的验收项，并把结果回链到 TaskCenter。",
            ),
            "acceptance": (
                "页面能清楚说明对象、动作、证据和当前下一步。",
                "页面契约能在 SystemMap 和 TaskCenter 之间往返，不再只留下模糊 watch。",
            ),
        }
        for page in COCKPIT_PAGES
        if page["id"] not in covered_pages
    ]
    items = [
        {
            **item,
            "source_refs": [_source_ref_for_id(CATALOG_SOURCE, item["id"], "路线图定义", "system_map_api")],
        }
        for item in [*existing_items, *generated_page_contracts]
    ]
    for lane_id, label in lane_labels.items():
        lane_items = [item for item in items if item["stage"] == lane_id]
        lanes.append({"id": lane_id, "title": label, "items": lane_items})
    return {
        "items": items,
        "lanes": lanes,
        "summary": {
            "total": len(items),
            "shipped": sum(1 for item in items if item["status"] == "shipped"),
            "planned": sum(1 for item in items if item["status"] != "shipped"),
            "p0": sum(1 for item in items if item["priority"] == "P0"),
        },
    }


def _build_playbooks(page_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    playbooks: list[dict[str, Any]] = []
    for playbook in OPERATING_PLAYBOOKS:
        steps = []
        for step in playbook["steps"]:
            page = page_lookup.get(step["page_id"])
            if not page:
                continue
            steps.append({**step, "page": page})
        playbooks.append(
            {
                **playbook,
                "steps": steps,
                "source_refs": [_source_ref_for_id(CATALOG_SOURCE, playbook["id"], "操作清单定义", "system_map_api")],
            }
        )
    return playbooks


def _build_usage_paths(page_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **path,
            "pages": [page_lookup[step] for step in path["steps"] if step in page_lookup],
            "source_refs": [_source_ref_for_id(CATALOG_SOURCE, path["id"], "使用路径定义", "system_map_api")],
        }
        for path in USAGE_PATHS
    ]


def _page_maturity_next_action(
    projects: list[dict[str, Any]],
    domains: list[dict[str, Any]],
    usage_paths: list[dict[str, Any]],
    playbook_steps: list[dict[str, Any]],
    roadmap_items: list[dict[str, Any]],
    actions: int,
) -> str:
    if not usage_paths:
        return "把页面接入至少一条使用路径。"
    if not playbook_steps:
        return "补一条操作清单步骤，让页面进入日常流程。"
    if not domains:
        return "补功能域映射，说明页面承载的能力。"
    if not projects:
        return "补项目或服务映射，避免页面只有入口没有对象。"
    if not actions:
        return "补受控动作或排查命令，让页面能推进问题。"
    if not roadmap_items:
        return "补路线图或验收项，让页面演进可追踪。"
    return "保持页面、项目、清单和路线图证据新鲜。"


def _build_page_maturity(
    projects: list[dict[str, Any]],
    feature_domains: list[dict[str, Any]],
    usage_paths: list[dict[str, Any]],
    playbooks: list[dict[str, Any]],
    roadmap: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    roadmap_items = roadmap.get("items") or []
    for page in COCKPIT_PAGES:
        page_id = page["id"]
        linked_project_ids = set(PAGE_PROJECT_LINKS.get(page_id, ()))
        page_projects = [
            project
            for project in projects
            if project.get("cockpit_page") == page_id or project.get("id") in linked_project_ids
        ]
        linked_domain_ids = set(PAGE_CAPABILITY_LINKS.get(page_id, ()))
        page_domains = [
            domain
            for domain in feature_domains
            if domain.get("cockpit_page") == page_id or domain.get("id") in linked_domain_ids
        ]
        page_usage_paths = [
            path for path in usage_paths if any(path_page.get("id") == page_id for path_page in path.get("pages") or [])
        ]
        page_playbook_steps = [
            step
            for playbook in playbooks
            for step in playbook.get("steps") or []
            if step.get("page_id") == page_id or (step.get("page") or {}).get("id") == page_id
        ]
        page_roadmap_items = [item for item in roadmap_items if item.get("cockpit_page") == page_id]
        roadmap_status = "shipped" if any(item.get("status") == "shipped" for item in page_roadmap_items) else "planned"
        project_action_count = sum(
            len(project.get("actions") or []) + len(project.get("triage_commands") or []) for project in page_projects
        )
        page_action_ids = list(PAGE_OPERATOR_ACTIONS.get(page_id, ()))
        page_action_details = [
            {
                "id": action_id,
                **PAGE_OPERATOR_ACTION_METADATA.get(
                    action_id,
                    {
                        "label": action_id,
                        "kind": "queue",
                        "risk": "medium",
                        "description": "进入任务中心承接该页面动作。",
                    },
                ),
            }
            for action_id in page_action_ids
        ]
        action_count = project_action_count + len(page_action_ids)
        score = (
            (25 if page_projects else 0)
            + (20 if page_domains else 0)
            + (20 if page_usage_paths else 0)
            + (15 if page_playbook_steps else 0)
            + (10 if page_roadmap_items else 0)
            + (10 if action_count else 0)
        )
        traceability_status = "tracked" if page_roadmap_items else "untracked"
        status = (
            "ready"
            if score >= 70 and traceability_status == "tracked" and roadmap_status == "shipped"
            else "watch"
            if score >= 40
            else "gap"
        )
        traceability_next_action = (
            "保持页面路线图与验收项同步。"
            if roadmap_status == "shipped"
            else "把页面运营契约从 planned 推进到 shipped，并补真实验收证据。"
        )
        items.append(
            {
                "page": page,
                "page_id": page_id,
                "score": score,
                "status": status,
                "traceability_status": traceability_status,
                "traceability_next_action": traceability_next_action,
                "roadmap_status": roadmap_status,
                "projects": [project.get("id") for project in page_projects],
                "domains": [domain.get("id") for domain in page_domains],
                "usage_paths": [path.get("id") for path in page_usage_paths],
                "playbook_steps": [step.get("id") for step in page_playbook_steps],
                "roadmap_items": [item.get("id") for item in page_roadmap_items],
                "actions": action_count,
                "operator_actions": page_action_ids,
                "operator_action_details": page_action_details,
                "next_action": (
                    traceability_next_action
                    if roadmap_status != "shipped"
                    else _page_maturity_next_action(
                        page_projects,
                        page_domains,
                        page_usage_paths,
                        page_playbook_steps,
                        page_roadmap_items,
                        action_count,
                    )
                ),
            }
        )

    return {
        "items": items,
        "attention_items": [
            item for item in sorted(items, key=lambda row: (row["score"], row["page_id"])) if item["status"] != "ready"
        ],
        "featured_attention_items": [
            item for item in sorted(items, key=lambda row: (row["score"], row["page_id"])) if item["status"] != "ready"
        ][:8],
        "summary": {
            "total": len(items),
            "ready": sum(1 for item in items if item["status"] == "ready"),
            "watch": sum(1 for item in items if item["status"] == "watch"),
            "gap": sum(1 for item in items if item["status"] == "gap"),
            "score": round(sum(item["score"] for item in items) / len(items)) if items else 0,
        },
    }


def _count_source_refs(*collections: list[dict[str, Any]]) -> int:
    total = 0
    for collection in collections:
        for item in collection:
            total += len(item.get("source_refs") or [])
            for port in item.get("runtime", {}).get("ports", []):
                if port.get("source_ref"):
                    total += 1
    return total


def _count_project_actions(projects: list[dict[str, Any]]) -> int:
    return sum(len(project.get("actions") or []) for project in projects)


def build_system_map() -> dict[str, Any]:
    registry_path = compat.WORKSPACE_ROOT / "docs" / "project-registry.yaml"
    capability_map_path = compat.WORKSPACE_ROOT / "docs" / "FUNCTIONAL-CAPABILITY-MAP.md"
    port_registry_path = compat.WORKSPACE_ROOT / "protocols" / "port-registry.yaml"
    registry = _read_yaml(registry_path)
    port_registry = _read_yaml(port_registry_path)
    projects = _build_projects(registry, port_registry, registry_path, port_registry_path)
    project_focus = _build_project_focus(projects)
    project_triage = _build_project_triage(projects)
    project_capability_coverage = _build_project_capability_coverage(projects)
    project_portfolio = _build_project_portfolio(projects, project_capability_coverage)
    domain_apps = _build_domain_apps_summary()
    router_health = router_health_snapshot()
    feature_domains = _parse_capability_domains(capability_map_path)
    layers = _build_layers(registry, projects, registry_path)
    page_lookup = {page["id"]: page for page in COCKPIT_PAGES}
    gaps = _build_gap_list(projects, feature_domains, domain_apps, project_capability_coverage, router_health)
    roadmap = _build_roadmap()
    playbooks = _build_playbooks(page_lookup)
    usage_paths = _build_usage_paths(page_lookup)
    page_maturity = _build_page_maturity(projects, feature_domains, usage_paths, playbooks, roadmap)

    return {
        "schema_version": "v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "architecture": {
            "model": (registry.get("workspace") or {}).get("architecture", "5+4+1+1"),
            "ecos_version": (registry.get("workspace") or {}).get("ecos_version", "v6"),
            "dependency_direction": "entry surfaces -> routing mesh -> engines/runtime/protocol -> governed state and evidence",
        },
        "source_paths": {
            "project_registry": _path_state(registry_path),
            "architecture": _path_state(compat.WORKSPACE_ROOT / "ARCHITECTURE.md"),
            "functional_capability_map": _path_state(capability_map_path),
            "layer_index": _path_state(compat.WORKSPACE_ROOT / "docs" / "generated" / "project-layer-index.md"),
            "port_registry": _path_state(port_registry_path),
            "bos_services": _path_state(compat.WORKSPACE_ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"),
        },
        "cockpit_pages": list(COCKPIT_PAGES),
        "layers": layers,
        "projects": projects,
        "project_focus": project_focus,
        "project_triage": project_triage,
        "project_capability_coverage": project_capability_coverage,
        "project_portfolio": project_portfolio,
        "domain_apps": domain_apps,
        "router_health": router_health,
        "feature_domains": feature_domains,
        "roadmap": roadmap,
        "playbooks": playbooks,
        "usage_paths": usage_paths,
        "page_maturity": page_maturity,
        "gaps": gaps,
        "summary": {
            "projects": len(projects),
            "layers": len(layers),
            "feature_domains": len(feature_domains),
            "cockpit_pages": len(COCKPIT_PAGES),
            "native_project_surfaces": sum(1 for project in projects if project["coverage"] == "native"),
            "orientation_project_surfaces": sum(1 for project in projects if project["coverage"] != "native"),
            "ready_projects": sum(1 for project in projects if project["operational"]["status"] == "ready"),
            "partial_projects": sum(1 for project in projects if project["operational"]["status"] == "partial"),
            "missing_projects": sum(1 for project in projects if project["operational"]["status"] == "missing"),
            "running_projects": sum(1 for project in projects if project["runtime"]["status"] == "running"),
            "stopped_projects": sum(1 for project in projects if project["runtime"]["status"] == "stopped"),
            "unobserved_projects": sum(1 for project in projects if project["runtime"]["status"] == "unobserved"),
            "not_applicable_projects": sum(
                1 for project in projects if project["runtime"]["status"] == "not_applicable"
            ),
            "gaps": len(gaps),
            "roadmap_items": roadmap["summary"]["total"],
            "playbooks": len(playbooks),
            "project_actions": _count_project_actions(projects),
            "projects_needing_action": project_focus["summary"]["needs_action"],
            "project_triage_commands": project_triage["summary"]["total_commands"],
            "project_coverage_score": project_capability_coverage["summary"]["score"],
            "project_portfolio_score": project_portfolio["summary"]["score"],
            "blocked_projects": project_portfolio["summary"]["blocked"],
            "at_risk_projects": project_portfolio["summary"]["at_risk"],
            "domain_apps": domain_apps["summary"]["total"],
            "domain_app_score": domain_apps["summary"]["score"],
            "domain_app_security_attention": domain_apps["summary"]["security_attention_apps"],
            "page_maturity_score": page_maturity["summary"]["score"],
            "page_maturity_ready": page_maturity["summary"]["ready"],
            "page_maturity_watch": page_maturity["summary"]["watch"],
            "page_maturity_gap": page_maturity["summary"]["gap"],
            "source_refs": _count_source_refs(
                projects,
                layers,
                feature_domains,
                roadmap["items"],
                playbooks,
                usage_paths,
            ),
        },
    }


@router.get("/api/cockpit/system-map")
async def get_system_map() -> dict[str, Any]:
    return build_system_map()


@router.get("/api/cockpit/source-ref")
async def get_source_ref_preview(
    target: str | None = Query(default=None, description="Source ref target, usually absolute path:line"),
    path: str | None = Query(default=None, description="Source file path when target is not provided"),
    line: int | None = Query(default=None, ge=1, description="Optional 1-based source line"),
    context: int = Query(default=4, ge=0, le=20, description="Number of surrounding lines to include"),
) -> dict[str, Any]:
    return build_source_ref_preview(target=target, path=path, line=line, context=context)
