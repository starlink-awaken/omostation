"""OPC P5 Scenarios — B4 cockpit 统一入口.

P5-F1 technical-radar: 从 cockpit `data/db/research` 拉真实研究 ID 集合,
按 agent 出现频次 + topic 关键字 + 标签命中率排序, 产出 ≥3 upgrade candidates。

P5-F2 work-assistant: 接 1 个真实工作 query (如 "OPC P5 路线图"), 走
research 引擎, 输出结构化草稿 + source + timestamp + next-action。

P5-F3 family-health: 走 privacy_class=confidential 路径 (只读
documents_vault 内 "family" tag 的 vault item, 严格不调 provider)。

P5-F4 decision-inbox: 决策收件箱 — 场景卡驱动的决策生命周期管理。
  子命令: {list, summary, add, status, show, create-scene, create-journey}

所有 scenario 共享同一入口: `cockpit scenario {radar|assistant|health|inbox} [--query Q]`。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_scenario_parser(scenario_p: Any, parser_class: type) -> None:
    """Build the `cockpit scenario` argument subparsers (P5-F1..F9).

    Extracted from cli.py so that cli.py stays under the god-module >1500L
    hard rule. `scenario_p` is the top-level `sub.add_parser("scenario", ...)`
    created in cli.py and `parser_class` is the WorkspaceParser subclass
    defined there. Keeping `sub.add_parser("scenario")` in cli.py preserves
    the help_map static registration check (test_help_discover_ssot).
    """
    # 产品走查 v5 #V5-13: 默认人类可读面板, --json 输出机器可读原样 (脚本/管道消费)
    scenario_p.add_argument(
        "--json",
        action="store_true",
        dest="scenario_json",
        help="输出原始 JSON (脚本/管道消费); 默认人类可读面板",
    )
    scenario_sub = scenario_p.add_subparsers(dest="scenario_sub", parser_class=parser_class)
    scenario_radar = scenario_sub.add_parser(
        "radar", help="P5-F1 technical-radar: 扫描研究活动, 产出 ≥3 upgrade candidates"
    )
    scenario_radar.add_argument("--limit", type=int, default=10, help="最多产出多少 candidates (默认 10, 红线 ≥3)")
    scenario_assistant = scenario_sub.add_parser(
        "assistant", help="P5-F2 work-assistant: 1 真实工作 query → 结构化草稿"
    )
    scenario_assistant.add_argument("--query", type=str, default="OPC P5 progress", help="真实工作 query")
    scenario_health = scenario_sub.add_parser(
        "health", help="P5-F3 family-health: 1 真实家庭健康 query → 3 级 next-action (privacy=confidential)"
    )
    scenario_health.add_argument("--query", type=str, default="日常家庭健康问询", help="真实家庭健康 query")

    # P5-F4: 决策收件箱
    scenario_inbox = scenario_sub.add_parser("inbox", help="P5-F4 decision-inbox: 场景卡驱动的决策生命周期管理")
    inbox_sub = scenario_inbox.add_subparsers(dest="inbox_action", parser_class=parser_class)
    inbox_sub.add_parser("list", help="列出所有场景")
    inbox_sub.add_parser("summary", help="收件箱概览")
    inbox_add = inbox_sub.add_parser("add", help="添加意图到场景")
    inbox_add.add_argument("--scene-id", dest="scene_id", required=True, help="场景 ID")
    inbox_add.add_argument("--source", default="manual", help="来源 (email/file/message/manual/oa/sms)")
    inbox_add.add_argument("--content", required=True, help="意图内容")
    inbox_add.add_argument("--priority", default="P3", choices=["P0", "P1", "P2", "P3"], help="优先级")
    inbox_status = inbox_sub.add_parser("status", help="更新意图状态")
    inbox_status.add_argument("--intent-id", dest="intent_id", required=True, help="意图 ID")
    inbox_status.add_argument(
        "--status", required=True, choices=["pending", "task_created", "approved", "rejected", "done"], help="新状态"
    )
    inbox_status.add_argument("--task-id", dest="task_id", help="关联的 OMO Task ID")
    inbox_show = inbox_sub.add_parser("show", help="查看场景详情")
    inbox_show.add_argument("--scene-id", dest="scene_id", required=True, help="场景 ID")
    inbox_create_scene = inbox_sub.add_parser("create-scene", help="创建新场景")
    inbox_create_scene.add_argument("--name", required=True, help="场景名称")
    inbox_create_scene.add_argument("--description", default="", help="场景描述")
    inbox_create_scene.add_argument("--priority", default="P1", choices=["P0", "P1", "P2"], help="优先级")
    inbox_create_journey = inbox_sub.add_parser("create-journey", help="创建新 Journey")
    inbox_create_journey.add_argument("--scene-id", dest="scene_id", required=True, help="场景 ID")
    inbox_create_journey.add_argument("--name", required=True, help="Journey 名称")

    # P5-F5: 摄入管线
    scenario_intake = scenario_sub.add_parser("intake", help="P5-F5 intake: 邮件/文件/消息→结构化事项摄入管线")
    intake_sub = scenario_intake.add_subparsers(dest="intake_action", parser_class=parser_class)
    intake_preview = intake_sub.add_parser("preview", help="预览摄入结果 (不持久化)")
    intake_preview.add_argument("--content", required=True, help="摄入内容")
    intake_preview.add_argument(
        "--source", default="manual", choices=["email", "file", "message", "manual", "oa", "sms"], help="来源类型"
    )
    intake_preview.add_argument("--filename", default="", help="文件名 (file 来源时)")
    intake_run = intake_sub.add_parser("run", help="执行摄入管线 (提取→丰富→添加到收件箱)")
    intake_run.add_argument("--scene-id", dest="scene_id", required=True, help="目标场景 ID")
    intake_run.add_argument("--content", required=True, help="摄入内容")
    intake_run.add_argument(
        "--source", default="manual", choices=["email", "file", "message", "manual", "oa", "sms"], help="来源类型"
    )
    intake_run.add_argument("--filename", default="", help="文件名 (file 来源时)")
    intake_run.add_argument("--journey-id", dest="journey_id", help="目标 Journey ID (默认第一个)")

    # P5-F6: 任务桥接
    scenario_task = scenario_sub.add_parser("task", help="P5-F6 task: 场景卡→OMO Task 桥接管理")
    task_sub = scenario_task.add_subparsers(dest="task_action", parser_class=parser_class)
    task_approve = task_sub.add_parser("approve", help="审批意图并创建 OMO Task 绑定")
    task_approve.add_argument("--intent-id", dest="intent_id", required=True, help="意图 ID")
    task_approve.add_argument("--outcome-metric", dest="outcome_metric", default="", help="结果指标")
    task_sub.add_parser("status", help="查看意图绑定状态").add_argument(
        "--intent-id", dest="intent_id", required=True, help="意图 ID"
    )
    task_sub.add_parser("list", help="列出所有绑定")
    task_complete = task_sub.add_parser("complete", help="标记绑定完成")
    task_complete.add_argument("--binding-id", dest="binding_id", required=True, help="绑定 ID")

    # P5-F7: HITL 审批流 + 证据面板
    scenario_approval = scenario_sub.add_parser("approval", help="P5-F7 approval: HITL 审批流 + 证据面板")
    approval_sub = scenario_approval.add_subparsers(dest="approval_action", parser_class=parser_class)
    approval_sub.add_parser("queue", help="查看待审批队列")
    approval_evidence = approval_sub.add_parser("evidence", help="查看意图证据详情")
    approval_evidence.add_argument("--intent-id", dest="intent_id", required=True, help="意图 ID")
    approval_approve = approval_sub.add_parser("approve", help="审批通过意图")
    approval_approve.add_argument("--intent-id", dest="intent_id", required=True, help="意图 ID")
    approval_approve.add_argument("--reviewer", default="human", help="审批人")
    approval_approve.add_argument("--note", default="", help="审批备注")
    approval_approve.add_argument("--outcome-metric", dest="outcome_metric", default="", help="结果指标")
    approval_reject = approval_sub.add_parser("reject", help="拒绝意图")
    approval_reject.add_argument("--intent-id", dest="intent_id", required=True, help="意图 ID")
    approval_reject.add_argument("--reviewer", default="human", help="审批人")
    approval_reject.add_argument("--note", default="", help="拒绝原因")
    approval_history = approval_sub.add_parser("history", help="查看审批历史")
    approval_history.add_argument("--limit", type=int, default=20, help="最多返回条数")
    approval_sub.add_parser("stats", help="查看审批统计")

    # P5-F8: 真实输入接入
    scenario_connector = scenario_sub.add_parser(
        "connector", help="P5-F8 connector: 真实输入接入 (邮件/文件/JSONL 自动导入)"
    )
    connector_sub = scenario_connector.add_subparsers(dest="connector_action", parser_class=parser_class)
    connector_run = connector_sub.add_parser("run", help="运行连接器")
    connector_run.add_argument("--source", required=True, choices=["email", "file", "jsonl", "manual"], help="来源类型")
    connector_run.add_argument("--scene-id", dest="scene_id", required=True, help="目标场景 ID")
    connector_run.add_argument("--source-path", dest="source_path", default="", help="源路径 (mbox文件/目录/jsonl文件)")
    connector_sub.add_parser("stats", help="查看连接器统计")

    # P5-F9: 复盘
    scenario_review = scenario_sub.add_parser("review", help="P5-F9 review: 每周复盘 + 试点报告")
    review_sub = scenario_review.add_subparsers(dest="review_action", parser_class=parser_class)
    review_weekly = review_sub.add_parser("weekly", help="生成每周复盘报告")
    review_weekly.add_argument("--weeks", type=int, default=1, help="回顾周数 (默认1周)")
    review_sub.add_parser("pilot", help="生成4周试点总结报告")

    # 真实领域业务场景合规性全链路审查 (Policy-as-Code)
    scenario_domain = scenario_sub.add_parser("domain", help="真实领域业务场景合规性审查 (Policy-as-Code)")
    scenario_domain.add_argument("--file", type=str, help="指定待审查的领域业务场景 YAML 文件路径")
    scenario_domain.add_argument("--json", action="store_true", help="以 JSON 格式输出审查报告")


# ── Decision inbox engine ──


def _decision_inbox_engine(workspace_root: Path | None = None) -> Any:
    """Load the decision inbox engine module."""
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-decision-inbox.py"
    spec = importlib.util.spec_from_file_location("scene_card_decision_inbox_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-decision-inbox.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _decision_inbox_list(workspace_root: Path) -> dict[str, Any]:
    """List all scenes in the decision inbox."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        scenes = engine.list_scenes(workspace_root)
        return {"ok": True, "scenes": [engine._dictify(s) for s in scenes]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_summary(workspace_root: Path) -> dict[str, Any]:
    """Show summary of the decision inbox."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        summary = engine.get_inbox_summary(workspace_root)
        return {"ok": True, "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_add_intent(
    workspace_root: Path,
    scene_id: str,
    source: str,
    raw_content: str,
    priority: str = "P3",
    journey_id: str | None = None,
) -> dict[str, Any]:
    """Add an intent to the decision inbox."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        scene = engine.load_scene(workspace_root, scene_id)
        if scene is None:
            return {"ok": False, "error": f"Scene {scene_id} not found"}
        if not scene.journeys:
            return {"ok": False, "error": f"Scene {scene_id} has no journeys"}
        jid = journey_id or scene.journeys[0].id
        intent = engine.add_intent(
            workspace_root,
            scene_id=scene_id,
            journey_id=jid,
            source=source,
            raw_content=raw_content,
            priority=priority,
        )
        return {"ok": True, "intent": engine._dictify(intent)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_set_status(
    workspace_root: Path,
    intent_id: str,
    status: str,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Update an intent's status."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        intent = engine.update_intent_status(
            workspace_root,
            intent_id=intent_id,
            new_status=status,
            task_id=task_id,
        )
        if intent is None:
            return {"ok": False, "error": f"Intent {intent_id} not found"}
        return {"ok": True, "intent": engine._dictify(intent)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_show_scene(workspace_root: Path, scene_id: str) -> dict[str, Any]:
    """Show details of a scene."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        scene = engine.load_scene(workspace_root, scene_id)
        if scene is None:
            return {"ok": False, "error": f"Scene {scene_id} not found"}
        return {"ok": True, "scene": engine._dictify(scene)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_create_scene(
    workspace_root: Path,
    name: str,
    description: str,
    priority: str = "P1",
) -> dict[str, Any]:
    """Create a new decision inbox scene."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        scene = engine.create_scene(workspace_root, name=name, description=description, priority=priority)
        return {"ok": True, "scene": engine._dictify(scene)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_create_journey(
    workspace_root: Path,
    scene_id: str,
    name: str,
) -> dict[str, Any]:
    """Create a new journey in a scene."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        journey = engine.create_journey(workspace_root, scene_id=scene_id, name=name)
        return {"ok": True, "journey": engine._dictify(journey)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Intake pipeline ──


def _intake_engine(workspace_root: Path | None = None) -> Any:
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-intake-pipeline.py"
    spec = importlib.util.spec_from_file_location("scene_card_intake_pipeline_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-intake-pipeline.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _intake_preview(workspace_root: Path, content: str, source: str = "manual", filename: str = "") -> dict[str, Any]:
    """Preview intake without persisting."""
    try:
        engine = _intake_engine(workspace_root)
        enriched = engine.preview_intake(content, source=source, filename=filename)
        return {
            "ok": True,
            "title": enriched.title,
            "description": enriched.description[:200],
            "category": enriched.category,
            "priority": enriched.priority,
            "deadline": enriched.deadline,
            "tags": enriched.tags,
            "confidence": enriched.confidence,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _intake_run(
    workspace_root: Path,
    scene_id: str,
    content: str,
    source: str = "manual",
    filename: str = "",
    journey_id: str | None = None,
) -> dict[str, Any]:
    """Run intake pipeline: extract → enrich → add to inbox."""
    try:
        engine = _intake_engine(workspace_root)
        result = engine.intake(
            workspace_root,
            source=source,
            raw_content=content,
            scene_id=scene_id,
            journey_id=journey_id,
            filename=filename,
        )
        if not result.ok:
            return {"ok": False, "error": result.error}
        return {
            "ok": True,
            "intent_id": result.intent_id,
            "scene_id": result.scene_id,
            "journey_id": result.journey_id,
            "priority": result.enriched.priority if result.enriched else "P3",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Task bridge ──


def _task_bridge_engine(workspace_root: Path | None = None) -> Any:
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-task-bridge.py"
    spec = importlib.util.spec_from_file_location("scene_card_task_bridge_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-task-bridge.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _task_approve(workspace_root: Path, intent_id: str, outcome_metric: str = "") -> dict[str, Any]:
    """Approve an intent and create its OMO task binding."""
    try:
        engine = _task_bridge_engine(workspace_root)
        result = engine.approve_intent_and_create_task(
            workspace_root,
            intent_id=intent_id,
            outcome_metric=outcome_metric,
        )
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _task_binding_status(workspace_root: Path, intent_id: str) -> dict[str, Any]:
    """Get binding status for an intent."""
    try:
        engine = _task_bridge_engine(workspace_root)
        status = engine.get_binding_status(workspace_root, intent_id)
        if status is None:
            return {"ok": False, "error": f"No binding found for intent {intent_id}"}
        return {"ok": True, **status}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _task_list_bindings(workspace_root: Path) -> dict[str, Any]:
    """List all task bindings."""
    try:
        engine = _task_bridge_engine(workspace_root)
        bindings = engine.list_bindings(workspace_root)
        return {
            "ok": True,
            "bindings": [
                {
                    "binding_id": b.binding_id,
                    "task_id": b.task_id,
                    "scene_id": b.scene_id,
                    "intent_id": b.intent_id,
                    "status": b.status,
                    "created_at": b.created_at,
                }
                for b in bindings
            ],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _task_complete(workspace_root: Path, binding_id: str) -> dict[str, Any]:
    """Mark a task binding as completed."""
    try:
        engine = _task_bridge_engine(workspace_root)
        result = engine.complete_task(workspace_root, binding_id)
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Approval flow ──


def _approval_engine(workspace_root: Path | None = None) -> Any:
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-approval-flow.py"
    spec = importlib.util.spec_from_file_location("scene_card_approval_flow_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-approval-flow.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _approval_queue(workspace_root: Path) -> dict[str, Any]:
    """Get the review queue."""
    try:
        engine = _approval_engine(workspace_root)
        queue = engine.get_review_queue(workspace_root)
        return {"ok": True, "queue": queue, "total": len(queue)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _approval_evidence(workspace_root: Path, intent_id: str) -> dict[str, Any]:
    """Get evidence detail for an intent."""
    try:
        engine = _approval_engine(workspace_root)
        detail = engine.get_evidence_detail(workspace_root, intent_id)
        if detail is None:
            return {"ok": False, "error": f"Intent {intent_id} not found"}
        return {"ok": True, **detail}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _approval_approve(
    workspace_root: Path,
    intent_id: str,
    reviewer: str = "human",
    note: str = "",
    outcome_metric: str = "",
) -> dict[str, Any]:
    """Approve an intent."""
    try:
        engine = _approval_engine(workspace_root)
        result = engine.approve_intent(
            workspace_root,
            intent_id=intent_id,
            reviewer=reviewer,
            note=note,
            outcome_metric=outcome_metric,
        )
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _approval_reject(
    workspace_root: Path,
    intent_id: str,
    reviewer: str = "human",
    note: str = "",
) -> dict[str, Any]:
    """Reject an intent."""
    try:
        engine = _approval_engine(workspace_root)
        result = engine.reject_intent(
            workspace_root,
            intent_id=intent_id,
            reviewer=reviewer,
            note=note,
        )
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _approval_history(workspace_root: Path, limit: int = 20) -> dict[str, Any]:
    """Get approval history."""
    try:
        engine = _approval_engine(workspace_root)
        history = engine.get_approval_history(workspace_root, limit=limit)
        return {"ok": True, "history": history, "total": len(history)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _approval_stats(workspace_root: Path) -> dict[str, Any]:
    """Get approval statistics."""
    try:
        engine = _approval_engine(workspace_root)
        stats = engine.get_approval_stats(workspace_root)
        return {"ok": True, "stats": stats}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Connector ──


def _connector_engine(workspace_root: Path | None = None) -> Any:
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-connector.py"
    spec = importlib.util.spec_from_file_location("scene_card_connector_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-connector.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _connector_run(workspace_root: Path, source: str, scene_id: str, source_path: str = "") -> dict[str, Any]:
    try:
        eng = _connector_engine(workspace_root)
        result = eng.run_connector(workspace_root, source=source, scene_id=scene_id, source_path=source_path)
        return {
            "ok": True,
            "run_id": result.run_id,
            "source": result.source,
            "items_found": result.items_found,
            "items_imported": result.items_imported,
            "errors": result.errors,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _connector_stats(workspace_root: Path) -> dict[str, Any]:
    try:
        eng = _connector_engine(workspace_root)
        stats = eng.get_connector_stats(workspace_root)
        return {"ok": True, "stats": stats}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Review ──


def _review_engine(workspace_root: Path | None = None) -> Any:
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-review.py"
    spec = importlib.util.spec_from_file_location("scene_card_review_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-review.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _review_weekly(workspace_root: Path, weeks: int = 1) -> dict[str, Any]:
    try:
        eng = _review_engine(workspace_root)
        report = eng.generate_weekly_review(workspace_root, weeks=weeks)
        return {"ok": True, "report": report}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _review_pilot(workspace_root: Path) -> dict[str, Any]:
    try:
        eng = _review_engine(workspace_root)
        report = eng.generate_pilot_report(workspace_root)
        return {"ok": True, "report": report}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


from .scenario_sources import (
    _archive_scenario_receipt,
    _f1_technical_radar,
    _f2_work_assistant,
    _f3_family_health,
    _family_cards_sources,
    _load_recent_research_rows,
    _now_iso,
    _research_db_path,
    _score_text_match,
    _workspace_root,
)


def _cmd_scenario_domain(args) -> int:
    import runpy

    ws = _workspace_root()
    runner = ws / "bin" / "ssot" / "real-scenario-runner.py"
    target_file = getattr(args, "file", None)
    is_json = getattr(args, "json", False)
    runner_args = ["real-scenario-runner"]
    if target_file:
        runner_args.extend(["--file", target_file])
    if is_json:
        runner_args.append("--json")
    old_argv = sys.argv
    try:
        sys.argv = runner_args
        runpy.run_path(str(runner), run_name="__main__")
        return 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    except Exception as exc:
        sys.stderr.write(f"Error running domain scenario: {exc}\n")
        return 1
    finally:
        sys.argv = old_argv


def cmd_scenario(args) -> int:
    """cockpit scenario {radar|assistant|health|inbox|intake|task|domain}."""
    sub = getattr(args, "scenario_sub", None) or getattr(args, "scenario_action", None)
    if sub is None:
        console = sys.stderr
        console.write("Usage: cockpit scenario {radar|assistant|health|inbox|intake|task|domain} [--query Q]\n")
        return 2

    if sub == "domain":
        return _cmd_scenario_domain(args)
    elif sub == "radar":
        result = _f1_technical_radar(limit=getattr(args, "limit", 10) or 10)
    elif sub == "assistant":
        query = getattr(args, "query", None) or "OPC P5 progress"
        result = _f2_work_assistant(query=query)
    elif sub == "health":
        query = getattr(args, "query", None) or "日常家庭健康问询"
        result = _f3_family_health(query=query)
    elif sub == "inbox":
        ws = _workspace_root()
        inbox_action = getattr(args, "inbox_action", None)
        if inbox_action is None:
            sys.stderr.write(
                "Usage: cockpit scenario inbox {list|summary|add|status|show|create-scene|create-journey}\n"
            )
            return 2
        if inbox_action == "list":
            result = _decision_inbox_list(ws)
        elif inbox_action == "summary":
            result = _decision_inbox_summary(ws)
        elif inbox_action == "add":
            result = _decision_inbox_add_intent(
                ws,
                scene_id=getattr(args, "scene_id", ""),
                source=getattr(args, "source", "manual"),
                raw_content=getattr(args, "content", ""),
                priority=getattr(args, "priority", "P3"),
            )
        elif inbox_action == "status":
            result = _decision_inbox_set_status(
                ws,
                intent_id=getattr(args, "intent_id", ""),
                status=getattr(args, "status", ""),
                task_id=getattr(args, "task_id", None),
            )
        elif inbox_action == "show":
            result = _decision_inbox_show_scene(ws, scene_id=getattr(args, "scene_id", ""))
        elif inbox_action == "create-scene":
            result = _decision_inbox_create_scene(
                ws,
                name=getattr(args, "name", "Untitled Scene"),
                description=getattr(args, "description", ""),
                priority=getattr(args, "priority", "P1"),
            )
        elif inbox_action == "create-journey":
            result = _decision_inbox_create_journey(
                ws,
                scene_id=getattr(args, "scene_id", ""),
                name=getattr(args, "name", "Untitled Journey"),
            )
        else:
            sys.stderr.write(f"unknown inbox action: {inbox_action}\n")
            return 2
    elif sub == "intake":
        ws = _workspace_root()
        intake_action = getattr(args, "intake_action", None)
        if intake_action is None:
            sys.stderr.write("Usage: cockpit scenario intake {preview|run}\n")
            return 2
        if intake_action == "preview":
            result = _intake_preview(
                ws,
                content=getattr(args, "content", ""),
                source=getattr(args, "source", "manual"),
                filename=getattr(args, "filename", ""),
            )
        elif intake_action == "run":
            result = _intake_run(
                ws,
                scene_id=getattr(args, "scene_id", ""),
                content=getattr(args, "content", ""),
                source=getattr(args, "source", "manual"),
                filename=getattr(args, "filename", ""),
                journey_id=getattr(args, "journey_id", None),
            )
        else:
            sys.stderr.write(f"unknown intake action: {intake_action}\n")
            return 2
    elif sub == "task":
        ws = _workspace_root()
        task_action = getattr(args, "task_action", None)
        if task_action is None:
            sys.stderr.write("Usage: cockpit scenario task {approve|status|list|complete}\n")
            return 2
        if task_action == "approve":
            result = _task_approve(
                ws,
                intent_id=getattr(args, "intent_id", ""),
                outcome_metric=getattr(args, "outcome_metric", ""),
            )
        elif task_action == "status":
            result = _task_binding_status(ws, intent_id=getattr(args, "intent_id", ""))
        elif task_action == "list":
            result = _task_list_bindings(ws)
        elif task_action == "complete":
            result = _task_complete(ws, binding_id=getattr(args, "binding_id", ""))
        else:
            sys.stderr.write(f"unknown task action: {task_action}\n")
            return 2
    elif sub == "approval":
        ws = _workspace_root()
        approval_action = getattr(args, "approval_action", None)
        if approval_action is None:
            sys.stderr.write("Usage: cockpit scenario approval {queue|evidence|approve|reject|history|stats}\n")
            return 2
        if approval_action == "queue":
            result = _approval_queue(ws)
        elif approval_action == "evidence":
            result = _approval_evidence(ws, intent_id=getattr(args, "intent_id", ""))
        elif approval_action == "approve":
            result = _approval_approve(
                ws,
                intent_id=getattr(args, "intent_id", ""),
                reviewer=getattr(args, "reviewer", "human"),
                note=getattr(args, "note", ""),
                outcome_metric=getattr(args, "outcome_metric", ""),
            )
        elif approval_action == "reject":
            result = _approval_reject(
                ws,
                intent_id=getattr(args, "intent_id", ""),
                reviewer=getattr(args, "reviewer", "human"),
                note=getattr(args, "note", ""),
            )
        elif approval_action == "history":
            result = _approval_history(ws, limit=getattr(args, "limit", 20) or 20)
        elif approval_action == "stats":
            result = _approval_stats(ws)
        else:
            sys.stderr.write(f"unknown approval action: {approval_action}\n")
            return 2
    elif sub == "connector":
        ws = _workspace_root()
        conn_action = getattr(args, "connector_action", None)
        if conn_action is None:
            sys.stderr.write("Usage: cockpit scenario connector {run|stats}\n")
            return 2
        if conn_action == "run":
            result = _connector_run(
                ws,
                source=getattr(args, "source", "manual"),
                scene_id=getattr(args, "scene_id", ""),
                source_path=getattr(args, "source_path", ""),
            )
        elif conn_action == "stats":
            result = _connector_stats(ws)
        else:
            sys.stderr.write(f"unknown connector action: {conn_action}\n")
            return 2
    elif sub == "review":
        ws = _workspace_root()
        review_action = getattr(args, "review_action", None)
        if review_action is None:
            sys.stderr.write("Usage: cockpit scenario review {weekly|pilot}\n")
            return 2
        if review_action == "weekly":
            result = _review_weekly(ws, weeks=getattr(args, "weeks", 1) or 1)
        elif review_action == "pilot":
            result = _review_pilot(ws)
        else:
            sys.stderr.write(f"unknown review action: {review_action}\n")
            return 2
    else:
        sys.stderr.write(f"unknown scenario sub: {sub}\n")
        return 2

    if sub in ("inbox", "intake", "task", "approval", "connector", "review"):
        if getattr(args, "scenario_json", False):
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            _render_scenario_human(result)
        return 0

    result["archive_path"] = _archive_scenario_receipt(result)
    if getattr(args, "scenario_json", False):
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        _render_scenario_human(result)
    return 0


def _render_scenario_human(result: dict[str, Any]) -> None:
    """人类可读面板 (产品走查 v5 #V5-13: 之前裸 JSON 家长/管理者看不懂).

    三类 scenario 各自渲染: health 紧急级别配色 + 大字行动; radar 候选表格;
    assistant 草稿面板 + 来源表。--json 保留机器可读原样。
    """
    from rich import box as rich_box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    sc = result.get("scenario", "")
    gen = result.get("generated_at", "")

    if sc == "family-health":
        level = str(result.get("next_action_level", "normal"))
        action = str(result.get("next_action", ""))
        style = {"urgent": "red", "attention": "yellow"}.get(level, "green")
        icon = {"urgent": "🚨", "attention": "⚠️"}.get(level, "✅")
        query = result.get("query", "")
        reds = result.get("red_lines_followed", []) or []
        console.print(
            Panel(
                f"[bold {style}]{icon} 健康建议 · {level.upper()}[/]\n\n"
                f"[bold]查询:[/] {query}\n"
                f"[bold]建议行动:[/] {action}\n\n"
                f"[dim]隐私: {result.get('privacy_class', 'confidential')} · "
                f"来源: {result.get('source_count', 0)} 条 · 红线: {'、'.join(reds)}[/]",
                title="👨‍👩‍👧 家庭健康",
                border_style=style,
            )
        )
        if level == "urgent":
            console.print("[bold red]⚠️ 这是紧急信号, 请立即按建议行动, 切勿延误就医。[/]")
        return

    if sc == "technical-radar":
        cands = result.get("candidates", []) or []
        console.print(
            Panel(
                f"[bold cyan]📡 技术雷达 · {len(cands)} 个升级候选[/]\n[dim]{gen}[/]",
                border_style="cyan",
            )
        )
        table = Table(box=rich_box.ROUNDED, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("候选", style="bold")
        table.add_column("来源", style="cyan", no_wrap=False)
        table.add_column("下一步", style="green", no_wrap=False)
        for i, c in enumerate(cands, 1):
            table.add_row(
                str(i),
                str(c.get("title", ""))[:50],
                str(c.get("source_path", ""))[:28],
                str(c.get("next_action", ""))[:32],
            )
        console.print(table)
        return

    if sc == "work-assistant":
        draft = result.get("draft", {}) or {}
        sources = result.get("sources", []) or []
        console.print(
            Panel(
                f"[bold green]💼 工作助理草稿[/]\n"
                f"[bold]主题:[/] {draft.get('title', '')}\n"
                f"[bold]概要:[/] {draft.get('body', '')}\n\n"
                f"[bold]下一步:[/] {result.get('next_action', '')}\n"
                f"[dim]参考来源: {result.get('source_count', 0)} 条[/]",
                border_style="green",
            )
        )
        if sources:
            table = Table(box=rich_box.ROUNDED, header_style="bold green")
            table.add_column("#", width=3)
            table.add_column("来源", style="cyan", no_wrap=False)
            table.add_column("摘要", style="dim", no_wrap=False)
            for i, s in enumerate(sources, 1):
                table.add_row(
                    str(i),
                    str(s.get("title", ""))[:36],
                    str(s.get("summary", ""))[:54],
                )
            console.print(table)
        return

    # ── Decision inbox rendering ──
    if "scenes" in result:
        scenes = result.get("scenes", [])
        console.print(Panel(f"[bold blue]📋 决策收件箱 · {len(scenes)} 场景[/]", border_style="blue"))
        table = Table(box=rich_box.ROUNDED, header_style="bold blue")
        table.add_column("ID", style="dim", width=32)
        table.add_column("名称", style="bold")
        table.add_column("优先级", width=8)
        table.add_column("Journeys", width=8)
        for s in scenes:
            j_count = len(s.get("journeys", []))
            table.add_row(s.get("id", ""), s.get("name", ""), s.get("priority", ""), str(j_count))
        console.print(table)
        return

    if "summary" in result:
        summary = result.get("summary", {})
        console.print(
            Panel(
                f"[bold blue]📊 收件箱概览[/]\n"
                f"场景数: {summary.get('scene_count', 0)}\n"
                f"总意图: {summary.get('total_intents', 0)}\n"
                f"待处理: [bold yellow]{summary.get('pending_intents', 0)}[/]\n"
                f"来源分布: {summary.get('by_source', {})}\n"
                f"优先级分布: {summary.get('by_priority', {})}",
                border_style="blue",
            )
        )
        return

    if "scene" in result:
        scene = result.get("scene", {})
        panel_lines = [
            f"[bold]ID:[/] {scene.get('id', '')}",
            f"[bold]名称:[/] {scene.get('name', '')}",
            f"[bold]描述:[/] {scene.get('description', '')}",
            f"[bold]状态:[/] {scene.get('status', '')}",
            f"[bold]优先级:[/] {scene.get('priority', '')}",
        ]
        journeys = scene.get("journeys", [])
        panel_lines.append(f"[bold]Journeys:[/] {len(journeys)}")
        for j in journeys:
            panel_lines.append(
                f"  ├─ {j.get('name', '')} ({j.get('status', '')}) — {len(j.get('intents', []))} intents"
            )
        console.print(Panel("\n".join(panel_lines), title="🏷 场景详情", border_style="blue"))
        if journeys:
            for j in journeys:
                intents = j.get("intents", [])
                if not intents:
                    continue
                console.print(f"\n[bold]Journey: {j.get('name', '')}[/]")
                itable = Table(box=rich_box.ROUNDED, header_style="bold cyan")
                itable.add_column("ID", style="dim", width=32)
                itable.add_column("来源", width=10)
                itable.add_column("内容", style="bold")
                itable.add_column("状态", width=12)
                itable.add_column("优先级", width=8)
                for i in intents:
                    itable.add_row(
                        i.get("id", ""),
                        i.get("source", ""),
                        str(i.get("raw_content", ""))[:40],
                        i.get("status", ""),
                        i.get("priority", ""),
                    )
                console.print(itable)
        return

    if "intent" in result:
        intent = result.get("intent", {})
        console.print(
            Panel(
                f"[bold]意图 ID:[/] {intent.get('id', '')}\n"
                f"[bold]来源:[/] {intent.get('source', '')}\n"
                f"[bold]内容:[/] {str(intent.get('raw_content', ''))[:100]}\n"
                f"[bold]状态:[/] {intent.get('status', '')}\n"
                f"[bold]优先级:[/] {intent.get('priority', '')}\n"
                f"[bold]Task ID:[/] {intent.get('task_id', '—')}\n"
                f"[bold]创建时间:[/] {intent.get('created_at', '')}",
                title="💡 意图详情",
                border_style="cyan",
            )
        )
        return

    if "journey" in result:
        journey = result.get("journey", {})
        console.print(
            Panel(
                f"[bold]Journey ID:[/] {journey.get('id', '')}\n"
                f"[bold]名称:[/] {journey.get('name', '')}\n"
                f"[bold]状态:[/] {journey.get('status', '')}\n"
                f"[bold]Intents:[/] {len(journey.get('intents', []))}",
                title="🛤 Journey 详情",
                border_style="green",
            )
        )
        return

    # ── Approval rendering ──
    if "queue" in result:
        queue = result.get("queue", [])
        console.print(Panel(f"[bold yellow]📋 待审批队列 · {len(queue)} 项[/]", border_style="yellow"))
        if queue:
            table = Table(box=rich_box.ROUNDED, header_style="bold yellow")
            table.add_column("ID", style="dim", width=32)
            table.add_column("场景", style="bold")
            table.add_column("来源", width=10)
            table.add_column("内容", style="bold")
            table.add_column("优先级", width=8)
            table.add_column("证据", width=6)
            for item in queue:
                table.add_row(
                    item.get("intent_id", ""),
                    item.get("scene_name", ""),
                    item.get("source", ""),
                    str(item.get("raw_content", ""))[:36],
                    item.get("priority", ""),
                    str(item.get("evidence_count", 0)),
                )
            console.print(table)
        return

    if "stats" in result:
        stats = result.get("stats", {})
        console.print(
            Panel(
                f"[bold blue]📊 审批统计[/]\n"
                f"总意图: {stats.get('total_intents', 0)}\n"
                f"待审批: [bold yellow]{stats.get('pending_review', 0)}[/]\n"
                f"已通过: [bold green]{stats.get('approved', 0)}[/]\n"
                f"已拒绝: [bold red]{stats.get('rejected', 0)}[/]\n"
                f"通过率: [bold]{stats.get('approval_rate', 0) * 100:.1f}%[/]\n"
                f"审批记录: {stats.get('receipts_count', 0)}",
                border_style="blue",
            )
        )
        return

    if "history" in result:
        history = result.get("history", [])
        console.print(Panel(f"[bold]📜 审批历史 · {len(history)} 条[/]", border_style="blue"))
        if history:
            table = Table(box=rich_box.ROUNDED, header_style="bold blue")
            table.add_column("时间", style="dim", width=20)
            table.add_column("意图", style="bold", width=32)
            table.add_column("决定", width=10)
            table.add_column("审批人", width=10)
            table.add_column("备注", style="bold")
            for item in history:
                decision = item.get("decision", "")
                style = "green" if decision == "approved" else "red"
                table.add_row(
                    str(item.get("created_at", ""))[:19],
                    item.get("intent_id", ""),
                    f"[{style}]{decision}[/]",
                    item.get("reviewer", ""),
                    str(item.get("note", ""))[:32],
                )
            console.print(table)
        return

    if "receipts" in result:
        receipts = result.get("receipts", [])
        console.print(Panel(f"[bold]📜 审批凭证 · {len(receipts)} 条[/]", border_style="green"))
        for r in receipts[:10]:
            decision = r.get("decision", "")
            style = "green" if decision == "approved" else "red"
            console.print(
                f"  [{style}]{decision}[/] {r.get('intent_id', '')} — {r.get('reviewer', '')} — {str(r.get('created_at', ''))[:19]}"
            )
        return

    if "receipt_id" in result:
        decision = result.get("decision", result.get("status", ""))
        style = "green" if decision in ("approved", "task_created") else "red"
        icon = "✅" if decision in ("approved", "task_created") else "❌"
        lines = [
            f"[bold]决定:[/] [{style}]{icon} {decision}[/]",
            f"[bold]凭证 ID:[/] {result.get('receipt_id', '')}",
            f"[bold]审批人:[/] {result.get('reviewer', '')}",
        ]
        if result.get("binding_id"):
            lines.append(f"[bold]绑定 ID:[/] {result.get('binding_id')}")
        if result.get("task_id"):
            lines.append(f"[bold]Task ID:[/] {result.get('task_id')}")
        console.print(Panel("\n".join(lines), title="💡 审批结果", border_style=style))
        return

    # ── Connector rendering ──
    if "run_id" in result and "items_found" in result:
        source = result.get("source", "")
        found = result.get("items_found", 0)
        imported = result.get("items_imported", 0)
        errors = result.get("errors", [])
        style = "red" if errors else "green"
        lines = [
            f"[bold]运行 ID:[/] {result.get('run_id', '')}",
            f"[bold]来源:[/] {source}",
            f"[bold]发现:[/] {found} 项",
            f"[bold]导入:[/] [green]{imported}[/] 项",
        ]
        if errors:
            lines.append(f"[bold red]错误:[/] {len(errors)} 项")
            for e in errors[:3]:
                lines.append(f"  [red]•[/] {e}")
        console.print(Panel("\n".join(lines), title=f"🔌 连接器运行 ({source})", border_style=style))
        return

    if "stats" in result and "total_runs" in result.get("stats", {}):
        stats = result["stats"]
        lines = [
            f"[bold]总运行:[/] {stats.get('total_runs', 0)}",
            f"[bold]发现:[/] {stats.get('total_found', 0)} 项",
            f"[bold]导入:[/] [green]{stats.get('total_imported', 0)}[/] 项",
            f"[bold]错误:[/] {stats.get('total_errors', 0)}",
        ]
        by_source = stats.get("by_source", {})
        if by_source:
            lines.append("")
            lines.append("[bold]按来源:[/]")
            for src, s in by_source.items():
                lines.append(f"  {src}: {s.get('imported', 0)}/{s.get('found', 0)} 项")
        console.print(Panel("\n".join(lines), title="📊 连接器统计", border_style="blue"))
        return

    # ── Review rendering ──
    if "report" in result:
        report = result.get("report", {})
        if "summary" in report:
            summary = report["summary"]
            lines = [
                f"[bold]总意图:[/] {summary.get('total_intents', 0)}",
                f"[bold]待审批:[/] [yellow]{summary.get('pending', 0)}[/]",
                f"[bold]已通过:[/] [green]{summary.get('approved', 0)}[/]",
                f"[bold]已拒绝:[/] [red]{summary.get('rejected', 0)}[/]",
                f"[bold]准确率:[/] {summary.get('accuracy', 0) * 100:.1f}%",
                f"[bold]节省时间:[/] [green]{summary.get('time_saved_hours', 0)}[/] 小时",
            ]
            dist = report.get("distribution", {})
            if dist.get("by_source"):
                lines.append("")
                lines.append("[bold]来源分布:[/]")
                for src, cnt in dist["by_source"].items():
                    lines.append(f"  {src}: {cnt}")
            if dist.get("by_priority"):
                lines.append("")
                lines.append("[bold]优先级分布:[/]")
                for pri, cnt in dist["by_priority"].items():
                    lines.append(f"  {pri}: {cnt}")
            console.print(Panel("\n".join(lines), title="📊 复盘报告", border_style="green"))
            return

        if "pilot_name" in report:
            scenes = report.get("scenes", [])
            total = report.get("total_intents", 0)
            lines = [
                f"[bold]试点:[/] {report.get('pilot_name', '')}",
                f"[bold]周期:[/] {report.get('pilot_duration', '')}",
                f"[bold]场景数:[/] {len(scenes)}",
                f"[bold]总意图:[/] {total}",
            ]
            for s in scenes:
                lines.append(f"  • {s.get('name', '')}: {s.get('intent_count', 0)} 意图")
            console.print(Panel("\n".join(lines), title="🚀 试点总结报告", border_style="blue"))
            return

    # 兜底: 未知 scenario 退回 JSON
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
