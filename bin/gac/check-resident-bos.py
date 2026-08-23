#!/usr/bin/env python3
"""CR-RESIDENT-BOS-01: resident 接口 BOS 路由 CI 校验.

resident 接口 (status/roles/daemon/decision/execute) 必须通过 bos://resident/* 暴露,
禁止绕过 BOS 直连 resident 内部数据面. 校验三个来源一致:
- SSOT: projects/agora/etc/bos-services.yaml (domain: resident 服务)
- 注册: .omo/_knowledge/bos-registry.json (domain: resident 条目)
- 白名单: agora/mcp/resolver/services_types.py (BOS_URI_DOMAINS 含 resident)

rule: resident.call.route == 'bos://resident/*'
期望 4 条必需 URI (status/roles/daemon/decision); execute 缺失按 advisory warn 报告.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BOS_SERVICES = REPO / "projects" / "agora" / "etc" / "bos-services.yaml"
BOS_REGISTRY = REPO / ".omo" / "_knowledge" / "bos-registry.json"
SERVICES_TYPES = (
    REPO / "projects" / "agora" / "src" / "agora" / "mcp" / "resolver" / "services_types.py"
)

# 期望 resident 必需 URI (execute 作为可选缺口 advisory 报告)
REQUIRED_URIS = [
    "bos://resident/core/status",
    "bos://resident/core/roles",
    "bos://resident/daemon/once",
    "bos://resident/decision/run",
]
OPTIONAL_URIS = ["bos://resident/execute/run"]
RESIDENT_URI_PREFIX = "bos://resident/"


def _resident_uris_from_services() -> list[str]:
    if not BOS_SERVICES.is_file():
        return []
    try:
        import yaml

        data = yaml.safe_load(BOS_SERVICES.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 - 解析失败按缺失处理
        return []
    uris: list[str] = []
    for svc in data.get("services") or []:
        if not isinstance(svc, dict):
            continue
        if str(svc.get("domain", "")).lower() != "resident":
            continue
        if str(svc.get("status", "active")).lower() == "deprecated":
            continue
        uri = svc.get("uri", "")
        if isinstance(uri, str) and uri.startswith(RESIDENT_URI_PREFIX):
            uris.append(uri)
    return uris


def _resident_uris_from_registry() -> list[str]:
    if not BOS_REGISTRY.is_file():
        return []
    try:
        data = json.loads(BOS_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    services = data.get("services") if isinstance(data, dict) else data
    if not isinstance(services, list):
        return []
    uris: list[str] = []
    for svc in services:
        if not isinstance(svc, dict):
            continue
        if str(svc.get("domain", "")).lower() != "resident":
            continue
        uri = svc.get("uri", "")
        if isinstance(uri, str) and uri.startswith(RESIDENT_URI_PREFIX):
            uris.append(uri)
    return uris


def _domain_allowlist() -> list[str]:
    if not SERVICES_TYPES.is_file():
        return []
    m = re.search(
        r"BOS_URI_DOMAINS\s*=\s*\((.*?)\)",
        SERVICES_TYPES.read_text(encoding="utf-8"),
        re.S,
    )
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


def check_bos_route() -> tuple[bool, str]:
    """CR-RESIDENT-BOS-01: resident 接口经 bos://resident/* 路由暴露."""
    svc_uris = _resident_uris_from_services()
    reg_uris = _resident_uris_from_registry()
    allowlist = _domain_allowlist()

    missing_svc = [u for u in REQUIRED_URIS if u not in svc_uris]
    missing_reg = [u for u in REQUIRED_URIS if u not in reg_uris]
    missing_allow = "resident" not in allowlist

    problems: list[str] = []
    if missing_svc:
        problems.append(f"bos-services.yaml 缺 {len(missing_svc)}: {missing_svc}")
    if missing_reg:
        problems.append(f"bos-registry.json 缺 {len(missing_reg)}: {missing_reg}")
    if missing_allow:
        problems.append("BOS_URI_DOMAINS 白名单缺 resident")

    optional_missing = [u for u in OPTIONAL_URIS if u not in svc_uris]
    detail_parts = [
        f"services={len(svc_uris)} registry={len(reg_uris)} allowlist_resident={not missing_allow}",
    ]
    if optional_missing:
        detail_parts.append(f"advisory: 缺 optional {len(optional_missing)} (execute)")
    if problems:
        return False, "; ".join(problems + detail_parts)
    return True, "; ".join(detail_parts)


def main() -> int:
    print("── CR-RESIDENT-BOS-01: resident 接口 BOS 路由 ──")
    passed, detail = check_bos_route()
    icon = "OK" if passed else "FAIL"
    print(f"  [{icon}] {detail}")
    print()
    if passed:
        print("CR-RESIDENT-BOS-01 PASS")
        return 0
    print("CR-RESIDENT-BOS-01 FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
