"""
model_driven.toolchain.derivation_engine — 推导规则执行引擎

将 DR-01~DR-15 推导规则和 Trigger 专用规则转为可执行的检查函数。
每条规则返回 DerivationResult，包含是否触发、风险级别、详细信息。

DR-01~DR-15 规则已提取到 derivation_rules.py 中。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from model_driven.constants import (
    DAEMON_STUCK_MULTIPLIER,
    DEFAULT_DAEMON_INTERVAL,
    DEFAULT_MAX_RETRIES,
    EVENT_BUS_QUEUE_THRESHOLD,
)
from model_driven.toolchain.derivation_rules import DerivationResult, DerivationRules


class DerivationEngine:
    """推导规则执行引擎 — 激活 DR-01~DR-15 和 Trigger 规则为可执行检查"""

    def __init__(self):
        self._rules = DerivationRules()
        self._results: list[DerivationResult] = []
        self._trigger_results: list[DerivationResult] = []

    def execute_all(
        self, models: list[dict[str, Any]], context: dict[str, Any] | None = None
    ) -> list[DerivationResult]:
        """执行所有推导规则"""
        context = context or {}
        by_type = self._index_by_type(models)

        # DR-01~DR-15
        self._rules.execute_all(by_type, context)

        # DR-TRIGGER-01~05 + DEP (触发机制推导)
        triggers = by_type.get("trigger", [])
        if triggers:
            self.execute_trigger_rules(triggers, context)

        self._results = self._rules.results + self._trigger_results
        return self._results

    def _index_by_type(self, models: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """按类型索引模型"""
        idx: dict[str, list[dict[str, Any]]] = {}
        for m in models:
            mtype = m.get("type", "unknown")
            idx.setdefault(mtype, []).append(m)
        return idx

    def get_summary(self) -> dict[str, Any]:
        """获取执行摘要"""
        triggered = [r for r in self._results if r.triggered]
        by_level: dict[str, int] = {}
        for r in triggered:
            by_level[r.risk_level] = by_level.get(r.risk_level, 0) + 1

        return {
            "total_rules": len(self._results),
            "triggered": len(triggered),
            "not_triggered": len(self._results) - len(triggered),
            "by_risk_level": by_level,
            "high_risks": [r for r in triggered if r.risk_level in ("high", "critical")],
            "executed_at": datetime.now(UTC).isoformat(),
        }

    # ── DR-TRIGGER: 触发机制推导规则 ─────────────────────────

    def execute_trigger_rules(
        self, trigger_nodes: list[dict[str, Any]], context: dict[str, Any] | None = None
    ) -> list[DerivationResult]:
        """执行 Trigger 专用推导规则 (DR-TRIGGER-01~05 + DEP)"""
        self._trigger_results.clear()
        context = context or {}
        trigger_status = context.get("trigger_status", {})
        by_id = {t.get("id"): t for t in trigger_nodes}

        self._check_cron_triggers(trigger_nodes, context)
        self._check_watchdog_triggers(trigger_nodes, context)
        self._check_git_hook_triggers(trigger_nodes, context)
        self._check_event_bus_triggers(trigger_nodes, context)
        self._check_daemon_triggers(trigger_nodes, context)
        self._check_trigger_dependencies(trigger_nodes, trigger_status, by_id)

        return self._trigger_results

    def _check_cron_triggers(self, trigger_nodes: list, context: dict) -> None:
        for ct in trigger_nodes:
            if ct.get("properties", {}).get("trigger_type") != "cron":
                continue
            last_exec = context.get(f"last_exec_{ct['id']}", "")
            expected_next = context.get(f"expected_next_{ct['id']}", "")
            if last_exec and expected_next and last_exec > expected_next:
                self._trigger_results.append(
                    DerivationResult(
                        "DR-TRIGGER-01", "Cron 任务超时未执行 → 调度器健康风险",
                        True, "high", f"Trigger {ct['id']} 超时未执行",
                        details={"trigger": ct["id"], "action": "register_debt"},
                    )
                )

    def _check_watchdog_triggers(self, trigger_nodes: list, context: dict) -> None:
        for wt in trigger_nodes:
            if wt.get("properties", {}).get("trigger_type") != "watchdog":
                continue
            failures = context.get(f"failures_{wt['id']}", 0)
            max_failures = wt.get("properties", {}).get("retry_policy", {}).get("max_retries", DEFAULT_MAX_RETRIES)
            if failures >= max_failures:
                self._trigger_results.append(
                    DerivationResult(
                        "DR-TRIGGER-02", "Watchdog 连续失败超过阈值 → 服务不可用风险",
                        True, "critical", f"Trigger {wt['id']} 连续失败 {failures}/{max_failures}",
                        details={"trigger": wt["id"], "failures": failures, "action": "auto_restart"},
                    )
                )

    def _check_git_hook_triggers(self, trigger_nodes: list, context: dict) -> None:
        for gh in trigger_nodes:
            if gh.get("properties", {}).get("trigger_type") != "git_hook":
                continue
            extraction_status = context.get(f"extraction_{gh['id']}", "unknown")
            if extraction_status == "failed":
                self._trigger_results.append(
                    DerivationResult(
                        "DR-TRIGGER-03", "Git Hook 触发但 MOF 萃取失败 → 知识丢失风险",
                        True, "high", f"Trigger {gh['id']} MOF 萃取失败",
                        details={"trigger": gh["id"], "action": "retry_extraction"},
                    )
                )

    def _check_event_bus_triggers(self, trigger_nodes: list, context: dict) -> None:
        for eb in trigger_nodes:
            if eb.get("properties", {}).get("trigger_type") != "event_bus":
                continue
            queue_size = context.get(f"queue_{eb['id']}", 0)
            if queue_size > EVENT_BUS_QUEUE_THRESHOLD:
                self._trigger_results.append(
                    DerivationResult(
                        "DR-TRIGGER-04", "EventBus 事件积压超过阈值 → 事件处理延迟风险",
                        True, "high", f"Trigger {eb['id']} 事件积压 {queue_size}",
                        details={"trigger": eb["id"], "queue_size": queue_size, "action": "truncate_events"},
                    )
                )

    def _check_daemon_triggers(self, trigger_nodes: list, context: dict) -> None:
        for dt in trigger_nodes:
            if dt.get("properties", {}).get("trigger_type") != "daemon":
                continue
            interval = dt.get("properties", {}).get("interval_seconds", DEFAULT_DAEMON_INTERVAL)
            last_duration = context.get(f"duration_{dt['id']}", 0)
            if last_duration > DAEMON_STUCK_MULTIPLIER * interval:
                self._trigger_results.append(
                    DerivationResult(
                        "DR-TRIGGER-05", "Daemon 周期超过预期 2 倍 → 守护进程卡死风险",
                        True, "critical", f"Trigger {dt['id']} 周期 {last_duration}s > {DAEMON_STUCK_MULTIPLIER * interval}s",
                        details={"trigger": dt["id"], "duration": last_duration, "action": "restart_daemon"},
                    )
                )

    def _check_trigger_dependencies(self, trigger_nodes: list, trigger_status: dict, by_id: dict) -> None:
        for trigger in trigger_nodes:
            deps = trigger.get("properties", {}).get("dependencies", [])
            for dep_id in deps:
                dep_status = trigger_status.get(dep_id, "unknown")
                if dep_status != "healthy":
                    self._trigger_results.append(
                        DerivationResult(
                            "DR-TRIGGER-DEP",
                            f"Trigger 依赖检查: {trigger['id']} → {dep_id}",
                            True, "high",
                            f"Trigger {trigger['id']} 依赖 {dep_id} 状态为 {dep_status}",
                            details={
                                "trigger": trigger["id"], "dependency": dep_id,
                                "dep_status": dep_status, "action": "block_and_heal",
                            },
                        )
                    )

    def execute_trigger_driven_heal(self, high_risk_triggers: list[DerivationResult]) -> list[dict[str, Any]]:
        """闭环驱动: 对高风险 Trigger 执行自动修复"""
        heal_actions = []
        try:
            from model_driven.management.omo_bridge import OMOBridge

            bridge = OMOBridge()
            for risk in high_risk_triggers:
                action = risk.details.get("action", "")
                trigger_id = risk.details.get("trigger", "")
                self._do_heal_action(bridge, action, trigger_id, risk, heal_actions)
        except ImportError:
            pass
        return heal_actions

    def execute_trigger_driven_heal_dict(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """闭环驱动 (dict 版本) — 供 TriggerRegistry.run_heal() 调用"""
        heal_actions = []
        try:
            from model_driven.management.omo_bridge import OMOBridge

            bridge = OMOBridge()
            for f in findings:
                action = f.get("details", {}).get("action", "")
                trigger_id = f.get("details", {}).get("trigger", "")
                risk_level = f.get("risk_level", "medium")
                message = f.get("message", "")
                queue_size = f.get("details", {}).get("queue_size", 0)
                dependency = f.get("details", {}).get("dependency", "")
                dep_status = f.get("details", {}).get("dep_status", "")

                if action == "register_debt":
                    debt = bridge.register_debt_and_persist(
                        title=f"Trigger 超时: {trigger_id}", description=message, severity=risk_level,
                    )
                    heal_actions.append({"type": "debt_registered", "trigger": trigger_id, "debt": debt})
                elif action in ("auto_restart", "restart_daemon"):
                    task = bridge.create_task_and_persist(
                        title=f"重启 Trigger: {trigger_id}", description=message, priority="P0",
                    )
                    heal_actions.append({"type": "restart_task_created", "trigger": trigger_id, "task": task})
                elif action == "block_and_heal":
                    bridge.record_audit_and_persist(
                        "trigger_dependency_blocked", "trigger", trigger_id,
                        {"dependency": dependency, "status": dep_status},
                    )
                    heal_actions.append({"type": "audit_recorded", "trigger": trigger_id})
                elif action == "truncate_events":
                    task = bridge.create_task_and_persist(
                        title=f"清理事件积压: {trigger_id}",
                        description=f"事件队列超过阈值: {queue_size}", priority="P1",
                    )
                    heal_actions.append({"type": "cleanup_task_created", "trigger": trigger_id, "task": task})
        except ImportError:
            pass
        return heal_actions

    def _do_heal_action(self, bridge, action: str, trigger_id: str, risk: DerivationResult, heal_actions: list) -> None:
        """执行单个修复动作"""
        if action == "register_debt":
            debt = bridge.register_debt_and_persist(
                title=f"Trigger 超时: {trigger_id}", description=risk.message, severity=risk.risk_level,
            )
            heal_actions.append({"type": "debt_registered", "trigger": trigger_id, "debt": debt})
        elif action in ("auto_restart", "restart_daemon"):
            task = bridge.create_task_and_persist(
                title=f"重启 Trigger: {trigger_id}", description=risk.message, priority="P0",
            )
            heal_actions.append({"type": "restart_task_created", "trigger": trigger_id, "task": task})
        elif action == "block_and_heal":
            bridge.record_audit_and_persist(
                "trigger_dependency_blocked", "trigger", trigger_id,
                {"dependency": risk.details.get("dependency"), "status": risk.details.get("dep_status")},
            )
            heal_actions.append({"type": "audit_recorded", "trigger": trigger_id})
        elif action == "truncate_events":
            task = bridge.create_task_and_persist(
                title=f"清理事件积压: {trigger_id}",
                description=f"事件队列超过阈值: {risk.details.get('queue_size', 0)}", priority="P1",
            )
            heal_actions.append({"type": "cleanup_task_created", "trigger": trigger_id, "task": task})
