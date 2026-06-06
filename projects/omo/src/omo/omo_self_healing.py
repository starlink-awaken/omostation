"""OMO 自愈代谢引擎 (Self-Healing Metabolism Engine)

Phase 38: 从被动监听升级为主动自愈。
- 监听 Agora SSE 事件流
- 滑动窗口统计错误事件
- 阈值触发 MetaOS 工作流 → 生成 Debt 报告 → 尝试自动修复

架构:
    Agora SSE ──→ ErrorEventCounter ──→ HealingRuleEngine ──→ MetaOS Workflow
                                                │
                                                └──→ Debt 报告生成
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

logger = logging.getLogger("omo.self_healing")


# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

OMO_ROOT = Path(os.environ.get("OMO_ROOT", Path.home() / "Workspace/projects/omo"))
DEBT_ITEMS_DIR = OMO_ROOT / ".omo" / "debt" / "items"
DEBT_REGISTRY = OMO_ROOT / ".omo" / "debt" / "registry.yaml"


# ═══════════════════════════════════════════════════════════════════════════
# Error Event Counter
# ═══════════════════════════════════════════════════════════════════════════


class ErrorEventCounter:
    """滑动窗口错误事件计数器。

    按事件类型分组计数，支持时间窗口过期清理。
    """

    def __init__(self, window_seconds: int = 300):
        self._window = timedelta(seconds=window_seconds)
        self._events: deque[tuple[str, float]] = deque()

    def record(self, event_type: str) -> None:
        """记录一个事件。"""
        now = time.monotonic()
        self._events.append((event_type, now))
        self._expire()

    def _expire(self) -> None:
        """清除窗口外的过期事件。"""
        cutoff = time.monotonic() - self._window.total_seconds()
        while self._events and self._events[0][1] < cutoff:
            self._events.popleft()

    def count(self, event_type: str | None = None) -> int:
        """返回窗口内事件计数。event_type=None 返回总数。"""
        self._expire()
        if event_type is None:
            return len(self._events)
        return sum(1 for t, _ in self._events if t == event_type)

    def by_type(self) -> dict[str, int]:
        """按事件类型分组计数。"""
        self._expire()
        counts: dict[str, int] = {}
        for ev_type, _ in self._events:
            counts[ev_type] = counts.get(ev_type, 0) + 1
        return counts

    def reset(self) -> None:
        self._events.clear()


# ═══════════════════════════════════════════════════════════════════════════
# Healing Rule
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class HealingRule:
    """自愈规则：当条件满足时触发动作。

    Attributes:
        name: 规则名称
        event_types: 匹配的事件类型列表 (空列表匹配所有)
        threshold: 窗口内最小事件数才触发
        severity: 生成的 Debt 严重级别
        action: 触发动作 (debt | workflow | both)
        cooldown_seconds: 冷却时间，避免重复触发
        workflow_id: 关联的 MetaOS 工作流 ID (可选)
    """

    name: str
    event_types: list[str] = field(default_factory=list)
    threshold: int = 5
    severity: str = "warning"
    action: str = "debt"  # debt | workflow | both
    cooldown_seconds: int = 600
    workflow_id: str = ""
    description: str = ""

    _last_triggered: float = field(default=0.0, init=False, repr=False)

    def matches(self, event_type: str) -> bool:
        return not self.event_types or event_type in self.event_types

    def is_cooled_down(self) -> bool:
        return time.monotonic() - self._last_triggered > self.cooldown_seconds

    def mark_triggered(self) -> None:
        self._last_triggered = time.monotonic()


# ═══════════════════════════════════════════════════════════════════════════
# Default Healing Rules
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_RULES: list[HealingRule] = [
    HealingRule(
        name="error_spike_audit",
        event_types=["SYSTEM_ERROR", "AUDIT_FAILURE", "HEALTH_DOWN"],
        threshold=3,
        severity="critical",
        action="both",
        cooldown_seconds=600,
        description="系统错误/审计失败/健康下降超过阈值时，自动触发审计 + 生成债务",
    ),
    HealingRule(
        name="import_failure_chain",
        event_types=["IMPORT_ERROR", "MODULE_NOT_FOUND"],
        threshold=5,
        severity="high",
        action="debt",
        cooldown_seconds=1800,
        description="导入错误频发时生成债务，提示检查依赖链",
    ),
    HealingRule(
        name="timeout_cascade",
        event_types=["TIMEOUT", "CONNECTION_TIMEOUT", "SSE_DISCONNECT"],
        threshold=5,
        severity="high",
        action="both",
        cooldown_seconds=600,
        description="超时事件激增时生成债务 + 尝试重启相关服务",
    ),
    HealingRule(
        name="test_failure_alert",
        event_types=["TEST_FAILURE", "CI_FAILURE"],
        threshold=2,
        severity="warning",
        action="debt",
        cooldown_seconds=3600,
        description="CI 测试失败时生成债务，追踪测试健康",
    ),
    HealingRule(
        name="disk_quota_warning",
        event_types=["DISK_FULL", "QUOTA_EXCEEDED"],
        threshold=1,
        severity="critical",
        action="debt",
        cooldown_seconds=300,
        description="磁盘/配额告警立刻生成严重债务",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# Self-Healing Engine
# ═══════════════════════════════════════════════════════════════════════════


class SelfHealingEngine:
    """OMO 自愈代谢核心引擎。

    职责：
    1. 接收并计数 SSE 事件
    2. 匹配规则并触发动作
    3. 生成 Debt 报告
    4. 触发 MetaOS 工作流
    """

    def __init__(
        self,
        rules: list[HealingRule] | None = None,
        window_seconds: int = 300,
    ):
        self._counter = ErrorEventCounter(window_seconds=window_seconds)
        self._rules: list[HealingRule] = rules or DEFAULT_RULES
        self._triggered_count: dict[str, int] = {}
        logger.info(
            "self_healing_engine_init rules=%s window_s=%s",
            len(self._rules),
            window_seconds,
        )

    # ── Event Handling ─────────────────────────────────────────────────

    async def on_event(self, event: dict) -> list[dict]:
        """处理一个 SSE 事件。返回触发的动作列表。"""
        ev_type = event.get("type", "UNKNOWN")
        self._counter.record(ev_type)

        triggered = []
        for rule in self._rules:
            if not rule.matches(ev_type):
                continue
            if not rule.is_cooled_down():
                continue

            count = self._counter.count(ev_type)
            if count < rule.threshold:
                continue

            logger.warning(
                "self_healing_rule_triggered rule=%s event_type=%s count=%s threshold=%s",
                rule.name,
                ev_type,
                count,
                rule.threshold,
            )

            rule.mark_triggered()
            self._triggered_count[rule.name] = self._triggered_count.get(rule.name, 0) + 1

            actions = []
            if rule.action in ("debt", "both"):
                debt_id = await self._create_debt(rule, ev_type, count)
                if debt_id:
                    actions.append({"type": "debt_created", "debt_id": debt_id})

            if rule.action in ("workflow", "both"):
                wf_result = await self._trigger_workflow(rule)
                actions.append({"type": "workflow_triggered", "result": wf_result})

            if actions:
                triggered.append(
                    {
                        "rule": rule.name,
                        "event_type": ev_type,
                        "count": count,
                        "actions": actions,
                    }
                )

        return triggered

    # ── Debt Creation ──────────────────────────────────────────────────

    async def _create_debt(self, rule: HealingRule, event_type: str, count: int) -> str | None:
        """基于规则和事件创建债务条目。"""
        debt_id = f"auto-{rule.name}-{int(time.time())}"
        now = datetime.now(UTC).isoformat()

        debt_data = {
            "id": debt_id,
            "title": f"[自动] {rule.description or rule.name}: {event_type} × {count}",
            "dimension": "operational",
            "subdimension": "auto_healing",
            "domain": "ecos",
            "scope": "auto_detected",
            "severity": rule.severity,
            "weight": _severity_weight(rule.severity),
            "entropy_class": "dynamic",
            "lifecycle_state": "open",
            "owner": "omo-self-healing",
            "affected_roots": ["omo", "agora"],
            "evidence_refs": [f"sse://event/{event_type}"],
            "mitigation_refs": [],
            "opened_at": now,
            "last_reviewed_at": None,
            "next_review_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "gate_level": "L1",
            "history": [
                {
                    "at": now,
                    "action": "created",
                    "trigger": f"self_healing_rule:{rule.name}",
                    "event_count": str(count),
                }
            ],
            "x1_policy_ref": "auto-healing-policy",
            "x2_freshness": "new",
            "x3_tier": rule.severity,
        }

        try:
            DEBT_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
            item_path = DEBT_ITEMS_DIR / f"{debt_id}.yaml"
            item_path.write_text(yaml.dump(debt_data, allow_unicode=True, sort_keys=False), encoding="utf-8")

            # 更新 registry
            self._append_to_registry(item_path)
            logger.info("self_healing_debt_created debt_id=%s path=%s", debt_id, str(item_path))
            return debt_id
        except Exception as exc:
            logger.error("self_healing_debt_create_failed error=%s", str(exc))
            return None

    def _append_to_registry(self, item_path: Path) -> None:
        """将新债务条目追加到 registry.yaml。"""
        if not DEBT_REGISTRY.exists():
            return

        try:
            registry = yaml.safe_load(DEBT_REGISTRY.read_text(encoding="utf-8")) or {}
            seed_items: list[str] = registry.get("seed_items", [])
            rel_path = str(item_path.relative_to(OMO_ROOT))
            if rel_path not in seed_items:
                seed_items.append(rel_path)
                registry["seed_items"] = seed_items
                DEBT_REGISTRY.write_text(
                    yaml.dump(registry, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
        except Exception as exc:
            logger.warning("self_healing_registry_update_failed error=%s", str(exc))

    # ── Workflow Trigger ───────────────────────────────────────────────

    async def _trigger_workflow(self, rule: HealingRule) -> dict:
        """触发 MetaOS 工作流。"""
        if not rule.workflow_id:
            return {"status": "skipped", "reason": "no workflow_id configured"}

        try:
            result = subprocess.run(
                ["metaos", "run", rule.workflow_id],
                capture_output=True,
                text=True,
                timeout=120,
            )
            logger.info(
                "self_healing_workflow_triggered workflow_id=%s returncode=%s",
                rule.workflow_id,
                result.returncode,
            )
            return {
                "status": "success" if result.returncode == 0 else "failed",
                "workflow_id": rule.workflow_id,
                "stdout": result.stdout[:500],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            logger.error("self_healing_workflow_timeout workflow_id=%s", rule.workflow_id)
            return {"status": "timeout", "workflow_id": rule.workflow_id}
        except Exception as exc:
            logger.error("self_healing_workflow_error error=%s", str(exc))
            return {"status": "error", "error": str(exc)}

    # ── Status ────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """返回自愈引擎当前状态。"""
        return {
            "rules_configured": len(self._rules),
            "total_triggers": sum(self._triggered_count.values()),
            "by_rule": dict(self._triggered_count),
            "event_window_s": self._counter._window.total_seconds(),
            "current_events": self._counter.count(),
            "events_by_type": self._counter.by_type(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════


def _severity_weight(severity: str) -> float:
    return {"critical": 10.0, "high": 7.0, "warning": 4.0, "info": 2.0}.get(severity, 4.0)


# ═══════════════════════════════════════════════════════════════════════════
# Module-level singleton (for daemon integration)
# ═══════════════════════════════════════════════════════════════════════════

_engine: SelfHealingEngine | None = None


def get_healing_engine() -> SelfHealingEngine:
    """获取全局自愈引擎实例（懒加载）。"""
    global _engine
    if _engine is None:
        _engine = SelfHealingEngine()
    return _engine
