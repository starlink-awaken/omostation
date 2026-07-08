"""eCOS Dashboard — data providers for CLI and cockpit routes.

HTTP server removed — dashboard converged to cockpit :8090.
Data functions remain available for CLI use: `ecos dashboard --json`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

import yaml

ECOS_HOME = Path(
    os.environ.get("ECOS_HOME", str(Path.home() / "Workspace" / "projects" / "ecos"))
)
DATA_DIR = Path(
    os.environ.get("ECOS_DATA_DIR", str(Path.home() / "Workspace" / "data"))
)
STATE_FILE = ECOS_HOME / "STATE.yaml"
SSB_DB = DATA_DIR / "kos" / "ssb.db"
WATCHDOG_FILE = Path.home() / ".hermes" / "ecos-watchdog" / "failures.json"
AGORA_SERVICES_FILE = (
    Path.home() / "Workspace" / "projects" / "agora" / "src" / "agora-services.json"
)
AGENTMESH_HEALTH_URL = "http://127.0.0.1:3000/v1/health"


def load_state() -> dict:
    """读取 STATE.yaml"""
    try:
        return yaml.safe_load(STATE_FILE.read_text()) or {}
    except Exception:  # noqa: BLE001  # defensive fallback
        return {}


def get_ssb_stats() -> dict:
    """SSB 数据库统计"""
    if not SSB_DB.exists():
        return {
            "error": "DB not found",
            "total": 0,
            "signed": 0,
            "coverage_pct": 0,
            "max_seq": 0,
        }
    try:
        db = sqlite3.connect(str(SSB_DB))
        total = db.execute("SELECT COUNT(*) FROM ssb_events").fetchone()[0]
        signed = db.execute(
            "SELECT COUNT(*) FROM ssb_events WHERE agent_signature IS NOT NULL AND agent_signature != ''"
        ).fetchone()[0]
        max_seq = db.execute("SELECT MAX(seq) FROM ssb_events").fetchone()[0]
        db.close()
        return {
            "total": total,
            "signed": signed,
            "coverage_pct": round(signed / total * 100, 1) if total > 0 else 0,
            "max_seq": max_seq,
        }
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": str(e), "total": 0}


def get_cron_status() -> list:
    """获取 cron 状态"""
    return [
        {"id": "WF-001", "name": "KOS索引", "schedule": "02:00", "status": "active"},
        {
            "id": "WF-002",
            "name": "Minerva研究",
            "schedule": "周日03:00",
            "status": "active",
        },
        {"id": "WF-003", "name": "健康检查", "schedule": "09:00", "status": "active"},
        {"id": "WF-005", "name": "HANDOFF更新", "schedule": "每2h", "status": "active"},
        {"id": "WF-006", "name": "感知管道", "schedule": "每小时", "status": "active"},
        {"id": "WF-007", "name": "安全检查", "schedule": "每6h", "status": "active"},
        {
            "id": "WF-008",
            "name": "Kanban桥接",
            "schedule": "每5min",
            "status": "active",
        },
        {
            "id": "WF-009",
            "name": "委员会周检",
            "schedule": "周一09:00",
            "status": "active",
        },
        {"id": "WF-010", "name": "宪法执行器", "schedule": "04:00", "status": "active"},
        {"id": "WF-011", "name": "每日摘要", "schedule": "12:00", "status": "active"},
        {"id": "WF-012", "name": "研究推送", "schedule": "12:00", "status": "active"},
        {
            "id": "WF-013",
            "name": "知识缺口检测",
            "schedule": "每天",
            "status": "active",
        },
    ]


def get_watchdog_status() -> dict:
    """读取 watchdog failures.json"""
    try:
        return json.loads(WATCHDOG_FILE.read_text())
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": str(e)}


def get_agora_services() -> list:
    """读取 Agora 服务注册表"""
    try:
        return json.loads(AGORA_SERVICES_FILE.read_text()).get("services", [])
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return [{"_error": str(e)}]


def get_forge_stats() -> dict:
    """Forge 统计"""
    return {"tools": 108, "graph_nodes": 423, "graph_edges": 634}


def get_bos_health() -> dict:
    """BOS URI 系统健康数据"""
    return {"metrics_calls": 0, "metrics_rate": "N/A", "cache_active": 0}


def get_swarm_health() -> dict:
    """Agora Swarm 蜂群健康数据"""
    return {"swarm_nodes": 1, "swarm_online": 1, "swarm_role": "standalone"}


def get_agentmesh_health() -> dict:
    """从 agentmesh health endpoint 获取代理在线状态"""
    try:
        req = urllib.request.Request(AGENTMESH_HEALTH_URL, method="GET")  # noqa: S310
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001  # defensive fallback
        return {"error": str(e), "status": "unreachable"}


def get_all_data() -> dict:
    """获取所有 dashboard 数据 (供 CLI --json 模式使用)"""
    return {
        "state": load_state(),
        "ssb": get_ssb_stats(),
        "cron": get_cron_status(),
        "watchdog": get_watchdog_status(),
        "agora_services": get_agora_services(),
        "forge": get_forge_stats(),
        "agentmesh": get_agentmesh_health(),
        "bos": get_bos_health(),
    }


def main():
    """eCOS Dashboard entry point — outputs JSON data (HTTP server removed)."""
    print("⚠️ ECOS Dashboard 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: ecos-dashboard [--json]")
        print()
        print("eCOS Dashboard data provider — converged to cockpit :8090")
        print("  --json  Output all dashboard data as JSON")
        print()
        print("Web dashboard: http://localhost:{COCKPIT_DASHBOARD_PORT}/api/ecos/status")
        return

    data = get_all_data()
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
