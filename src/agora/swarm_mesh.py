"""agora.swarm_mesh — 多 Agent 蜂群实时全感知、通信与碰撞预警引擎.

管理 .omo/state/swarm/ 目录下的 active-nodes.yaml (节点注册表)
与 broadcast-bus.jsonl (蜂群事件总线).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SWARM_STATE_DIR = WORKSPACE_ROOT / ".omo" / "state" / "swarm"
ACTIVE_NODES_PATH = SWARM_STATE_DIR / "active-nodes.yaml"
BROADCAST_BUS_PATH = SWARM_STATE_DIR / "broadcast-bus.jsonl"


class SwarmMeshManager:
    """多 Agent 蜂群网状感知与通信管理器"""

    def __init__(self, root: Path = WORKSPACE_ROOT) -> None:
        self.root = root
        self.swarm_dir = self.root / ".omo" / "state" / "swarm"
        self.nodes_path = self.swarm_dir / "active-nodes.yaml"
        self.bus_path = self.swarm_dir / "broadcast-bus.jsonl"
        self.swarm_dir.mkdir(parents=True, exist_ok=True)

    def _load_nodes(self) -> List[Dict[str, Any]]:
        if not self.nodes_path.exists():
            return []
        try:
            with open(self.nodes_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get("nodes", [])
        except Exception:
            return []

    def _save_nodes(self, nodes: List[Dict[str, Any]]) -> None:
        with open(self.nodes_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"nodes": nodes, "updated_at": datetime.now(timezone.utc).isoformat()}, f, allow_unicode=True)

    def register_node(
        self,
        agent_id: str,
        role: str = "Developer",
        working_paths: Optional[List[str]] = None,
        active_run_id: str = "",
        status: str = "active",
    ) -> Dict[str, Any]:
        nodes = self._load_nodes()
        now_str = datetime.now(timezone.utc).isoformat()
        paths = working_paths or []

        found = False
        for n in nodes:
            if n.get("agent_id") == agent_id:
                n["role"] = role
                n["working_paths"] = paths
                n["active_run_id"] = active_run_id
                n["status"] = status
                n["last_heartbeat"] = now_str
                found = True
                break

        if not found:
            nodes.append({
                "agent_id": agent_id,
                "role": role,
                "working_paths": paths,
                "active_run_id": active_run_id,
                "status": status,
                "last_heartbeat": now_str,
            })

        self._save_nodes(nodes)
        return {"status": "success", "agent_id": agent_id, "registered_at": now_str}

    def who_is_working_on(self, path: str) -> List[Dict[str, Any]]:
        nodes = self._load_nodes()
        matches = []
        clean_path = path.strip("/")

        for n in nodes:
            w_paths = n.get("working_paths", [])
            for wp in w_paths:
                wp_clean = wp.strip("/")
                if clean_path.startswith(wp_clean) or wp_clean.startswith(clean_path):
                    matches.append(n)
                    break
        return matches

    def broadcast(
        self,
        sender_id: str,
        content: str,
        channel: str = "all",
        event_type: str = "notice",
        target_agent_id: str = "",
    ) -> Dict[str, Any]:
        msg_id = f"msg-{int(time.time() * 1000)}"
        now_str = datetime.now(timezone.utc).isoformat()

        record = {
            "msg_id": msg_id,
            "sender_id": sender_id,
            "channel": channel,
            "event_type": event_type,
            "target_agent_id": target_agent_id,
            "content": content,
            "timestamp": now_str,
        }

        with open(self.bus_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return {"status": "sent", "msg_id": msg_id, "timestamp": now_str}

    def read_channel(self, channel: str = "all", limit: int = 20) -> List[Dict[str, Any]]:
        if not self.bus_path.exists():
            return []

        results = []
        try:
            with open(self.bus_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                        if channel == "all" or rec.get("channel") == channel:
                            results.append(rec)
                            if len(results) >= limit:
                                break
                    except Exception:
                        continue
        except Exception:
            pass

        return results
