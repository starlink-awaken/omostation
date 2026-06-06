"""
OMO 自愈代谢引擎 (Self-Healing Metabolism Engine)

Phase 38-39: 从被动监听升级为主动自愈。
- 监听 Agora SSE 事件流
- 滑动窗口统计错误事件
- 阈值触发 MetaOS 工作流 → 生成 Debt 报告 → 尝试自动修复
- 支持自定义修复脚本 (omo_self_healing_fixes.py)
- HTTP 状态端点 + Agora 事件发布

架构:
    Agora SSE ──→ ErrorEventCounter ──→ HealingRuleEngine ──→ MetaOS Workflow
                                                │
                                    ┌───────────┼───────────┐
                                    ▼           ▼           ▼
                               Debt 报告    Auto-Fix     Agora Event
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
        action: 触发动作 (debt | workflow | fix | both)
        cooldown_seconds: 冷却时间，避免重复触发
        workflow_id: 关联的 MetaOS 工作流 ID (可选)
        fix_names: 关联的修复脚本名称列表 (来自 FIX_REGISTRY)
        publish_event: 是否向 Agora 发布事件
        description: 规则描述
    """

    name: str
    event_types: list[str] = field(default_factory=list)
    threshold: int = 5
    severity: str = "warning"
    action: str = "debt"  # debt | workflow | fix | both
    cooldown_seconds: int = 600
    workflow_id: str = ""
    fix_names: list[str] = field(default_factory=list)
    publish_event: bool = True
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
        fix_names=["process_health_check"],
        description="系统错误/审计失败/健康下降时触发审计+债务+进程检查",
    ),
    HealingRule(
        name="import_failure_chain",
        event_types=["IMPORT_ERROR", "MODULE_NOT_FOUND"],
        threshold=5,
        severity="high",
        action="debt",
        cooldown_seconds=1800,
        description="导入错误频发时生成债务",
    ),
    HealingRule(
        name="timeout_cascade",
        event_types=["TIMEOUT", "CONNECTION_TIMEOUT", "SSE_DISCONNECT"],
        threshold=5,
        severity="high",
        action="both",
        cooldown_seconds=600,
        fix_names=["restart_agora", "clear_pytest_cache"],
        description="超时事件激增时重启Agora+清理缓存",
    ),
    HealingRule(
        name="test_failure_alert",
        event_types=["TEST_FAILURE", "CI_FAILURE"],
        threshold=2,
        severity="warning",
        action="debt",
        cooldown_seconds=3600,
        description="CI 测试失败时生成债务",
    ),
    HealingRule(
        name="disk_quota_warning",
        event_types=["DISK_FULL", "QUOTA_EXCEEDED"],
        threshold=1,
        severity="critical",
        action="fix",
        fix_names=["disk_check", "clean_temp_files", "git_gc"],
        publish_event=False,
        description="磁盘告警立刻清理临时文件+磁盘检查",
    ),
    HealingRule(
        name="memory_pressure",
        event_types=["MEMORY_EXHAUSTED", "OOM_KILLED"],
        threshold=1,
        severity="critical",
        action="fix",
        cooldown_seconds=300,
        fix_names=["process_health_check", "clear_pytest_cache"],
        description="内存耗尽时进程健康检查+缓存清理",
    ),
    HealingRule(
        name="process_dead_alert",
        event_types=["PROCESS_DOWN", "SERVICE_UNREACHABLE"],
        threshold=1,
        severity="high",
        action="fix",
        cooldown_seconds=300,
        fix_names=["restart_agora", "process_health_check"],
        description="进程宕机时自动重启+健康检查",
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
        agora_event_url: str = "",
    ):
        self._counter = ErrorEventCounter(window_seconds=window_seconds)
        self._rules: list[HealingRule] = rules or DEFAULT_RULES
        self._triggered_count: dict[str, int] = {}
        self._fix_history: list[dict] = []
        self._agora_event_url = agora_event_url or os.environ.get(
            "AGORA_EVENT_URL", "http://127.0.0.1:8080/v1/events"
        )
        logger.info(
            "self_healing_engine_init rules=%s window_s=%s agora=%s",
            len(self._rules),
            window_seconds,
            self._agora_event_url,
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

            # Auto-fix execution
            if rule.fix_names:
                fix_results = await self._run_fixes(rule)
                for fr in fix_results:
                    actions.append({"type": "fix_executed", "result": fr})

            # Publish event to Agora
            if rule.publish_event:
                await self._publish_healing_event(rule, ev_type, count, actions)

            if actions:
                triggered.append({
                    "rule": rule.name,
                    "event_type": ev_type,
                    "count": count,
                    "actions": actions,
                })

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

    # ── Auto-Fix ───────────────────────────────────────────────────────

    async def _run_fixes(self, rule: HealingRule) -> list[dict]:
        """执行规则关联的修复脚本 (失败自动重试)。"""
        from omo.omo_self_healing_fixes import run_fix

        results = []
        for fix_name in rule.fix_names:
            result = run_fix(fix_name, {"rule": rule.name, "severity": rule.severity})
            # 失败自动重试 1 次
            if not result["success"]:
                logger.warning("fix_retrying fix=%s", fix_name)
                result = run_fix(fix_name, {"rule": rule.name, "severity": rule.severity, "retry": True})
            self._fix_history.append({
                "rule": rule.name,
                "fix_name": fix_name,
                "success": result["success"],
                "output": result["output"][:200],
            })
            if len(self._fix_history) > 100:
                self._fix_history = self._fix_history[-100:]
            results.append(result)
        return results

    # ── Event Publishing ───────────────────────────────────────────────

    async def _publish_healing_event(
        self, rule: HealingRule, ev_type: str, count: int, actions: list[dict]
    ) -> None:
        """向 Agora 发布自愈事件。"""
        try:
            import json

            import httpx

            payload = {
                "type": "omo:healing:triggered",
                "rule": rule.name,
                "event_type": ev_type,
                "count": count,
                "severity": rule.severity,
                "actions": actions,
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                await client.post(
                    self._agora_event_url,
                    json=payload,
                )
        except Exception:
            pass  # 事件发布失败不影响主流程

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
            "fixes_executed": len(self._fix_history),
            "recent_fixes": self._fix_history[-5:],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════


def _severity_weight(severity: str) -> float:
    return {"critical": 10.0, "high": 7.0, "warning": 4.0, "info": 2.0}.get(severity, 4.0)


# ═══════════════════════════════════════════════════════════════════════════
# Trend Analysis
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class EventTrend:
    """事件趋势快照。"""

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    total_events: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    triggers: int = 0
    fixes: int = 0
    debts: int = 0


class TrendTracker:
    """追踪事件趋势 (10 个快照点)。"""

    def __init__(self, max_snapshots: int = 10):
        self._snapshots: deque[EventTrend] = deque(maxlen=max_snapshots)
        self._total_triggers: int = 0
        self._total_fixes: int = 0
        self._total_debts: int = 0

    def record(self, trend: EventTrend) -> None:
        self._snapshots.append(trend)
        self._total_triggers += trend.triggers
        self._total_fixes += trend.fixes
        self._total_debts += trend.debts

    def get_trends(self) -> list[dict]:
        return [
            {
                "ts": t.timestamp,
                "events": t.total_events,
                "by_type": t.events_by_type,
                "triggers": t.triggers,
                "fixes": t.fixes,
            }
            for t in self._snapshots
        ]

    def is_escalating(self, event_type: str) -> bool:
        """检测事件是否在升级 (最近 3 个快照连续增长)。"""
        if len(self._snapshots) < 3:
            return False
        recent = list(self._snapshots)[-3:]
        counts = [s.events_by_type.get(event_type, 0) for s in recent]
        return counts[0] < counts[1] < counts[2]


# ═══════════════════════════════════════════════════════════════════════════
# HTTP Health Server (status + fix execution)
# ═══════════════════════════════════════════════════════════════════════════

_HEALING_HTTP_PORT = int(os.environ.get("OMO_HEALING_HTTP_PORT", "9091"))


def start_http_status_server(engine: SelfHealingEngine | None = None) -> None:
    """在后台线程启动 HTTP 状态端点。

    Endpoints:
        GET /health           — {"status": "ok", "engine": ...}
        GET /status            — 自愈引擎完整状态
        GET /fixes             — 可用修复脚本列表
        POST /fix/run/<name>   — 手动触发一个修复
        GET /trends            — 趋势数据
    """
    if engine is None:
        engine = get_healing_engine()

    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler

        _engine_ref = engine

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    self._json(200, {"status": "ok", "engine": "omo-self-healing"})
                elif self.path == "/status":
                    self._json(200, _engine_ref.get_status())
                elif self.path == "/fixes":
                    from omo.omo_self_healing_fixes import list_fixes
                    self._json(200, {"fixes": list_fixes()})
                elif self.path == "/trends":
                    self._json(200, {"trends": _engine_ref._trends.get_trends()})
                else:
                    self._json(404, {"error": "not found"})

            def do_POST(self):
                if self.path.startswith("/fix/run/"):
                    fix_name = self.path.split("/fix/run/")[1]
                    from omo.omo_self_healing_fixes import run_fix
                    result = run_fix(fix_name)
                    self._json(200, result)
                else:
                    self._json(404, {"error": "not found"})

            def _json(self, code, data):
                import json
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "http://localhost:8090")
                self.end_headers()
                self.wfile.write(json.dumps(data, default=str).encode())

            def log_message(self, format, *args):
                pass  # suppress logs

        import threading
        server = HTTPServer(("127.0.0.1", _HEALING_HTTP_PORT), _Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True, name="healing-http")
        t.start()
        logger.info("healing_http_started port=%s", _HEALING_HTTP_PORT)
    except Exception:
        logger.warning("healing_http_start_failed — port may be in use")


# ═══════════════════════════════════════════════════════════════════════════
# Configuration Persistence
# ═══════════════════════════════════════════════════════════════════════════

HEALING_CONFIG_PATH = OMO_ROOT / ".omo" / "self_healing_rules.yaml"


def save_rules(rules: list[HealingRule], path: Path | None = None) -> None:
    """保存自定义规则到 YAML 配置文件。"""
    target = path or HEALING_CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for r in rules:
        data.append({
            "name": r.name,
            "event_types": r.event_types,
            "threshold": r.threshold,
            "severity": r.severity,
            "action": r.action,
            "cooldown_seconds": r.cooldown_seconds,
            "workflow_id": r.workflow_id,
            "fix_names": r.fix_names,
            "publish_event": r.publish_event,
            "description": r.description,
        })
    target.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    logger.info("healing_rules_saved path=%s count=%s", target, len(data))


def load_rules(path: Path | None = None) -> list[HealingRule]:
    """从 YAML 配置文件加载自定义规则。"""
    target = path or HEALING_CONFIG_PATH
    if not target.exists():
        return []
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or []
    rules = []
    for d in data:
        rules.append(HealingRule(
            name=d["name"],
            event_types=d.get("event_types", []),
            threshold=d.get("threshold", 5),
            severity=d.get("severity", "warning"),
            action=d.get("action", "debt"),
            cooldown_seconds=d.get("cooldown_seconds", 600),
            workflow_id=d.get("workflow_id", ""),
            fix_names=d.get("fix_names", []),
            publish_event=d.get("publish_event", True),
            description=d.get("description", ""),
        ))
    return rules


# ═══════════════════════════════════════════════════════════════════════════
# Module-level singleton
# ═══════════════════════════════════════════════════════════════════════════

_engine: SelfHealingEngine | None = None


def get_healing_engine() -> SelfHealingEngine:
    """获取全局自愈引擎实例（懒加载）。优先加载自定义规则。"""
    global _engine
    if _engine is None:
        custom_rules = load_rules()
        if custom_rules:
            _engine = SelfHealingEngine(rules=custom_rules)
            logger.info("healing_engine_loaded_custom_rules count=%s", len(custom_rules))
        else:
            _engine = SelfHealingEngine()
    return _engine
