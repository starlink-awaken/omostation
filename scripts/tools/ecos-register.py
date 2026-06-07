#!/usr/bin/env python3
"""
eCOS v5 L1 — Runtime Matrix 注册桩 (ecos-register)
=====================================================
Phase X2-W3 / L3 深度奠基
将 ecos-daemon 注册到 L1 Runtime Matrix，提供 health() 端点。

当前 v1: 文件系统注册（JSON 状态文件）
后续: MCP/SSE 注册到 Runtime Registry

用法:
    # 注册 daemon
    python3 ecos-register.py --register --name ecos-daemon --type daemon

    # 查询注册状态
    python3 ecos-register.py --status

    # 健康检查端点（供外部监控调用）
    python3 ecos-register.py --health
"""

import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path


REGISTRY_DIR = Path.home() / ".ecos" / "runtime"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"
HEALTH_FILE = REGISTRY_DIR / "health.json"


def init_registry():
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text(json.dumps({"services": [], "updated_at": None}, indent=2))


def register_service(name: str, service_type: str, command: str = "", interval: str = "") -> dict:
    """注册服务到 Runtime Matrix"""
    init_registry()
    registry = json.loads(REGISTRY_FILE.read_text())

    # 检查是否已注册
    for svc in registry["services"]:
        if svc["name"] == name:
            svc["updated_at"] = datetime.now(timezone.utc).isoformat()
            svc["type"] = service_type
            REGISTRY_FILE.write_text(json.dumps(registry, ensure_ascii=False, indent=2))
            return {"status": "updated", "name": name}

    # 新注册
    service = {
        "name": name,
        "type": service_type,
        "command": command,
        "interval": interval,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }
    registry["services"].append(service)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    REGISTRY_FILE.write_text(json.dumps(registry, ensure_ascii=False, indent=2))

    # 写入健康状态文件
    write_health(name, "healthy", "registered")
    return {"status": "registered", "name": name}


def write_health(name: str, status: str, detail: str = ""):
    """写入健康状态"""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    health = {
        "service": name,
        "status": status,
        "detail": detail,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    HEALTH_FILE.write_text(json.dumps(health, ensure_ascii=False, indent=2))


def get_status() -> dict:
    """获取注册状态"""
    init_registry()
    registry = json.loads(REGISTRY_FILE.read_text())
    health = {}
    if HEALTH_FILE.exists():
        health = json.loads(HEALTH_FILE.read_text())
    return {"registry": registry, "health": health}


def health_check() -> dict:
    """健康检查端点"""
    status = get_status()
    services = status["registry"]["services"]
    return {
        "status": "healthy" if services else "empty",
        "services": len(services),
        "last_check": datetime.now(timezone.utc).isoformat(),
        "services_detail": [
            {"name": s["name"], "type": s["type"], "status": s.get("status", "unknown")}
            for s in services
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 L1 Runtime Matrix 注册桩")
    parser.add_argument("--register", action="store_true", help="注册服务")
    parser.add_argument("--name", type=str, default="ecos-daemon", help="服务名")
    parser.add_argument("--type", type=str, default="daemon", help="服务类型")
    parser.add_argument("--command", type=str, default="ecos-daemon.sh --once", help="启动命令")
    parser.add_argument("--interval", type=str, default="6h", help="调度间隔")
    parser.add_argument("--status", action="store_true", help="查看注册状态")
    parser.add_argument("--health", action="store_true", help="健康检查端点")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.register:
        result = register_service(args.name, args.type, args.command, args.interval)
    elif args.health:
        result = health_check()
    elif args.status:
        result = get_status()
    else:
        result = health_check()

    if args.json or args.health:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0)


if __name__ == "__main__":
    main()
