"""Agora Instance — 多实例身份与路由隔离。

每个Agora运行时=一个Instance，相互独立注册、独立路由。
实例之间通过A2A AgentCard发现互连。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

INSTANCE_CONFIG_DIR = Path.home() / ".config" / "agora" / "instances"


@dataclass
class AgoraInstance:
    instance_id: str  # "agora:starlink-core"
    instance_type: str  # "personal" | "team" | "org" | "ecosystem"
    display_name: str
    endpoint: str  # "http://localhost:7430"
    a2a_endpoint: str  # "http://localhost:7430/a2a"
    owner: str  # "org:starlink"
    capabilities: list[str]  # ["identity", "capability", "event", "knowledge", "task"]
    services: list[str]  # 本实例注册的服务名列表
    peers: list[str]  # 已知的其他实例ID列表


class InstanceManager:
    def __init__(self, config_dir: str | Path | None = None):
        self._dir = Path(config_dir or INSTANCE_CONFIG_DIR)
        self._instances: dict[str, AgoraInstance] = {}
        self._load()

    def _load(self) -> None:
        if self._dir.exists():
            for f in sorted(self._dir.glob("*.json")):
                data = json.loads(f.read_text())
                inst = AgoraInstance(**data)
                self._instances[inst.instance_id] = inst

    def register(self, instance: AgoraInstance) -> None:
        self._instances[instance.instance_id] = instance
        self._save(instance)

    def get(self, instance_id: str) -> AgoraInstance | None:
        return self._instances.get(instance_id)

    def list(self, type_filter: str = "") -> list[AgoraInstance]:
        if type_filter:
            return [
                i for i in self._instances.values() if i.instance_type == type_filter
            ]
        return list(self._instances.values())

    def add_peer(self, instance_id: str, peer_id: str) -> None:
        inst = self._instances.get(instance_id)
        if inst and peer_id not in inst.peers:
            inst.peers.append(peer_id)
            self._save(inst)

    def get_local(self) -> AgoraInstance:
        """返回当前Agora实例。"""
        instance_id = os.environ.get("AGORA_INSTANCE_ID", "agora:default")
        local = self.get(instance_id)
        if local:
            return local
        return AgoraInstance(
            instance_id=instance_id,
            instance_type="personal",
            display_name="Default",
            endpoint=os.environ.get("AGORA_ENDPOINT", "http://localhost:7430"),
            a2a_endpoint=os.environ.get(
                "AGORA_A2A_ENDPOINT", "http://localhost:7430/a2a"
            ),
            owner="org:starlink",
            capabilities=["identity", "capability", "event", "knowledge", "task"],
            services=[],
            peers=[],
        )

    def _save(self, instance: AgoraInstance) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        safe_name = instance.instance_id.replace(":", "-")
        path = self._dir / f"{safe_name}.json"
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance.instance_id,
                    "instance_type": instance.instance_type,
                    "display_name": instance.display_name,
                    "endpoint": instance.endpoint,
                    "a2a_endpoint": instance.a2a_endpoint,
                    "owner": instance.owner,
                    "capabilities": instance.capabilities,
                    "services": instance.services,
                    "peers": instance.peers,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
