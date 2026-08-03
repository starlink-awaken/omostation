"""Alerts API endpoints.

提供告警管理功能。

Routes:
    GET    /api/alerts                    → 告警列表
    GET    /api/alerts/:id                → 告警详情
    POST   /api/alerts/:id/acknowledge    → 确认告警
    POST   /api/alerts/:id/silence        → 静默告警
    POST   /api/alerts/:id/resolve        → 解决告警
    GET    /api/alerts/rules              → 告警规则列表
    POST   /api/alerts/rules              → 创建告警规则
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from cockpit.compat import WORKSPACE_ROOT

router = APIRouter()

# L4-kernel 项目路径
WORKSPACE_DIR = WORKSPACE_ROOT
L4_KERNEL_DIR = WORKSPACE_DIR / "projects" / "l4-kernel"

# 内存存储（生产环境应使用数据库）
alerts_store: list[dict] = []
rules_store: list[dict] = []
alert_state_store: dict[str, dict] = {}
rule_override_store: dict[str, dict] = {}


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


def generate_alerts_from_l4_data() -> list[dict]:
    """从 L4 健康数据生成告警。"""
    l4_data = run_l4_script("health_monitor.py", ["--output", "json"])
    signal_data = run_l4_script("signal_analysis.py", ["--hours", "72", "--output", "json"])

    alerts = []
    now = datetime.now(UTC).isoformat()

    if l4_data:
        # 检查不健康的域
        for domain in l4_data.get("domains", []):
            if not domain.get("fresh", True):
                alerts.append(
                    {
                        "id": f"alert-{domain['id']}-health",
                        "level": "error",
                        "source": "L4 Health",
                        "message": f"{domain['id']} 域不健康",
                        "description": f"检测到 {domain['id']} 域存在 {domain.get('issue_count', 0)} 个问题",
                        "status": "active",
                        "created_at": now,
                        "updated_at": now,
                    }
                )

        # 检查信号数异常
        for domain in l4_data.get("domains", []):
            if domain.get("signal_count", 0) > 100:
                alerts.append(
                    {
                        "id": f"alert-{domain['id']}-signals",
                        "level": "warning",
                        "source": "L4 Health",
                        "message": f"{domain['id']} 域信号数异常 ({domain['signal_count']}个)",
                        "description": f"{domain['id']} 域信号数量超过阈值，可能存在异常",
                        "status": "active",
                        "created_at": now,
                        "updated_at": now,
                    }
                )

    if signal_data:
        # 检查信号风险
        for risk in signal_data.get("risks", []):
            alerts.append(
                {
                    "id": f"alert-risk-{len(alerts)}",
                    "level": risk.get("severity", "warning"),
                    "source": "Signal Analysis",
                    "message": risk.get("message", "检测到风险"),
                    "description": f"信号分析检测到风险: {risk.get('risk', 'unknown')}",
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                }
            )

    return alerts


@router.get("/api/alerts")
async def get_alerts(
    status: str | None = Query(None, description="告警状态过滤"),
    level: str | None = Query(None, description="告警级别过滤"),
    limit: int = Query(100, description="返回数量限制"),
):
    """获取告警列表。"""
    # 从 L4 数据生成告警
    alerts = generate_alerts_from_l4_data()

    # Overlay operator state so the next refresh does not erase an acknowledgement.
    for alert in alerts:
        alert.update(alert_state_store.get(alert["id"], {}))

    # 过滤
    if status:
        alerts = [a for a in alerts if a["status"] == status]
    if level:
        alerts = [a for a in alerts if a["level"] == level]

    # 限制数量
    alerts = alerts[:limit]

    return {
        "items": alerts,
        "total": len(alerts),
    }


class AcknowledgeRequest(BaseModel):
    comment: str | None = None


@router.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: AcknowledgeRequest):
    """确认告警。"""
    payload = {
        "id": alert_id,
        "status": "acknowledged",
        "acknowledged_by": "admin",
        "acknowledged_at": datetime.now(UTC).isoformat(),
        "comment": request.comment,
    }
    alert_state_store[alert_id] = payload
    return payload


class SilenceRequest(BaseModel):
    duration: int = 60
    reason: str | None = None


@router.post("/api/alerts/{alert_id}/silence")
async def silence_alert(alert_id: str, request: SilenceRequest):
    """静默告警。"""
    payload = {
        "id": alert_id,
        "status": "silenced",
        "silenced_until": datetime.now(UTC).isoformat(),
        "duration": request.duration,
        "reason": request.reason,
    }
    alert_state_store[alert_id] = payload
    return payload


class ResolveRequest(BaseModel):
    comment: str | None = None


@router.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, request: ResolveRequest):
    """解决告警。"""
    payload = {
        "id": alert_id,
        "status": "resolved",
        "resolved_by": "admin",
        "resolved_at": datetime.now(UTC).isoformat(),
        "comment": request.comment,
    }
    alert_state_store[alert_id] = payload
    return payload


@router.get("/api/alerts/rules")
async def get_alert_rules():
    """获取告警规则列表。"""
    # 默认规则
    default_rules = [
        {
            "id": "rule-1",
            "name": "健康率下降",
            "condition": "health_rate < 100%",
            "level": "error",
            "channels": ["slack", "email"],
            "enabled": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
        {
            "id": "rule-2",
            "name": "信号数异常",
            "condition": "signal_count > 100",
            "level": "warning",
            "channels": ["slack"],
            "enabled": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
        {
            "id": "rule-3",
            "name": "域不健康",
            "condition": "fresh = false",
            "level": "error",
            "channels": ["slack", "email", "wechat"],
            "enabled": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
    ]

    merged = []
    for rule in default_rules:
        merged.append({**rule, **rule_override_store.get(rule["id"], {})})
    merged.extend(rules_store)
    return {"items": merged, "total": len(merged)}


class CreateRuleRequest(BaseModel):
    name: str
    condition: str
    level: str = "warning"
    channels: list[str] = Field(default_factory=lambda: ["slack"])
    enabled: bool = True


@router.post("/api/alerts/rules")
async def create_alert_rule(request: CreateRuleRequest):
    """创建告警规则。"""
    rule = {
        "id": f"custom-rule-{len(rules_store) + 1}",
        "name": request.name,
        "condition": request.condition,
        "level": request.level,
        "channels": request.channels,
        "enabled": request.enabled,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    rules_store.append(rule)
    return rule


class UpdateRuleRequest(BaseModel):
    enabled: bool | None = None
    name: str | None = None
    condition: str | None = None
    level: str | None = None
    channels: list[str] | None = None


@router.patch("/api/alerts/rules/{rule_id}")
async def update_alert_rule(rule_id: str, request: UpdateRuleRequest):
    """Update a custom rule or record a governed override for a built-in rule."""
    rule = next((item for item in rules_store if item["id"] == rule_id), None)
    if rule is None:
        current_rules = (await get_alert_rules())["items"]
        rule = next((item for item in current_rules if item["id"] == rule_id), None)
        if rule is None:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        changes = request.model_dump(exclude_unset=True)
        rule_override_store[rule_id] = {
            **rule_override_store.get(rule_id, {}),
            **{key: value for key, value in changes.items() if value is not None},
            "updated_at": datetime.now(UTC).isoformat(),
        }
        return {**rule, **rule_override_store[rule_id]}
    changes = request.model_dump(exclude_unset=True)
    rule.update({key: value for key, value in changes.items() if value is not None})
    rule["updated_at"] = datetime.now(UTC).isoformat()
    return rule


@router.get("/api/alerts/{alert_id}")
async def get_alert(alert_id: str):
    """获取告警详情。"""
    alerts = generate_alerts_from_l4_data()
    for alert in alerts:
        alert.update(alert_state_store.get(alert["id"], {}))
        if alert["id"] == alert_id:
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")


# ============================================================
# Triage endpoint — 分诊集成
# ============================================================

import urllib.request as _urllib_request


class TriageRequest(BaseModel):
    """分诊请求."""

    text: str = Field(..., description="待分诊文本")
    consensus: bool = Field(False, description="是否使用共识模式 (3模型投票)")


class TriageResponse(BaseModel):
    """分诊响应."""

    verdict: str = Field(..., description="分诊结果: 丢弃/沉淀/提醒")
    agreement: float = Field(1.0, description="一致率 (0-1)")
    status: str = Field("ok", description="状态: 共识/多数/分歧/错误")
    latency: float = Field(0.0, description="延迟 (秒)")
    error: str | None = Field(None, description="错误信息")


GATEWAY_URL = "http://100.96.126.35:4000/v1/chat/completions"
GATEWAY_KEY = "sk-omlx-admin"

TRIAGE_PROMPT = """你是信息分诊助手。判断: 丢弃 / 沉淀 / 提醒 三选一。

标准:
- 丢弃: 营销/广告/促销/社交动态/APP推送/续费推销
- 沉淀: 技术文章/知识教程/研究分析/笔记同步/课程更新 (有价值内容)
- 提醒: 会议/截止日期/账单/告警/待办/预约/需行动事项

示例:
【淘宝】5折→丢弃  【GitHub】新PR→沉淀  【日历】开会→提醒
【读书笔记】已同步→沉淀  【京东】续费优惠→丢弃  【银行】账单→提醒

信息: {text}
只输出一个词:"""


def _call_triage_model(model: str, text: str, needs_reasoning_off: bool = True) -> tuple[str, float]:
    """调用单个分诊模型."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": TRIAGE_PROMPT.format(text=text)}],
        "max_tokens": 20,
        "temperature": 0,
    }
    if needs_reasoning_off:
        payload["extra_body"] = {"reasoning_effort": "none"}

    data = json.dumps(payload).encode()
    req = _urllib_request.Request(
        GATEWAY_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GATEWAY_KEY}",
        },
    )

    import time as _time

    t0 = _time.time()
    try:
        with _urllib_request.urlopen(req, timeout=15) as resp:  # noqa: S310
            d = json.loads(resp.read())
        latency = _time.time() - t0
        content = d["choices"][0]["message"]["content"].strip()
        for v in ("丢弃", "沉淀", "提醒"):
            if v in content:
                return v, latency
        return "未知", latency
    except Exception:
        return "错误", _time.time() - t0


@router.post("/api/triage")
async def triage_notification(request: TriageRequest):
    """分诊通知 — 自动分类为 丢弃/沉淀/提醒.

    consensus=false: 单模型快速分诊 (~0.5s)
    consensus=true: 两级共识 (stage1 双模型并行 + stage2 分歧复核, ~1.5s)
    """
    import time as _time
    from concurrent.futures import ThreadPoolExecutor

    t0 = _time.time()

    if not request.consensus:
        # 单模型模式
        verdict, latency = _call_triage_model("triage", request.text)
        return TriageResponse(
            verdict=verdict,
            agreement=1.0,
            status="单模型",
            latency=latency,
            error="模型返回未知" if verdict == "未知" else None,
        )

    # 共识模式: stage1 双模型并行
    stage1_models = [("mid-local", True), ("mini-9b", True)]
    stage2_model = ("deepseek-chat", False)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_call_triage_model, m, request.text, off) for m, off in stage1_models]
        results = [f.result() for f in futures]

    votes: dict[str, int] = {}
    for verdict, _ in results:
        if verdict in ("丢弃", "沉淀", "提醒"):
            votes[verdict] = votes.get(verdict, 0) + 1

    max_verdict = max(votes, key=lambda k: votes[k]) if votes else "未知"
    max_count = max(votes.values()) if votes else 0

    # Stage 1 一致 → 直接返回
    if max_count == 2:
        return TriageResponse(
            verdict=max_verdict,
            agreement=1.0,
            status="共识",
            latency=_time.time() - t0,
            error=None,
        )

    # Stage 1 分歧 → 调 Stage 2
    verdict2, lat2 = _call_triage_model(stage2_model[0], request.text, stage2_model[1])
    if verdict2 in ("丢弃", "沉淀", "提醒"):
        votes[verdict2] = votes.get(verdict2, 0) + 1

    max_verdict = max(votes, key=lambda k: votes[k]) if votes else "未知"
    max_count = max(votes.values()) if votes else 0
    agreement = max_count / 3

    status = "共识" if agreement == 1.0 else ("多数" if agreement >= 2 / 3 else "分歧")

    return TriageResponse(
        verdict=max_verdict,
        agreement=agreement,
        status=status,
        latency=_time.time() - t0,
        error=None,
    )
