"""model_driven.toolchain.derivation_rules — 推导规则 DR-01~DR-15

从 derivation_engine.py 中提取，将 15 条推导规则作为独立函数，
供 DerivationEngine 和 TriggerRegistry 共用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from model_driven.constants import DEFAULT_COVERAGE_THRESHOLD, DEFAULT_EXPECTED_PROGRESS, MAX_HEALTH_SCORE


@dataclass
class DerivationResult:
    """单条推导规则的执行结果"""

    rule_id: str
    rule_description: str
    triggered: bool = False
    risk_level: str = "none"  # none/low/medium/high/critical
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    executed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class DerivationRules:
    """推导规则集合 — DR-01~DR-15 的可执行实现"""

    def __init__(self):
        self._results: list[DerivationResult] = []

    def _add_result(
        self, rule_id: str, description: str, triggered: bool, level: str = "none", message: str = "", **details
    ) -> None:
        self._results.append(
            DerivationResult(
                rule_id=rule_id,
                rule_description=description,
                triggered=triggered,
                risk_level=level,
                message=message,
                details=details,
            )
        )

    @property
    def results(self) -> list[DerivationResult]:
        return self._results

    def execute_all(self, by_type: dict[str, list[dict[str, Any]]], context: dict[str, Any] | None = None) -> list[DerivationResult]:
        """执行所有 15 条推导规则"""
        self._results.clear()
        context = context or {}

        self._dr01(by_type, context)
        self._dr02(by_type, context)
        self._dr03(by_type, context)
        self._dr04(by_type, context)
        self._dr05(by_type, context)
        self._dr06(by_type, context)
        self._dr07(by_type, context)
        self._dr08(by_type, context)
        self._dr09(by_type, context)
        self._dr10(by_type, context)
        self._dr11(by_type, context)
        self._dr12(by_type, context)
        self._dr13(by_type, context)
        self._dr14(by_type, context)
        self._dr15(by_type, context)

        return self._results

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
                    self._add_result(
                        "DR-01", "组件使用的协议衰减 → 组件存在协议风险",
                        True, "medium",
                        f"组件 {comp.get('id')} 使用衰减协议 {proto_id} (status={status})",
                        component=comp.get("id"), protocol=proto_id, protocol_status=status,
                    )
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
                self._add_result(
                    "DR-02", "核心域无成本归因 → 价值盲区", True, "high",
                    f"实体 {entity.get('id')} (domain={domain}) 无成本归因",
                    entity=entity.get("id"), domain=domain,
                )
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
                self._add_result(
                    "DR-03", "规范约束未关联校验器 → 空转约束", True, "medium",
                    f"规范 {spec.get('id')} 有 {len(constraints)} 条约束但无校验器",
                    spec=spec.get("id"), constraint_count=len(constraints),
                )
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
                        self._add_result(
                            "DR-04", "架构演化但模型未更新 → 模型漂移", True, "high",
                            f"架构 {arch.get('id')} 已更新 ({arch_updated}) 但模型 {model.get('id')} 未同步 ({model_updated})",
                            architecture=arch.get("id"), model=model.get("id"),
                        )
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
                    self._add_result(
                        "DR-05", "机制停止但依赖组件仍活跃 → 僵尸依赖", True, "medium",
                        f"组件 {comp.get('id')} 依赖已停止的机制 {dep}",
                        component=comp.get("id"), mechanism=dep,
                    )
        if not triggered:
            self._add_result("DR-05", "机制停止但依赖组件仍活跃 → 僵尸依赖", False)

    # ── DR-06: 被约束反向推导约束源 ──────────────────────────────

    def _dr06(self, by_type: dict, ctx: dict) -> None:
        constraint_mgmt = by_type.get("constraint_mgmt", []) + by_type.get("ConstraintMgmt", [])
        for cm in constraint_mgmt:
            blocks = cm.get("properties", {}).get("blocks", [])
            if blocks:
                self._add_result(
                    "DR-06", "被约束反向推导约束源", True, "low",
                    f"约束管理 {cm.get('id')} 阻塞了 {len(blocks)} 个目标",
                    source=cm.get("id"), blocked_targets=blocks,
                )
        if not constraint_mgmt:
            self._add_result("DR-06", "被约束反向推导约束源", False)

    # ── DR-07: SSOT 来源反向推导引用者 ───────────────────────────

    def _dr07(self, by_type: dict, ctx: dict) -> None:
        entities = by_type.get("entity", []) + by_type.get("Entity", [])
        triggered = False
        source_refs: dict[str, list[str]] = {}
        for entity in entities:
            for source in entity.get("properties", {}).get("sources", []):
                source_refs.setdefault(source, []).append(entity.get("id", "unknown"))
        for source, referencers in source_refs.items():
            if len(referencers) > 0:
                triggered = True
                self._add_result(
                    "DR-07", "SSOT 来源反向推导引用者", True, "low",
                    f"源 {source} 被 {len(referencers)} 个实体引用",
                    source=source, referenced_by=referencers,
                )
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
                    self._add_result(
                        "DR-08", "M1 节点缺失检测", True, "medium",
                        f"M2 类型 '{m2_type}' 有示例但无 M1 节点",
                        m2_type=m2_type, coverage="missing",
                    )
        if not triggered:
            self._add_result("DR-08", "M1 节点缺失检测", False)

    # ── DR-09: OKR 进度滞后 → 规划态风险 ─────────────────────────

    def _dr09(self, by_type: dict, ctx: dict) -> None:
        okrs = by_type.get("okr", []) + by_type.get("Goal", [])
        expected_progress = ctx.get("expected_progress", DEFAULT_EXPECTED_PROGRESS)
        triggered = False
        for okr in okrs:
            progress = okr.get("properties", {}).get("progress", okr.get("progress", 1.0))
            if progress < expected_progress:
                triggered = True
                self._add_result(
                    "DR-09", "OKR 进度滞后 → 规划态风险", True, "high",
                    f"OKR {okr.get('id')} 进度 {progress:.0%} < 期望 {expected_progress:.0%}",
                    okr=okr.get("id"), progress=progress, expected=expected_progress,
                )
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
                self._add_result(
                    "DR-10", "ADR 未关联 Spec → 设计漂移风险", True, "medium",
                    f"ADR {adr.get('id')} 未关联任何 Spec", adr=adr.get("id"),
                )
        if not triggered:
            self._add_result("DR-10", "ADR 未关联 Spec → 设计漂移风险", False)

    # ── DR-11: 测试覆盖率低于阈值 → 开发态风险 ───────────────────

    def _dr11(self, by_type: dict, ctx: dict) -> None:
        code_modules = by_type.get("code_module", [])
        threshold = ctx.get("test_coverage_threshold", DEFAULT_COVERAGE_THRESHOLD)
        triggered = False
        for mod in code_modules:
            coverage = mod.get("properties", {}).get("test_coverage", MAX_HEALTH_SCORE)
            if coverage < threshold:
                triggered = True
                self._add_result(
                    "DR-11", "测试覆盖率低于阈值 → 开发态风险", True, "high",
                    f"模块 {mod.get('id')} 覆盖率 {coverage}% < {threshold}%",
                    module=mod.get("id"), coverage=coverage, threshold=threshold,
                )
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
                self._add_result(
                    "DR-12", "部署无回滚计划 → 部署态风险", True, "high",
                    f"发布计划 {rp.get('id')} 无回滚计划", release_plan=rp.get("id"),
                )
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
                self._add_result(
                    "DR-13", "告警规则无关联运行手册 → 运行态风险", True, "medium",
                    f"告警规则 {ar.get('id')} 无关联运行手册", alert_rule=ar.get("id"),
                )
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
                    self._add_result(
                        "DR-14", "事件未复盘 → 运维态风险", True, "medium",
                        f"事件 {inc.get('id')} 已解决但未复盘", incident=inc.get("id"),
                    )
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
                self._add_result(
                    "DR-15", "价值流存在瓶颈 → 运营态风险", True, "medium",
                    f"价值流 {vs.get('id')} 存在 {len(bottlenecks)} 个瓶颈",
                    value_stream=vs.get("id"), bottleneck_count=len(bottlenecks),
                )
        if not triggered:
            self._add_result("DR-15", "价值流存在瓶颈 → 运营态风险", False)
