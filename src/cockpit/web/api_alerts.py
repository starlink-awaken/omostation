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
from pydantic import BaseModel

from cockpit.compat import WORKSPACE_ROOT

router = APIRouter()

# L4-kernel 项目路径
WORKSPACE_DIR = WORKSPACE_ROOT
L4_KERNEL_DIR = WORKSPACE_DIR / "projects" / "l4-kernel"

# 内存存储（生产环境应使用数据库）
alerts_store: list[dict] = []
rules_store: list[dict] = []


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


@router.get("/api/alerts/{alert_id}")
async def get_alert(alert_id: str):
    """获取告警详情。"""
    alerts = generate_alerts_from_l4_data()
    for alert in alerts:
        if alert["id"] == alert_id:
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")


class AcknowledgeRequest(BaseModel):
    comment: str | None = None


@router.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: AcknowledgeRequest):
    """确认告警。"""
    return {
        "id": alert_id,
        "status": "acknowledged",
        "acknowledged_by": "admin",
        "acknowledged_at": datetime.now(UTC).isoformat(),
        "comment": request.comment,
    }


class SilenceRequest(BaseModel):
    duration: int = 60
    reason: str | None = None


@router.post("/api/alerts/{alert_id}/silence")
async def silence_alert(alert_id: str, request: SilenceRequest):
    """静默告警。"""
    return {
        "id": alert_id,
        "status": "silenced",
        "silenced_until": datetime.now(UTC).isoformat(),
        "duration": request.duration,
        "reason": request.reason,
    }


class ResolveRequest(BaseModel):
    comment: str | None = None


@router.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, request: ResolveRequest):
    """解决告警。"""
    return {
        "id": alert_id,
        "status": "resolved",
        "resolved_by": "admin",
        "resolved_at": datetime.now(UTC).isoformat(),
        "comment": request.comment,
    }


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

    return {
        "items": default_rules,
        "total": len(default_rules),
    }


class CreateRuleRequest(BaseModel):
    name: str
    condition: str
    level: str = "warning"
    channels: list[str] = ["slack"]
    enabled: bool = True


@router.post("/api/alerts/rules")
async def create_alert_rule(request: CreateRuleRequest):
    """创建告警规则。"""
    rule = {
        "id": f"rule-{len(rules_store) + 1}",
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
