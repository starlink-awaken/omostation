"""Event Listener — BOS URI 事件监听与工作流自动触发

监听 Agora SSE 事件流，匹配 M1 节点的 relations.triggers 定义，
自动触发对应工作流。

架构:
  Agora SSE (:7431) / events.jsonl
    → event_listener.match(event)
    → matched M1 trigger → execute_m1_workflow()
    → on failure → auto-heal
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("ecos.workflow.event_listener")

# M1 工作流触发器注册表: {event_bos_uri: [workflow_id, ...]}
_trigger_registry: dict[str, list[str]] = {}

# 自愈工作流名称
_HEAL_WORKFLOW = "WORKFLOW-ECOS-DAILY-HEALTH"


# =========================================================================
# 触发器注册表构建
# =========================================================================


def build_trigger_registry() -> dict[str, list[str]]:
    """从 M1 节点与 definitions 目录构建触发器注册表"""
    from ecos.workflow.loader import list_workflows, load_workflow

    registry: dict[str, list[str]] = {}

    all_workflows = list_workflows()
    for wf_meta in all_workflows:
        wf_id = wf_meta.get("id") or wf_meta.get("name", "")
        wf = load_workflow(wf_id)
        if not wf:
            continue

        # 1. 扫描 M1 relations.triggers
        relations = wf.get("relations", [])
        if isinstance(relations, list):
            for rel in relations:
                if rel.get("type") == "triggers":
                    target = rel.get("target", "")
                    if target:
                        registry.setdefault(target, []).append(wf_id)
        elif isinstance(relations, dict):
            triggers = relations.get("triggers", [])
            for rel in triggers if isinstance(triggers, list) else []:
                target = rel.get("to", rel.get("target", ""))
                if target:
                    registry.setdefault(target, []).append(wf_id)

        # 2. 扫描 definitions 中的 root-level trigger 字段 (如 trigger: QuestCompleted)
        trigger = wf.get("trigger")
        if trigger and isinstance(trigger, str):
            registry.setdefault(trigger, []).append(wf_id)

    logger.info(
        "Trigger registry built: %d triggers → %d workflows",
        len(registry),
        len(all_workflows),
    )
    return registry


# =========================================================================
# 事件匹配引擎
# =========================================================================


def match_event(event: dict, registry: dict[str, list[str]] | None = None) -> list[str]:
    """匹配单条事件到工作流

    Args:
        event: 事件 dict，至少包含 bos_uri 或 source/target 字段
        registry: 触发器注册表（None 时自动构建）

    Returns:
        匹配到的 workflow_id 列表
    """
    if registry is None:
        registry = _trigger_registry or build_trigger_registry()

    matched: list[str] = []

    # 从多种字段提取 BOS URI
    event_uri = (
        event.get("bos_uri", "") or event.get("uri", "") or event.get("source", "")
    )

    if not event_uri:
        return matched

    # 精确匹配
    if event_uri in registry:
        matched.extend(registry[event_uri])

    # 前缀匹配: bos://memory/kos/search 匹配 bos://memory/*
    for trigger_uri, wf_ids in registry.items():
        if trigger_uri.endswith("/*") and event_uri.startswith(trigger_uri[:-2]):
            matched.extend(wf_ids)
        elif trigger_uri.endswith("/**") and event_uri.startswith(trigger_uri[:-3]):
            matched.extend(wf_ids)

    # 去重
    return list(set(matched))


# =========================================================================
# 事件执行器
# =========================================================================


def execute_matched(event: dict, dry_run: bool = False) -> list[dict]:
    """匹配并执行事件触发的所有工作流

    Args:
        event: 事件 dict
        dry_run: 干跑模式（只列不跑）

    Returns:
        执行结果列表
    """
    from ecos.workflow.executor import execute_m1_workflow

    wf_ids = match_event(event)
    results: list[dict] = []

    if not wf_ids:
        return results

    for wf_id in wf_ids:
        logger.info(
            "Event triggered workflow: %s → %s",
            event.get("bos_uri", event.get("source", "unknown")),
            wf_id,
        )
        result = execute_m1_workflow(
            wf_id, params={"trigger_event": event}, dry_run=dry_run
        )
        result["triggered_by"] = wf_id
        results.append(result)

        # 如果工作流失败，触发自愈
        if result.get("failed", 0) > 0 and not dry_run:
            _trigger_heal(wf_id, result)

    return results


# =========================================================================
# 自愈机制
# =========================================================================


def _trigger_heal(failed_workflow_id: str, failed_result: dict) -> dict | None:
    """触发自愈工作流

    当工作流执行失败时，自动运行日常健康巡检
    来检测和修复系统状态。
    """
    from ecos.workflow.executor import execute_m1_workflow

    logger.warning("Triggering heal workflow for failed: %s", failed_workflow_id)

    # 加载自愈工作流
    if not load_workflow(_HEAL_WORKFLOW):
        # 如果没有自愈工作流定义，直接跑健康检查步骤
        logger.info("No heal workflow defined, running health check")
        from ecos.workflow.executor import _execute_step

        return _execute_step("health_check")

    return execute_m1_workflow(
        _HEAL_WORKFLOW,
        params={
            "heal_target": failed_workflow_id,
            "heal_reason": f"Workflow {failed_workflow_id} failed: "
            f"{failed_result.get('failed', 0)} steps failed",
        },
    )


def load_workflow(name: str) -> dict | None:
    """加载工作流（与 loader 一致）"""
    from ecos.workflow.loader import load_workflow as _load

    return _load(name)


# =========================================================================
# 后台监听循环
# =========================================================================


def listen_forever(
    interval: float = 30.0,
    source: str = "agora_sse",
    agora_url: str = "http://127.0.0.1:7432",
    dry_run: bool = False,
) -> None:
    """持续监听事件源并触发工作流

    Args:
        interval: 轮询间隔（秒）
        source: 事件源类型 ('events.jsonl', 'agora_sse', 'jsonl_file')
        agora_url: Agora SSE 地址
        dry_run: 干跑模式
    """
    logger.info("Starting event listener (interval=%ss, source=%s)", interval, source)

    # 构建触发器注册表
    registry = build_trigger_registry()
    logger.info("Trigger registry: %d patterns registered", len(registry))

    # 事件源
    events_file = Path.home() / ".ecos" / "events.jsonl"

    if source == "agora_sse":
        _listen_agora_sse(agora_url, registry, dry_run)
    else:
        _poll_jsonl(events_file, registry, interval, dry_run)


def _poll_jsonl(
    events_file: Path, registry: dict[str, list[str]], interval: float, dry_run: bool
) -> None:
    """轮询 JSONL 事件文件"""
    last_position = events_file.stat().st_size if events_file.exists() else 0

    while True:
        time.sleep(interval)

        if not events_file.exists():
            continue

        current_size = events_file.stat().st_size
        if current_size <= last_position:
            continue

        # 读取新行
        with open(events_file) as f:
            f.seek(last_position)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    wf_ids = match_event(event, registry)
                    if wf_ids:
                        logger.info(
                            "Event matched %s: %s", wf_ids, event.get("bos_uri", "")
                        )
                        if not dry_run:
                            execute_matched(event)
                except (json.JSONDecodeError, Exception) as e:  # defensive fallback
                    logger.warning("Failed to process event: %s", e)

        last_position = current_size


def _listen_agora_sse(
    agora_url: str, registry: dict[str, list[str]], dry_run: bool
) -> None:
    """监听 Agora SSE 事件流（粘性重连）"""
    import httpx

    sse_url = f"{agora_url}/v1/events"
    logger.info("Connecting to Agora SSE: %s", sse_url)

    while True:
        try:
            with httpx.stream("GET", sse_url, timeout=None) as response:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            wf_ids = match_event(event, registry)
                            if wf_ids:
                                logger.info(
                                    "SSE event matched %s: %s",
                                    wf_ids,
                                    event.get("bos_uri", ""),
                                )
                                if not dry_run:
                                    execute_matched(event)
                        except json.JSONDecodeError:
                            continue
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("SSE disconnected: %s, reconnecting in 10s...", e)
            time.sleep(10)
