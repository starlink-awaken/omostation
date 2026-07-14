"""Tasks API endpoints.

提供任务管理功能。

Routes:
    GET    /api/tasks              → 任务列表
    GET    /api/tasks/:id          → 任务详情
    POST   /api/tasks/:id/pause    → 暂停任务
    POST   /api/tasks/:id/resume   → 恢复任务
    POST   /api/tasks/:id/cancel   → 取消任务
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from cockpit.compat import WORKSPACE_ROOT
from cockpit.web.api_system_map import build_system_map

router = APIRouter()

# L4-kernel 项目路径
WORKSPACE_DIR = WORKSPACE_ROOT
L4_KERNEL_DIR = WORKSPACE_DIR / "projects" / "l4-kernel"


def run_l4_script(script_name: str, args: list[str] | None = None) -> dict | None:
    """运行 L4-kernel 脚本并返回 JSON 结果。"""
    script_path = L4_KERNEL_DIR / "scripts" / script_name
    if not script_path.exists():
        return None

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Script {script_name} failed: {result.stderr}")
            return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:  # defensive fallback
        print(f"Error running {script_name}: {e}")
        return None


def get_tasks_from_omo() -> list[dict]:
    """从 OMO 获取任务列表。"""
    tasks_dir = WORKSPACE_DIR / ".omo" / "tasks"
    tasks = []

    # 读取活跃任务
    active_dir = tasks_dir / "active"
    if active_dir.exists():
        for task_file in active_dir.glob("*.yaml"):
            try:
                import yaml

                with open(task_file) as f:
                    task_data = yaml.safe_load(f) or {}
                tasks.append(
                    {
                        "id": task_data.get("id", task_file.stem),
                        "title": task_data.get("title", task_file.stem),
                        "description": task_data.get("description", ""),
                        "status": "in_progress",
                        "progress": task_data.get("progress", 0),
                        "created_at": task_data.get("created_at", datetime.now(UTC).isoformat()),
                        "updated_at": task_data.get("updated_at", datetime.now(UTC).isoformat()),
                        "assignee": task_data.get("assignee", None),
                        "priority": task_data.get("priority", "medium"),
                        "tags": task_data.get("tags", []),
                    }
                )
            except Exception:  # noqa: S112  # defensive fallback
                continue

    # 读取计划任务
    planned_dir = tasks_dir / "planned"
    if planned_dir.exists():
        for task_file in planned_dir.glob("*.yaml"):
            try:
                import yaml

                with open(task_file) as f:
                    task_data = yaml.safe_load(f) or {}
                tasks.append(
                    {
                        "id": task_data.get("id", task_file.stem),
                        "title": task_data.get("title", task_file.stem),
                        "description": task_data.get("description", ""),
                        "status": "pending",
                        "progress": 0,
                        "created_at": task_data.get("created_at", datetime.now(UTC).isoformat()),
                        "updated_at": task_data.get("updated_at", datetime.now(UTC).isoformat()),
                        "assignee": task_data.get("assignee", None),
                        "priority": task_data.get("priority", "medium"),
                        "tags": task_data.get("tags", []),
                    }
                )
            except Exception:  # noqa: S112  # defensive fallback
                continue

    # 读取完成任务
    done_dir = tasks_dir / "done"
    if done_dir.exists():
        for task_file in list(done_dir.glob("*.yaml"))[:10]:  # 只取最近 10 个
            try:
                import yaml

                with open(task_file) as f:
                    task_data = yaml.safe_load(f) or {}
                tasks.append(
                    {
                        "id": task_data.get("id", task_file.stem),
                        "title": task_data.get("title", task_file.stem),
                        "description": task_data.get("description", ""),
                        "status": "completed",
                        "progress": 100,
                        "created_at": task_data.get("created_at", datetime.now(UTC).isoformat()),
                        "updated_at": task_data.get("updated_at", datetime.now(UTC).isoformat()),
                        "assignee": task_data.get("assignee", None),
                        "priority": task_data.get("priority", "medium"),
                        "tags": task_data.get("tags", []),
                    }
                )
            except Exception:  # noqa: S112  # defensive fallback
                continue

    return tasks


def _priority_from_risk(risk: str) -> str:
    if risk == "high":
        return "high"
    if risk == "medium":
        return "medium"
    return "low"


def _playbook_copy_text(playbook: dict) -> str:
    lines = [
        f"# 操作清单任务草稿：{playbook['title']}",
        "",
        f"目标：{playbook.get('goal', '')}",
        f"频率：{playbook.get('frequency', 'on-demand')}",
        f"负责人：{playbook.get('owner', 'operator')}",
        "",
        "步骤：",
    ]
    for index, step in enumerate(playbook.get("steps") or [], start=1):
        lines.extend(
            [
                f"{index}. {step.get('action', '')}",
                f"   入口：{(step.get('page') or {}).get('title') or step.get('page_id')}",
                f"   证据：{step.get('evidence', '')}",
                f"   完成：{step.get('done_when', '')}",
            ]
        )
    return "\n".join(lines)


def _priority_from_portfolio_status(status: str) -> str:
    if status == "blocked":
        return "critical"
    if status == "at_risk":
        return "high"
    if status == "watch":
        return "medium"
    return "low"


def _project_portfolio_copy_text(project: dict) -> str:
    dimensions = project.get("non_ready_dimensions") or []
    lines = [
        f"# 项目组合修复草稿：{project.get('id', 'unknown')}",
        "",
        f"状态：{project.get('status', 'unknown')} · 组合分：{project.get('score', 0)}%",
        f"层级：{project.get('layer', 'unknown')} · 入口：{project.get('cockpit_page', 'SystemMap')}",
        f"主要缺口：{project.get('primary_gap', '')}",
        f"下一步：{project.get('next_action', '')}",
        "",
        "证据：",
        f"- runtime：{project.get('runtime_status', 'unknown')}",
        f"- verification：{project.get('verification_status', 'unknown')}",
        f"- triage commands：{project.get('triage_commands', 0)}",
    ]
    if dimensions:
        lines.append("")
        lines.append("未就绪维度：")
        for dimension in dimensions:
            lines.append(
                f"- {dimension.get('title', dimension.get('id', 'unknown'))}"
                f" [{dimension.get('status', 'unknown')}]：{dimension.get('next_action', '')}"
            )
    lines.extend(
        [
            "",
            "安全门：只读项目组合草稿；复制后由人确认，正式写入需走 C2G/OMO 受控入口。",
        ]
    )
    return "\n".join(lines)


def _priority_from_verification_ready(project: dict) -> str:
    runtime_status = str(project.get("runtime_status", "unknown"))
    if runtime_status in {"stopped", "unobserved"}:
        return "high"
    if runtime_status == "running":
        return "medium"
    return "low"


def _verification_ready_copy_text(project: dict) -> str:
    verification = project.get("latest_verification") or {}
    source_refs = project.get("source_refs") or []
    lines = [
        f"# 验证补证草稿：{project.get('id', 'unknown')}",
        "",
        f"项目：{project.get('id', 'unknown')}",
        f"层级：{project.get('layer', 'unknown')} · 入口：{project.get('cockpit_page', 'SystemMap')}",
        f"运行：{project.get('runtime_status', 'unknown')} · 验证：{verification.get('status', 'unknown')}",
        f"下一步：{project.get('next_action', '')}",
        "",
        "建议动作：",
        f"1. 复制并执行验证命令：{verification.get('command') or '未登记'}",
        "2. 确认输出结果是否能作为当前项目的最小可用验证。",
        "3. 通过 agent-workflow verify / closeout 留下正式证据。",
    ]
    if source_refs:
        lines.extend(
            [
                "",
                "来源定位：",
                *[
                    f"- {ref.get('label', ref.get('source_key', 'source'))}: {ref.get('target', ref.get('path', ''))}"
                    for ref in source_refs[:4]
                ],
            ]
        )
    lines.extend(
        [
            "",
            "安全门：只读验证补证草稿；复制后由人确认，正式写入需走 agent-workflow / C2G / OMO 受控入口。",
        ]
    )
    return "\n".join(lines)


def _priority_from_domain_app(app: dict) -> str:
    if app.get("security_posture") == "blocked" or app.get("security_failed", 0):
        return "critical"
    if app.get("risk_level") == "high" or app.get("runtime_status") == "stopped":
        return "high"
    if app.get("security_posture") == "attention" or app.get("health") != "ready":
        return "medium"
    return "low"


def _domain_app_copy_text(app: dict, domain_apps: dict) -> str:
    lines = [
        f"# 领域应用处理草稿：{app.get('name', app.get('id', 'unknown'))}",
        "",
        f"应用：{app.get('id', 'unknown')}",
        f"领域：{(app.get('domain') or {}).get('name', 'unknown')}",
        f"集成模式：{app.get('integration_mode', 'unknown')}",
        f"健康：{app.get('health', 'unknown')} · 运行：{app.get('runtime_status', 'unknown')}",
        f"安全态：{app.get('security_posture', 'unknown')} · 风险：{app.get('risk_level', 'unknown')}",
        f"下一步：{app.get('next_action', '')}",
        "",
        "能力：",
        f"- read：{', '.join(app.get('read_capabilities') or []) or 'none'}",
        f"- write：{', '.join(app.get('write_capabilities') or []) or 'none'}",
        f"- actions：{app.get('action_count', 0)}",
        "",
        "总览：",
        f"- domain app score：{(domain_apps.get('summary') or {}).get('score', 0)}%",
        f"- domain app status：{domain_apps.get('status', 'unknown')}",
        f"- security attention apps：{(domain_apps.get('summary') or {}).get('security_attention_apps', 0)}",
        "",
        "安全门：只读领域应用草稿；复制后由人确认，正式写入需走领域 app 自身认证/审计或 C2G/OMO 受控入口。",
    ]
    return "\n".join(lines)


def get_playbook_task_drafts() -> list[dict]:
    """Build read-only TaskCenter drafts from SystemMap playbooks."""
    system_map = build_system_map()
    generated_at = system_map.get("generated_at") or datetime.now(UTC).isoformat()
    drafts: list[dict] = []

    for playbook in system_map.get("playbooks") or []:
        playbook_id = playbook.get("id", "unknown")
        steps = playbook.get("steps") or []
        drafts.append(
            {
                "id": f"playbook-{playbook_id}",
                "title": f"操作清单：{playbook.get('title', playbook_id)}",
                "description": playbook.get("goal", ""),
                "status": "pending",
                "progress": 0,
                "created_at": generated_at,
                "updated_at": generated_at,
                "assignee": playbook.get("owner") or "operator",
                "priority": _priority_from_risk(str(playbook.get("risk", "low"))),
                "tags": ["playbook", "draft", str(playbook.get("frequency", "on-demand"))],
                "read_only": True,
                "source": {
                    "type": "system_map_playbook",
                    "id": playbook_id,
                    "title": playbook.get("title", playbook_id),
                    "source_refs": playbook.get("source_refs") or [],
                },
                "draft": {
                    "kind": "playbook_task",
                    "copy_text": _playbook_copy_text(playbook),
                    "step_count": len(steps),
                    "evidence_fields": [
                        {
                            "step_id": step.get("id"),
                            "page_id": step.get("page_id"),
                            "evidence": step.get("evidence", ""),
                            "done_when": step.get("done_when", ""),
                        }
                        for step in steps
                    ],
                    "guard": "只读任务草稿；需要正式写入时走 C2G/OMO 受控入口。",
                },
            }
        )

    return drafts


def get_domain_app_task_drafts(limit: int = 8) -> list[dict]:
    """Build read-only TaskCenter drafts from SystemMap DomainApps attention items."""
    system_map = build_system_map()
    generated_at = system_map.get("generated_at") or datetime.now(UTC).isoformat()
    domain_apps = system_map.get("domain_apps") or {}
    apps_by_id = {item.get("id"): item for item in domain_apps.get("items") or []}
    attention_ids = [item.get("id") for item in domain_apps.get("attention_items") or []]
    attention_apps = [apps_by_id[app_id] for app_id in attention_ids if app_id in apps_by_id]

    drafts: list[dict] = []
    for app in attention_apps[:limit]:
        app_id = app.get("id", "unknown")
        drafts.append(
            {
                "id": f"domain-app-{app_id}",
                "title": f"领域应用：处理 {app.get('name', app_id)}",
                "description": app.get("next_action", ""),
                "status": "pending",
                "progress": 0,
                "created_at": generated_at,
                "updated_at": generated_at,
                "assignee": "operator",
                "priority": _priority_from_domain_app(app),
                "tags": [
                    "domain-app",
                    "draft",
                    str(app.get("domain", {}).get("id", "unknown")),
                    str(app.get("runtime_status", "unknown")),
                    str(app.get("security_posture", "unknown")),
                ],
                "read_only": True,
                "source": {
                    "type": "system_map_domain_app",
                    "id": app_id,
                    "title": f"{app.get('name', app_id)} 领域应用态势",
                    "source_refs": [],
                },
                "draft": {
                    "kind": "domain_app_task",
                    "copy_text": _domain_app_copy_text(app, domain_apps),
                    "step_count": 1,
                    "evidence_fields": [
                        {"label": "健康状态", "value": str(app.get("health", "unknown"))},
                        {"label": "运行状态", "value": str(app.get("runtime_status", "unknown"))},
                        {"label": "安全态", "value": str(app.get("security_posture", "unknown"))},
                        {"label": "下一步", "value": str(app.get("next_action", ""))},
                    ],
                    "guard": "只读领域应用草稿；正式写入需走领域 app 自身认证/审计或 C2G/OMO 受控入口。",
                },
            }
        )

    return drafts


def _priority_from_capability_gap(gap: dict) -> str:
    severity = str(gap.get("severity", "medium"))
    if severity == "high":
        return "critical"
    if severity == "medium":
        return "high"
    return "medium"


def _capability_gap_copy_text(gap: dict) -> str:
    lines = [
        f"# 能力缺口处理草稿：{gap.get('title', gap.get('id', 'unknown'))}",
        "",
        f"缺口：{gap.get('id', 'unknown')}",
        f"严重度：{gap.get('severity', 'unknown')}",
        f"证据：{gap.get('evidence', '')}",
        f"下一步：{gap.get('next', '')}",
        "",
        "处理建议：",
        "1. 在 SystemMap 中确认缺口影响的项目、页面或领域。",
        "2. 复制相关验证/排查命令，确认缺口是否仍存在。",
        "3. 若需要正式写入任务，走 C2G/OMO 受控入口并附上证据。",
        "",
        "安全门：只读能力缺口草稿；复制后由人确认，正式写入需走 C2G/OMO 受控入口。",
    ]
    return "\n".join(lines)


def get_capability_gap_task_drafts(limit: int = 8) -> list[dict]:
    """Build read-only TaskCenter drafts from SystemMap capability gaps."""
    system_map = build_system_map()
    generated_at = system_map.get("generated_at") or datetime.now(UTC).isoformat()
    drafts: list[dict] = []

    for gap in (system_map.get("gaps") or [])[:limit]:
        gap_id = gap.get("id", "unknown")
        drafts.append(
            {
                "id": f"capability-gap-{gap_id}",
                "title": f"能力缺口：处理 {gap.get('title', gap_id)}",
                "description": gap.get("next", ""),
                "status": "pending",
                "progress": 0,
                "created_at": generated_at,
                "updated_at": generated_at,
                "assignee": "operator",
                "priority": _priority_from_capability_gap(gap),
                "tags": [
                    "capability-gap",
                    "draft",
                    str(gap.get("severity", "unknown")),
                    str(gap_id),
                ],
                "read_only": True,
                "source": {
                    "type": "system_map_capability_gap",
                    "id": gap_id,
                    "title": f"{gap.get('title', gap_id)} 能力缺口",
                    "source_refs": [],
                },
                "draft": {
                    "kind": "capability_gap_task",
                    "copy_text": _capability_gap_copy_text(gap),
                    "step_count": 3,
                    "evidence_fields": [
                        {"label": "严重度", "value": str(gap.get("severity", "unknown"))},
                        {"label": "证据", "value": str(gap.get("evidence", ""))},
                        {"label": "下一步", "value": str(gap.get("next", ""))},
                    ],
                    "guard": "只读能力缺口草稿；正式写入需走 C2G/OMO 受控入口。",
                },
            }
        )

    return drafts


def _priority_from_page_maturity(page_item: dict) -> str:
    if page_item.get("status") == "gap":
        return "high"
    if page_item.get("status") == "watch":
        return "medium"
    return "low"


def _page_maturity_copy_text(page_item: dict) -> str:
    page = page_item.get("page") or {}
    lines = [
        f"# 页面能力补齐草稿：{page.get('title', page_item.get('page_id', 'unknown'))}",
        "",
        f"页面：{page_item.get('page_id', 'unknown')}",
        f"状态：{page_item.get('status', 'unknown')} · 成熟度：{page_item.get('score', 0)}%",
        f"分组：{page.get('group', 'unknown')}",
        f"用途：{page.get('purpose', '')}",
        f"下一步：{page_item.get('next_action', '')}",
        "",
        "覆盖证据：",
        f"- projects：{', '.join(page_item.get('projects') or []) or 'none'}",
        f"- domains：{', '.join(page_item.get('domains') or []) or 'none'}",
        f"- usage paths：{', '.join(page_item.get('usage_paths') or []) or 'none'}",
        f"- playbook steps：{', '.join(page_item.get('playbook_steps') or []) or 'none'}",
        f"- roadmap items：{', '.join(page_item.get('roadmap_items') or []) or 'none'}",
        f"- actions：{page_item.get('actions', 0)}",
        "",
        "安全门：只读页面能力草稿；复制后由人确认，正式写入需走 C2G/OMO 受控入口。",
    ]
    return "\n".join(lines)


def get_page_maturity_task_drafts(limit: int = 8) -> list[dict]:
    """Build read-only TaskCenter drafts from Cockpit page maturity attention items."""
    system_map = build_system_map()
    generated_at = system_map.get("generated_at") or datetime.now(UTC).isoformat()
    page_maturity = system_map.get("page_maturity") or {}
    drafts: list[dict] = []

    for page_item in (page_maturity.get("attention_items") or [])[:limit]:
        page = page_item.get("page") or {}
        page_id = page_item.get("page_id", page.get("id", "unknown"))
        drafts.append(
            {
                "id": f"page-maturity-{page_id}",
                "title": f"页面能力：补齐 {page.get('title', page_id)}",
                "description": page_item.get("next_action", ""),
                "status": "pending",
                "progress": 0,
                "created_at": generated_at,
                "updated_at": generated_at,
                "assignee": "operator",
                "priority": _priority_from_page_maturity(page_item),
                "tags": [
                    "page-maturity",
                    "draft",
                    str(page_item.get("status", "unknown")),
                    str(page_id),
                    str(page.get("group", "unknown")),
                ],
                "read_only": True,
                "source": {
                    "type": "system_map_page_maturity",
                    "id": page_id,
                    "title": f"{page.get('title', page_id)} 页面成熟度",
                    "source_refs": [],
                },
                "draft": {
                    "kind": "page_maturity_task",
                    "copy_text": _page_maturity_copy_text(page_item),
                    "step_count": 1,
                    "evidence_fields": [
                        {"label": "状态", "value": str(page_item.get("status", "unknown"))},
                        {"label": "成熟度", "value": f"{page_item.get('score', 0)}%"},
                        {"label": "下一步", "value": str(page_item.get("next_action", ""))},
                    ],
                    "guard": "只读页面能力草稿；正式写入需走 C2G/OMO 受控入口。",
                },
            }
        )

    return drafts


def get_project_portfolio_task_drafts(limit: int = 8) -> list[dict]:
    """Build read-only TaskCenter drafts from SystemMap project portfolio priorities."""
    system_map = build_system_map()
    generated_at = system_map.get("generated_at") or datetime.now(UTC).isoformat()
    drafts: list[dict] = []
    projects_by_id = {project.get("id"): project for project in system_map.get("projects") or []}

    for project in (system_map.get("project_portfolio", {}).get("priority_projects") or [])[:limit]:
        project_id = project.get("id", "unknown")
        source_project = projects_by_id.get(project_id) or {}
        dimensions = project.get("non_ready_dimensions") or []
        drafts.append(
            {
                "id": f"portfolio-{project_id}",
                "title": f"项目组合：修复 {project_id}",
                "description": project.get("next_action", ""),
                "status": "pending",
                "progress": 0,
                "created_at": generated_at,
                "updated_at": generated_at,
                "assignee": "engineering",
                "priority": _priority_from_portfolio_status(str(project.get("status", "healthy"))),
                "tags": [
                    "project-portfolio",
                    "draft",
                    str(project.get("status", "unknown")),
                    str(project.get("layer", "unknown")),
                ],
                "read_only": True,
                "source": {
                    "type": "system_map_project_portfolio",
                    "id": project_id,
                    "title": f"{project_id} 项目组合态势",
                    "source_refs": source_project.get("source_refs") or [],
                },
                "draft": {
                    "kind": "project_portfolio_task",
                    "copy_text": _project_portfolio_copy_text(project),
                    "step_count": max(1, len(dimensions)),
                    "evidence_fields": [
                        {"label": "组合状态", "value": str(project.get("status", "unknown"))},
                        {"label": "组合分", "value": f"{project.get('score', 0)}%"},
                        {"label": "运行状态", "value": str(project.get("runtime_status", "unknown"))},
                        {"label": "验证状态", "value": str(project.get("verification_status", "unknown"))},
                        {"label": "主要缺口", "value": str(project.get("primary_gap", ""))},
                    ],
                    "guard": "只读项目组合草稿；复制后由人确认，正式写入需走 C2G/OMO 受控入口。",
                },
            }
        )

    return drafts


def get_verification_ready_task_drafts(limit: int = 12) -> list[dict]:
    """Build read-only TaskCenter drafts for projects with commands but no workflow evidence yet."""
    system_map = build_system_map()
    generated_at = system_map.get("generated_at") or datetime.now(UTC).isoformat()
    projects_by_id = {project.get("id"): project for project in system_map.get("projects") or []}
    queues = system_map.get("project_focus", {}).get("queues") or []
    verification_queue = next((queue for queue in queues if queue.get("id") == "verification-ready"), {})
    drafts: list[dict] = []

    for project_id in (verification_queue.get("project_ids") or [])[:limit]:
        project = projects_by_id.get(project_id) or {}
        verification = (project.get("runtime") or {}).get("latest_verification") or {}
        drafts.append(
            {
                "id": f"verification-ready-{project_id}",
                "title": f"验证补证：{project_id}",
                "description": "项目已登记验证命令，但最近还没有 workflow 验证证据。",
                "status": "pending",
                "progress": 0,
                "created_at": generated_at,
                "updated_at": generated_at,
                "assignee": "engineering",
                "priority": _priority_from_verification_ready(
                    {
                        "runtime_status": (project.get("runtime") or {}).get("status", "unknown"),
                    }
                ),
                "tags": [
                    "verification-ready",
                    "draft",
                    str(project.get("layer", "unknown")),
                    str((project.get("runtime") or {}).get("status", "unknown")),
                ],
                "read_only": True,
                "source": {
                    "type": "system_map_verification_ready",
                    "id": project_id,
                    "title": f"{project_id} 验证补证",
                    "source_refs": project.get("source_refs") or [],
                },
                "draft": {
                    "kind": "verification_ready_task",
                    "copy_text": _verification_ready_copy_text(
                        {
                            "id": project_id,
                            "layer": project.get("layer", "unknown"),
                            "cockpit_page": project.get("cockpit_page", "SystemMap"),
                            "runtime_status": (project.get("runtime") or {}).get("status", "unknown"),
                            "latest_verification": verification,
                            "next_action": "复制验证命令执行后，通过 agent-workflow 留证。",
                            "source_refs": project.get("source_refs") or [],
                        }
                    ),
                    "step_count": 3,
                    "evidence_fields": [
                        {"label": "运行状态", "value": str((project.get("runtime") or {}).get("status", "unknown"))},
                        {"label": "验证状态", "value": str(verification.get("status", "unknown"))},
                        {"label": "验证命令", "value": str(verification.get("command") or "未登记")},
                        {"label": "入口页面", "value": str(project.get("cockpit_page", "SystemMap"))},
                    ],
                    "guard": "只读验证补证草稿；正式写入需走 agent-workflow / C2G / OMO 受控入口。",
                },
            }
        )

    return drafts


@router.get("/api/tasks")
async def get_tasks(
    status: str | None = Query(None, description="任务状态过滤"),
    limit: int = Query(100, description="返回数量限制"),
    sort: str = Query("updated", description="排序方式"),
    include_playbook_drafts: bool = Query(False, description="包含 SystemMap 操作清单任务草稿"),
    include_project_portfolio_drafts: bool = Query(False, description="包含 SystemMap 项目组合任务草稿"),
    include_verification_ready_drafts: bool = Query(False, description="包含 SystemMap 验证补证草稿"),
    include_domain_app_drafts: bool = Query(False, description="包含 SystemMap 领域应用任务草稿"),
    include_capability_gap_drafts: bool = Query(False, description="包含 SystemMap 能力缺口任务草稿"),
    include_page_maturity_drafts: bool = Query(False, description="包含 Cockpit 页面能力补齐任务草稿"),
):
    """获取任务列表。"""
    tasks = get_tasks_from_omo()
    if include_playbook_drafts:
        tasks.extend(get_playbook_task_drafts())
    if include_project_portfolio_drafts:
        tasks.extend(get_project_portfolio_task_drafts())
    if include_verification_ready_drafts:
        tasks.extend(get_verification_ready_task_drafts())
    if include_domain_app_drafts:
        tasks.extend(get_domain_app_task_drafts())
    if include_capability_gap_drafts:
        tasks.extend(get_capability_gap_task_drafts())
    if include_page_maturity_drafts:
        tasks.extend(get_page_maturity_task_drafts())

    # 过滤
    if status:
        tasks = [t for t in tasks if t["status"] == status]

    # 排序
    if sort == "updated":
        tasks.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    elif sort == "created":
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    # 限制数量
    tasks = tasks[:limit]

    return {
        "items": tasks,
        "total": len(tasks),
    }


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情。"""
    tasks = get_tasks_from_omo()
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """暂停任务。"""
    return {
        "id": task_id,
        "status": "pending",
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复任务。"""
    return {
        "id": task_id,
        "status": "in_progress",
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务。"""
    return {
        "id": task_id,
        "status": "cancelled",
        "updated_at": datetime.now(UTC).isoformat(),
    }
