"""BOS 能力作为 external.resources provider 暴露 (mesh 能力目录衔接)。

让 bos-services.yaml 中的 BOS 能力 (188 个) 通过 external-resource 发现机制
(external.resources entry-point) 暴露给 external-resource-catalog.py,
使 mesh 场景卡能消费完整能力目录 (capability_index)。

Provider 契约 (external-connection-fabric.yaml dynamic_discovery):
- entry_point_group: external.resources
- provider_method: external_descriptor
- 返回单个 ExternalResourceDescriptor Mapping (capabilities 可含多 URI)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# capability 目录数据源: etc/bos-services.yaml (与 capability_catalog 一致)
# src/agora/external_resources/ → parents[3] = projects/agora 项目根
_DEFAULT_BOS_YAML = str(
    Path(__file__).resolve().parents[3] / "etc" / "bos-services.yaml"
)


class CapabilityProvider:
    """把 BOS 能力目录暴露为单个 external-resource descriptor。

    一个聚合 resource (id=bos://capabilities), capabilities 含全部能力 URI,
    使 external-resource-catalog.py --directory 的 capability_index 覆盖完整能力集。
    """

    def __init__(self, bos_yaml: str = "") -> None:
        self._bos_yaml = bos_yaml or os.environ.get(
            "AGORA_BOS_REGISTRY", _DEFAULT_BOS_YAML
        )

    def external_descriptor(self) -> dict[str, Any]:
        """返回聚合能力 descriptor (credential-free, 只读投影)。"""
        caps = self._load_capabilities()
        uris = sorted(caps)
        # lifecycle: 有 deprecated/僵尸候选时降级, 否则 active
        statuses = {c.get("status", "active") for c in caps.values()}
        lifecycle = "active" if not (statuses & {"deprecated", "sandbox"}) else "admitted"
        return {
            "id": "bos://capabilities",
            "kind": "tool_capability",
            "provider": "agora.bos",
            "protocol": "bos",
            "capabilities": uris,
            "data_classification": "internal",
            "provenance": {
                "source": "agora.bos",
                "bos_yaml": self._bos_yaml,
                "capability_count": len(uris),
            },
            "lifecycle": lifecycle,
            "health": {"status": "ok", "last_check": ""},
            "owner": "agora",
            "version": "1.0.0",
            "permission_ref": "agora.bos",
            "mode": "read_only_projection",
            "metadata": {
                "description": f"BOS capability directory ({len(uris)} capabilities)",
                "capability_statuses": {
                    status: sum(1 for c in caps.values() if c.get("status") == status)
                    for status in sorted(statuses)
                },
            },
        }

    def _load_capabilities(self) -> dict[str, dict[str, Any]]:
        """从 bos-services.yaml 加载能力声明 (与 capability_catalog.load 一致)。"""
        try:
            path = Path(self._bos_yaml)
            if not path.exists():
                return {}
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            services = data.get("services", []) if data else []
            caps: dict[str, dict[str, Any]] = {}
            for svc in services:
                uri = svc.get("uri", "")
                if not uri or not uri.startswith("bos://"):
                    continue
                caps[uri] = {
                    "uri": uri,
                    "domain": svc.get("domain", ""),
                    "package": svc.get("package", ""),
                    "action": svc.get("action", ""),
                    "description": svc.get("description", ""),
                    "status": svc.get("status", "active"),
                }
            return caps
        except Exception:  # noqa: BLE001 — 加载失败返回空 (defensive fallback)
            return {}


def build_capability_descriptor(bos_yaml: str = "") -> dict[str, Any]:
    """便捷入口: 返回聚合能力 descriptor (供脚本/测试直接调用)。"""
    return CapabilityProvider(bos_yaml).external_descriptor()
