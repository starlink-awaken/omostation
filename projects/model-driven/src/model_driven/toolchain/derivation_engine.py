"""
model_driven.toolchain.derivation_engine — 推导规则执行引擎

将 ontology.yaml (DR-01~DR-08) 和 ontology_extended.py (DR-09~DR-15) 中
定义的推导规则转为可执行的 Python 检查函数。

每条规则返回 DerivationResult，包含是否触发、风险级别、详细信息。

M0 运行时快照:
- TriggerRuntimeSnapshot: Trigger 的 M0 层运行时状态记录
- TriggerM0Manager: M0 快照管理 (保存/加载/漂移检测/健康聚合)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from model_driven.mof.m3_extended import LifecycleStage


@dataclass
class DerivationResult:
    """单条推导规则的执行结果"""

    rule_id: str
    rule_description: str
    triggered: bool = False
    risk_level: str = "none"  # none/low/medium/high/critical
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DerivationEngine:
    """推导规则执行引擎 — 激活 DR-01~DR-15 为可执行检查"""

    def __init__(self):
        self._results: list[DerivationResult] = []

    def execute_all(self, models: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[DerivationResult]:
        """执行所有推导规则"""
        self._results = []
        context = context or {}
        by_type = self._index_by_type(models)

        # DR-01~DR-08 (来自 ecos ontology.yaml)
        self._dr01(by_type, context)
        self._dr02(by_type, context)
        self._dr03(by_type, context)
        self._dr04(by_type, context)
        self._dr05(by_type, context)
        self._dr06(by_type, context)
        self._dr07(by_type, context)
        self._dr08(by_type, context)

        # DR-09~DR-15 (来自 model-driven ontology_extended.py)
        self._dr09(by_type, context)
        self._dr10(by_type, context)
        self._dr11(by_type, context)
        self._dr12(by_type, context)
        self._dr13(by_type, context)
        self._dr14(by_type, context)
        self._dr15(by_type, context)

        # DR-TRIGGER-01~05 + DEP (触发机制推导)
        triggers = by_type.get("trigger", [])
        if triggers:
            self.execute_trigger_rules(triggers, context)

        return self._results

    def _index_by_type(self, models: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """按类型索引模型"""
        idx: dict[str, list[dict[str, Any]]] = {}
        for m in models:
            mtype = m.get("type", "unknown")
            idx.setdefault(mtype, []).append(m)
        return idx

    def _add_result(self, rule_id: str, description: str, triggered: bool, level: str = "none", message: str = "", **details) -> None:
        self._results.append(DerivationResult(
            rule_id=rule_id,
            rule_description=description,
            triggered=triggered,
            risk_level=level,
            message=message,
            details=details,
        ))

    # ── DR-01: 组件使用的协议衰减 → 组件存在协议风险 ────────────

    def _dr01(self, by_type: dict, ctx: dict) -> None:
        components = by_type.get("component", []) + by_type.get("Component", [])
        protocols = by_type.get("protocol", []) + by_type.get("Protocol", [])

        protocol_status = {p.get("id"): p.get("status", "") for p in protocols}
        triggered = False

        for comp in components:
            for proto_id in comp.get("properties", {}).get("protocols", []):
                status = protocol_status.get(proto_id, "")
                if status in ("aging", "deprecated"):
                    triggered = True
                    self._add_result("DR-01", "组件使用的协议衰减 → 组件存在协议风险",
                                     True, "medium",
                                     f"组件 {comp.get('id')} 使用衰减协议 {proto_id} (status={status})",
                                     component=comp.get("id"), protocol=proto_id, protocol_status=status)

        if not triggered:
            self._add_result("DR-01", "组件使用的协议衰减 → 组件存在协议风险", False)

    # ── DR-02: 核心域无成本归因 → 价值盲区 ──────────────────────

    def _dr02(self, by_type: dict, ctx: dict) -> None:
        entities = by_type.get("entity", []) + by_type.get("Entity", [])
        costs = by_type.get("cost_model", []) + by_type.get("CostModel", [])
        cost_entities = {c.get("properties", {}).get("attribution_target", "") for c in costs}
        triggered = False

        tier_1_domains = ctx.get("tier_1_domains", ["family", "work", "meta"])
        for entity in entities:
            domain = entity.get("domain", "")
            if domain in tier_1_domains and entity.get("id") not in cost_entities:
                triggered = True
                self._add_result("DR-02", "核心域无成本归因 → 价值盲区",
                                 True, "high",
                                 f"实体 {entity.get('id')} (domain={domain}) 无成本归因",
                                 entity=entity.get("id"), domain=domain)

        if not triggered:
            self._add_result("DR-02", "核心域无成本归因 → 价值盲区", False)

    # ── DR-03: 规范约束未关联校验器 → 空转约束 ──────────────────

    def _dr03(self, by_type: dict, ctx: dict) -> None:
        specs = by_type.get("specification", []) + by_type.get("Specification", [])
        triggered = False

        for spec in specs:
            constraints = spec.get("properties", {}).get("constraints", [])
            validator = spec.get("properties", {}).get("validator", "")
            if constraints and not validator:
                triggered = True
                self._add_result("DR-03", "规范约束未关联校验器 → 空转约束",
                                 True, "medium",
                                 f"规范 {spec.get('id')} 有 {len(constraints)} 条约束但无校验器",
                                 spec=spec.get("id"), constraint_count=len(constraints))

        if not triggered:
            self._add_result("DR-03", "规范约束未关联校验器 → 空转约束", False)

    # ── DR-04: 架构演化但模型未更新 → 模型漂移 ──────────────────

    def _dr04(self, by_type: dict, ctx: dict) -> None:
        architectures = by_type.get("architecture", []) + by_type.get("Architecture", [])
        models = by_type.get("model", []) + by_type.get("Model", [])
        triggered = False

        for arch in architectures:
            if arch.get("status") in ("evolving", "active"):
                arch_updated = arch.get("updated", arch.get("created", ""))
                for model in models:
                    model_updated = model.get("updated", model.get("created", ""))
                    if arch_updated > model_updated:
                        triggered = True
                        self._add_result("DR-04", "架构演化但模型未更新 → 模型漂移",
                                         True, "high",
                                         f"架构 {arch.get('id')} 已更新 ({arch_updated}) 但模型 {model.get('id')} 未同步 ({model_updated})",
                                         architecture=arch.get("id"), model=model.get("id"))

        if not triggered:
            self._add_result("DR-04", "架构演化但模型未更新 → 模型漂移", False)

    # ── DR-05: 机制停止但依赖组件仍活跃 → 僵尸依赖 ──────────────

    def _dr05(self, by_type: dict, ctx: dict) -> None:
        mechanisms = by_type.get("mechanism", []) + by_type.get("Mechanism", [])
        components = by_type.get("component", []) + by_type.get("Component", [])
        triggered = False

        stopped_mechanisms = {m.get("id") for m in mechanisms if m.get("status") == "stopped"}
        for comp in components:
            deps = comp.get("properties", {}).get("depends_on", [])
            for dep in deps:
                if dep in stopped_mechanisms:
                    triggered = True
                    self._add_result("DR-05", "机制停止但依赖组件仍活跃 → 僵尸依赖",
                                     True, "medium",
                                     f"组件 {comp.get('id')} 依赖已停止的机制 {dep}",
                                     component=comp.get("id"), mechanism=dep)

        if not triggered:
            self._add_result("DR-05", "机制停止但依赖组件仍活跃 → 僵尸依赖", False)

    # ── DR-06: 被约束反向推导约束源 ──────────────────────────────

    def _dr06(self, by_type: dict, ctx: dict) -> None:
        constraints = by_type.get("constraint", []) + by_type.get("Constraint", [])
        constraint_mgmt = by_type.get("constraint_mgmt", []) + by_type.get("ConstraintMgmt", [])

        for cm in constraint_mgmt:
            blocks = cm.get("properties", {}).get("blocks", [])
            if blocks:
                self._add_result("DR-06", "被约束反向推导约束源",
                                 True, "low",
                                 f"约束管理 {cm.get('id')} 阻塞了 {len(blocks)} 个目标",
                                 source=cm.get("id"), blocked_targets=blocks)

        if not constraint_mgmt:
            self._add_result("DR-06", "被约束反向推导约束源", False)

    # ── DR-07: SSOT 来源反向推导引用者 ───────────────────────────

    def _dr07(self, by_type: dict, ctx: dict) -> None:
        entities = by_type.get("entity", []) + by_type.get("Entity", [])
        triggered = False

        # 构建引用关系
        source_refs: dict[str, list[str]] = {}
        for entity in entities:
            for source in entity.get("properties", {}).get("sources", []):
                source_refs.setdefault(source, []).append(entity.get("id", "unknown"))

        for source, referencers in source_refs.items():
            if len(referencers) > 0:
                triggered = True
                self._add_result("DR-07", "SSOT 来源反向推导引用者",
                                 True, "low",
                                 f"源 {source} 被 {len(referencers)} 个实体引用",
                                 source=source, referenced_by=referencers)

        if not triggered:
            self._add_result("DR-07", "SSOT 来源反向推导引用者", False)

    # ── DR-08: M1 节点缺失检测 ───────────────────────────────────

    def _dr08(self, by_type: dict, ctx: dict) -> None:
        from model_driven.mof.m2_lifecycle import ALL_M2_SCHEMAS

        triggered = False
        for m2_type, schema in ALL_M2_SCHEMAS.items():
            if schema.examples:
                m1_count = len(by_type.get(m2_type, []))
                if m1_count == 0:
                    triggered = True
                    self._add_result("DR-08", "M1 节点缺失检测",
                                     True, "medium",
                                     f"M2 类型 '{m2_type}' 有示例但无 M1 节点",
                                     m2_type=m2_type, coverage="missing")

        if not triggered:
            self._add_result("DR-08", "M1 节点缺失检测", False)

    # ── DR-09: OKR 进度滞后 → 规划态风险 ─────────────────────────

    def _dr09(self, by_type: dict, ctx: dict) -> None:
        okrs = by_type.get("okr", []) + by_type.get("Goal", [])
        expected_progress = ctx.get("expected_progress", 0.5)
        triggered = False

        for okr in okrs:
            progress = okr.get("properties", {}).get("progress", okr.get("progress", 1.0))
            if progress < expected_progress:
                triggered = True
                self._add_result("DR-09", "OKR 进度滞后 → 规划态风险",
                                 True, "high",
                                 f"OKR {okr.get('id')} 进度 {progress:.0%} < 期望 {expected_progress:.0%}",
                                 okr=okr.get("id"), progress=progress, expected=expected_progress)

        if not triggered:
            self._add_result("DR-09", "OKR 进度滞后 → 规划态风险", False)

    # ── DR-10: ADR 未关联 Spec → 设计漂移风险 ────────────────────

    def _dr10(self, by_type: dict, ctx: dict) -> None:
        adrs = by_type.get("adr", []) + by_type.get("Decision", [])
        triggered = False

        for adr in adrs:
            related = adr.get("properties", {}).get("related_specs", [])
            if not related:
                triggered = True
                self._add_result("DR-10", "ADR 未关联 Spec → 设计漂移风险",
                                 True, "medium",
                                 f"ADR {adr.get('id')} 未关联任何 Spec",
                                 adr=adr.get("id"))

        if not triggered:
            self._add_result("DR-10", "ADR 未关联 Spec → 设计漂移风险", False)

    # ── DR-11: 测试覆盖率低于阈值 → 开发态风险 ───────────────────

    def _dr11(self, by_type: dict, ctx: dict) -> None:
        code_modules = by_type.get("code_module", [])
        threshold = ctx.get("test_coverage_threshold", 80.0)
        triggered = False

        for mod in code_modules:
            coverage = mod.get("properties", {}).get("test_coverage", 100.0)
            if coverage < threshold:
                triggered = True
                self._add_result("DR-11", "测试覆盖率低于阈值 → 开发态风险",
                                 True, "high",
                                 f"模块 {mod.get('id')} 覆盖率 {coverage}% < {threshold}%",
                                 module=mod.get("id"), coverage=coverage, threshold=threshold)

        if not triggered:
            self._add_result("DR-11", "测试覆盖率低于阈值 → 开发态风险", False)

    # ── DR-12: 部署无回滚计划 → 部署态风险 ───────────────────────

    def _dr12(self, by_type: dict, ctx: dict) -> None:
        release_plans = by_type.get("release_plan", [])
        triggered = False

        for rp in release_plans:
            rollback = rp.get("properties", {}).get("rollback_plan", "")
            if not rollback:
                triggered = True
                self._add_result("DR-12", "部署无回滚计划 → 部署态风险",
                                 True, "high",
                                 f"发布计划 {rp.get('id')} 无回滚计划",
                                 release_plan=rp.get("id"))

        if not triggered:
            self._add_result("DR-12", "部署无回滚计划 → 部署态风险", False)

    # ── DR-13: 告警规则无关联运行手册 → 运行态风险 ───────────────

    def _dr13(self, by_type: dict, ctx: dict) -> None:
        alert_rules = by_type.get("alert_rule", [])
        triggered = False

        for ar in alert_rules:
            runbook = ar.get("properties", {}).get("runbook_ref", "")
            if not runbook:
                triggered = True
                self._add_result("DR-13", "告警规则无关联运行手册 → 运行态风险",
                                 True, "medium",
                                 f"告警规则 {ar.get('id')} 无关联运行手册",
                                 alert_rule=ar.get("id"))

        if not triggered:
            self._add_result("DR-13", "告警规则无关联运行手册 → 运行态风险", False)

    # ── DR-14: 事件未复盘 → 运维态风险 ────────────────────────────

    def _dr14(self, by_type: dict, ctx: dict) -> None:
        incidents = by_type.get("incident", [])
        triggered = False

        for inc in incidents:
            if inc.get("status") == "resolved":
                postmortem = inc.get("properties", {}).get("postmortem", "")
                if not postmortem:
                    triggered = True
                    self._add_result("DR-14", "事件未复盘 → 运维态风险",
                                     True, "medium",
                                     f"事件 {inc.get('id')} 已解决但未复盘",
                                     incident=inc.get("id"))

        if not triggered:
            self._add_result("DR-14", "事件未复盘 → 运维态风险", False)

    # ── DR-15: 价值流存在瓶颈 → 运营态风险 ────────────────────────

    def _dr15(self, by_type: dict, ctx: dict) -> None:
        value_streams = by_type.get("value_stream", [])
        triggered = False

        for vs in value_streams:
            bottlenecks = vs.get("properties", {}).get("bottlenecks", [])
            if bottlenecks:
                triggered = True
                self._add_result("DR-15", "价值流存在瓶颈 → 运营态风险",
                                 True, "medium",
                                 f"价值流 {vs.get('id')} 存在 {len(bottlenecks)} 个瓶颈",
                                 value_stream=vs.get("id"), bottleneck_count=len(bottlenecks))

        if not triggered:
            self._add_result("DR-15", "价值流存在瓶颈 → 运营态风险", False)

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
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── DR-TRIGGER: 触发机制推导规则 ─────────────────────────

    def execute_trigger_rules(self, trigger_nodes: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[DerivationResult]:
        """执行 Trigger 专用推导规则 (DR-TRIGGER-01~05)

        这些规则体现模型驱动的"驱动"本质：
        - 运行时检查 Trigger 依赖是否满足
        - 发现问题时自动注册 OMO Debt
        - 形成"检测→债务→修复→验证"闭环
        """
        context = context or {}
        trigger_status = context.get("trigger_status", {})

        # 按 ID 索引
        by_id = {t.get("id"): t for t in trigger_nodes}

        # DR-TRIGGER-01: Cron 任务超时未执行 → 调度器健康风险
        cron_triggers = [t for t in trigger_nodes if t.get("properties", {}).get("trigger_type") == "cron"]
        for ct in cron_triggers:
            last_exec = context.get(f"last_exec_{ct['id']}", "")
            expected_next = context.get(f"expected_next_{ct['id']}", "")
            if last_exec and expected_next and last_exec > expected_next:
                self._add_result("DR-TRIGGER-01", "Cron 任务超时未执行 → 调度器健康风险",
                                 True, "high",
                                 f"Trigger {ct['id']} 超时未执行",
                                 trigger=ct["id"], action="register_debt")

        # DR-TRIGGER-02: Watchdog 连续失败超过阈值 → 服务不可用风险
        watchdog_triggers = [t for t in trigger_nodes if t.get("properties", {}).get("trigger_type") == "watchdog"]
        for wt in watchdog_triggers:
            failures = context.get(f"failures_{wt['id']}", 0)
            max_failures = wt.get("properties", {}).get("retry_policy", {}).get("max_retries", 3)
            if failures >= max_failures:
                self._add_result("DR-TRIGGER-02", "Watchdog 连续失败超过阈值 → 服务不可用风险",
                                 True, "critical",
                                 f"Trigger {wt['id']} 连续失败 {failures}/{max_failures}",
                                 trigger=wt["id"], failures=failures, action="auto_restart")

        # DR-TRIGGER-03: Git Hook 触发但 MOF 萃取失败 → 知识丢失风险
        git_hooks = [t for t in trigger_nodes if t.get("properties", {}).get("trigger_type") == "git_hook"]
        for gh in git_hooks:
            extraction_status = context.get(f"extraction_{gh['id']}", "unknown")
            if extraction_status == "failed":
                self._add_result("DR-TRIGGER-03", "Git Hook 触发但 MOF 萃取失败 → 知识丢失风险",
                                 True, "high",
                                 f"Trigger {gh['id']} MOF 萃取失败",
                                 trigger=gh["id"], action="retry_extraction")

        # DR-TRIGGER-04: EventBus 事件积压超过阈值 → 事件处理延迟风险
        event_buses = [t for t in trigger_nodes if t.get("properties", {}).get("trigger_type") == "event_bus"]
        for eb in event_buses:
            queue_size = context.get(f"queue_{eb['id']}", 0)
            if queue_size > 1000:
                self._add_result("DR-TRIGGER-04", "EventBus 事件积压超过阈值 → 事件处理延迟风险",
                                 True, "high",
                                 f"Trigger {eb['id']} 事件积压 {queue_size}",
                                 trigger=eb["id"], queue_size=queue_size, action="truncate_events")

        # DR-TRIGGER-05: Daemon 周期超过预期 2 倍 → 守护进程卡死风险
        daemon_triggers = [t for t in trigger_nodes if t.get("properties", {}).get("trigger_type") == "daemon"]
        for dt in daemon_triggers:
            interval = dt.get("properties", {}).get("interval_seconds", 21600)
            last_duration = context.get(f"duration_{dt['id']}", 0)
            if last_duration > 2 * interval:
                self._add_result("DR-TRIGGER-05", "Daemon 周期超过预期 2 倍 → 守护进程卡死风险",
                                 True, "critical",
                                 f"Trigger {dt['id']} 周期 {last_duration}s > {2*interval}s",
                                 trigger=dt["id"], duration=last_duration, action="restart_daemon")

        # DR-TRIGGER-DEP: 运行时依赖检查 (模型驱动的"驱动"核心)
        for trigger in trigger_nodes:
            deps = trigger.get("properties", {}).get("dependencies", [])
            for dep_id in deps:
                dep_status = trigger_status.get(dep_id, "unknown")
                if dep_status != "healthy":
                    dep = by_id.get(dep_id, {})
                    self._add_result("DR-TRIGGER-DEP",
                                     f"Trigger 依赖检查: {trigger['id']} → {dep_id}",
                                     True, "high",
                                     f"Trigger {trigger['id']} 依赖 {dep_id} 状态为 {dep_status}",
                                     trigger=trigger["id"], dependency=dep_id, dep_status=dep_status,
                                     action="block_and_heal")

        return [r for r in self._results if r.rule_id.startswith("DR-TRIGGER")]

    def execute_trigger_driven_heal(self, high_risk_triggers: list[DerivationResult]) -> list[dict[str, Any]]:
        """闭环驱动: 对高风险 Trigger 执行自动修复

        模型驱动的"驱动"体现在这里：
        - 不是只报告问题，而是自动触发修复
        - 修复动作通过 OMOBridge 注册为 Debt/Task
        - 下次 daemon 循环验证修复是否生效
        """
        heal_actions = []
        try:
            from model_driven.management.omo_bridge import OMOBridge
            bridge = OMOBridge()

            for risk in high_risk_triggers:
                action = risk.details.get("action", "")
                trigger_id = risk.details.get("trigger", "")

                if action == "register_debt":
                    debt = bridge.register_debt_and_persist(
                        title=f"Trigger 超时: {trigger_id}",
                        description=risk.message,
                        severity=risk.risk_level,
                    )
                    heal_actions.append({"type": "debt_registered", "trigger": trigger_id, "debt": debt})

                elif action == "auto_restart" or action == "restart_daemon":
                    task = bridge.create_task_and_persist(
                        title=f"重启 Trigger: {trigger_id}",
                        description=risk.message,
                        priority="P0",
                    )
                    heal_actions.append({"type": "restart_task_created", "trigger": trigger_id, "task": task})

                elif action == "block_and_heal":
                    bridge.record_audit_and_persist(
                        "trigger_dependency_blocked",
                        "trigger",
                        trigger_id,
                        {"dependency": risk.details.get("dependency"), "status": risk.details.get("dep_status")},
                    )
                    heal_actions.append({"type": "audit_recorded", "trigger": trigger_id})

                elif action == "truncate_events":
                    task = bridge.create_task_and_persist(
                        title=f"清理事件积压: {trigger_id}",
                        description=f"事件队列超过阈值: {risk.details.get('queue_size', 0)}",
                        priority="P1",
                    )
                    heal_actions.append({"type": "cleanup_task_created", "trigger": trigger_id, "task": task})

        except ImportError:
            pass  # OMOBridge 不可用时静默跳过

        return heal_actions


# ── M0 运行时快照: TriggerRuntimeSnapshot ────────────────


@dataclass
class TriggerRuntimeSnapshot:
    """Trigger M0 运行时快照 — 记录 Trigger 的实际执行状态

    对应 MOF 四层模型中的 M0 层:
    - M3: BehavioralElement.Mechanism
    - M2: trigger
    - M1: TRIGGER-ECOS-DAEMON 等 10 个节点
    - M0: TriggerRuntimeSnapshot (本类)
    """

    trigger_id: str
    status: str = "unknown"  # healthy/degraded/stopped/unknown
    last_execution: str = ""
    last_duration_seconds: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    health_score: float = 100.0  # 0-100
    snapshotted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "status": self.status,
            "last_execution": self.last_execution,
            "last_duration_seconds": self.last_duration_seconds,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "health_score": self.health_score,
            "snapshotted_at": self.snapshotted_at,
            "metadata": self.metadata,
        }


class TriggerM0Manager:
    """Trigger M0 运行时管理器

    职责:
    1. 生成 Trigger 的 M0 运行时快照
    2. 保存快照到文件 (.omo/state/model-driven/trigger-m0-snapshot.yaml)
    3. 加载快照与 M1 声明对比检测漂移
    4. 更新 Trigger 健康分
    """

    def __init__(self, state_dir: str | None = None):
        if state_dir is None:
            from pathlib import Path
            self._state_dir = Path.home() / "Workspace" / ".omo" / "state" / "model-driven"
        else:
            self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_file = self._state_dir / "trigger-m0-snapshot.yaml"
        self._snapshots: dict[str, TriggerRuntimeSnapshot] = {}

    def record_execution(
        self,
        trigger_id: str,
        success: bool,
        duration_seconds: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> TriggerRuntimeSnapshot:
        """记录一次 Trigger 执行"""
        if trigger_id in self._snapshots:
            snap = self._snapshots[trigger_id]
        else:
            snap = TriggerRuntimeSnapshot(trigger_id=trigger_id)

        snap.last_execution = datetime.now(timezone.utc).isoformat()
        snap.last_duration_seconds = duration_seconds
        snap.metadata.update(metadata or {})

        if success:
            snap.consecutive_successes += 1
            snap.consecutive_failures = 0
            snap.health_score = min(100.0, snap.health_score + 5.0)
            if snap.consecutive_successes >= 3:
                snap.status = "healthy"
        else:
            snap.consecutive_failures += 1
            snap.consecutive_successes = 0
            snap.health_score = max(0.0, snap.health_score - 20.0)
            if snap.consecutive_failures >= 3:
                snap.status = "degraded"
            if snap.consecutive_failures >= 5:
                snap.status = "stopped"

        snap.snapshotted_at = datetime.now(timezone.utc).isoformat()
        self._snapshots[trigger_id] = snap
        return snap

    def get_snapshot(self, trigger_id: str) -> TriggerRuntimeSnapshot | None:
        return self._snapshots.get(trigger_id)

    def get_all_snapshots(self) -> dict[str, TriggerRuntimeSnapshot]:
        return self._snapshots.copy()

    def save(self) -> bool:
        """保存 M0 快照到文件"""
        try:
            import yaml
            data = {
                "m0_type": "trigger_runtime_snapshot",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "triggers": {
                    tid: snap.to_dict()
                    for tid, snap in self._snapshots.items()
                },
            }
            with open(self._snapshot_file, "w") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception:
            return False

    def load(self) -> bool:
        """从文件加载 M0 快照"""
        if not self._snapshot_file.exists():
            return False
        try:
            import yaml
            with open(self._snapshot_file) as f:
                data = yaml.safe_load(f)
            if not data or "triggers" not in data:
                return False
            for tid, snap_data in data["triggers"].items():
                snap = TriggerRuntimeSnapshot(
                    trigger_id=tid,
                    status=snap_data.get("status", "unknown"),
                    last_execution=snap_data.get("last_execution", ""),
                    last_duration_seconds=snap_data.get("last_duration_seconds", 0.0),
                    consecutive_failures=snap_data.get("consecutive_failures", 0),
                    consecutive_successes=snap_data.get("consecutive_successes", 0),
                    health_score=snap_data.get("health_score", 100.0),
                    snapshotted_at=snap_data.get("snapshotted_at", ""),
                    metadata=snap_data.get("metadata", {}),
                )
                self._snapshots[tid] = snap
            return True
        except Exception:
            return False

    def detect_drift(
        self, m1_triggers: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """M1 声明 vs M0 实际状态 漂移检测

        这是 MOF 模型驱动的核心:
        - M1 声明 trigger 应该是 active
        - M0 实际状态可能是 degraded/stopped
        - 漂移 = M1 期望 ≠ M0 实际
        """
        drifts = []
        for m1 in m1_triggers:
            tid = m1.get("id", "")
            m1_status = m1.get("status", "active")
            m0 = self._snapshots.get(tid)

            if m0 is None:
                drifts.append({
                    "trigger_id": tid,
                    "type": "missing_m0_snapshot",
                    "m1_status": m1_status,
                    "m0_status": "unknown",
                    "severity": "warning",
                    "message": f"Trigger {tid} 无 M0 运行时快照",
                })
            elif m0.status != "healthy" and m1_status == "active":
                drifts.append({
                    "trigger_id": tid,
                    "type": "status_drift",
                    "m1_status": m1_status,
                    "m0_status": m0.status,
                    "severity": "high",
                    "health_score": m0.health_score,
                    "consecutive_failures": m0.consecutive_failures,
                    "message": f"Trigger {tid}: M1={m1_status}, M0={m0.status} (health={m0.health_score})",
                })

        return drifts

    def get_health_summary(self) -> dict[str, Any]:
        """获取 Trigger M0 健康摘要"""
        total = len(self._snapshots)
        healthy = sum(1 for s in self._snapshots.values() if s.status == "healthy")
        degraded = sum(1 for s in self._snapshots.values() if s.status == "degraded")
        stopped = sum(1 for s in self._snapshots.values() if s.status == "stopped")

        return {
            "total_triggers": total,
            "healthy": healthy,
            "degraded": degraded,
            "stopped": stopped,
            "health_pct": round(healthy / total * 100, 1) if total > 0 else 0,
            "triggers": {
                tid: {
                    "status": snap.status,
                    "health_score": snap.health_score,
                    "consecutive_failures": snap.consecutive_failures,
                    "last_execution": snap.last_execution,
                }
                for tid, snap in self._snapshots.items()
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_health_summary(self) -> dict[str, Any]:
        """获取 Trigger M0 健康摘要"""
        total = len(self._snapshots)
        healthy = sum(1 for s in self._snapshots.values() if s.status == "healthy")
        degraded = sum(1 for s in self._snapshots.values() if s.status == "degraded")
        stopped = sum(1 for s in self._snapshots.values() if s.status == "stopped")

        return {
            "total_triggers": total,
            "healthy": healthy,
            "degraded": degraded,
            "stopped": stopped,
            "health_pct": round(healthy / total * 100, 1) if total > 0 else 0,
            "triggers": {
                tid: {
                    "status": snap.status,
                    "health_score": snap.health_score,
                    "consecutive_failures": snap.consecutive_failures,
                    "last_execution": snap.last_execution,
                }
                for tid, snap in self._snapshots.items()
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
