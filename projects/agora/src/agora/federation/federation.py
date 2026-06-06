"""A2A Federation — 跨Agora实例的AgentCard发现与通信。

Phase 11 / T147
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

FEDERATION_DB = Path.home() / ".kos" / "federation.db"


@dataclass
class AgentCard:
    agent_id: str  # "agent:hermes"
    name: str  # "Hermes"
    description: str  # "个人AI助手"
    capabilities: list[str]  # ["research", "code", "knowledge"]
    endpoint_url: str  # "http://localhost:7430"
    instance_id: str  # "agora:starlink-core"
    last_seen: str  # ISO timestamp
    trust_score: float = 0.5  # 0-1


class FederationManager:
    """跨实例Agent发现与通信"""

    def __init__(self):
        self._ensure_schema()

    def _ensure_schema(self):
        import sqlite3

        conn = sqlite3.connect(str(FEDERATION_DB))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_cards (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                capabilities TEXT DEFAULT '[]',
                endpoint_url TEXT DEFAULT '',
                instance_id TEXT DEFAULT '',
                last_seen TEXT DEFAULT '',
                trust_score REAL DEFAULT 0.5
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS peers (
                instance_id TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                a2a_endpoint TEXT DEFAULT '',
                last_sync TEXT DEFAULT '',
                status TEXT DEFAULT 'active'
            )
        """
        )
        conn.commit()
        conn.close()

    def register_agent_card(self, card: AgentCard):
        """注册或更新AgentCard。"""
        import sqlite3

        conn = sqlite3.connect(str(FEDERATION_DB))
        conn.execute(
            "INSERT OR REPLACE INTO agent_cards VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                card.agent_id,
                card.name,
                card.description,
                json.dumps(card.capabilities),
                card.endpoint_url,
                card.instance_id,
                card.last_seen,
                card.trust_score,
            ),
        )
        conn.commit()
        conn.close()

    def discover_peers(self) -> list[AgentCard | dict[str, str]]:
        """遍历所有对等实例，拉取它们的AgentCard。"""
        import sqlite3

        conn = sqlite3.connect(str(FEDERATION_DB))
        peers = conn.execute("SELECT instance_id, endpoint, a2a_endpoint FROM peers WHERE status='active'").fetchall()
        conn.close()

        results: list[AgentCard | dict[str, str]] = []
        for instance_id, endpoint, a2a_endpoint in peers:
            try:
                cards = self._fetch_agent_cards(a2a_endpoint or endpoint)
                for card_data in cards:
                    card = AgentCard(
                        agent_id=card_data.get("agent_id", card_data.get("name", "unknown")),
                        name=card_data.get("name", "Unknown"),
                        description=card_data.get("description", ""),
                        capabilities=card_data.get("capabilities", []),
                        endpoint_url=endpoint,
                        instance_id=instance_id,
                        last_seen=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    )
                    self.register_agent_card(card)
                    results.append(card)
                # 更新同步时间
                self._update_peer_sync(instance_id)
            except Exception as e:
                results.append({"error": str(e)})
        return results

    def _fetch_agent_cards(self, endpoint: str) -> list[dict]:
        """从对等实例获取AgentCard列表 (A2A协议)。"""
        import json as _json
        from urllib import request

        req = request.Request(f"{endpoint}/agent-cards", method="GET")  # noqa: S310
        resp = request.urlopen(req, timeout=10)  # noqa: S310
        return _json.loads(resp.read().decode()).get("cards", [])

    def _update_peer_sync(self, instance_id: str):
        import sqlite3

        conn = sqlite3.connect(str(FEDERATION_DB))
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute("UPDATE peers SET last_sync=? WHERE instance_id=?", (ts, instance_id))
        conn.commit()
        conn.close()

    def add_peer(self, instance_id: str, endpoint: str, a2a_endpoint: str = ""):
        """注册一个对等实例。"""
        import sqlite3

        conn = sqlite3.connect(str(FEDERATION_DB))
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "INSERT OR REPLACE INTO peers VALUES (?, ?, ?, ?, 'active')",
            (instance_id, endpoint, a2a_endpoint or f"{endpoint}/a2a", ts),
        )
        conn.commit()
        conn.close()

    def list_agents(self, capability_filter: str = "") -> list[dict]:
        """列出所有发现的AgentCard。"""
        import sqlite3

        conn = sqlite3.connect(str(FEDERATION_DB))
        if capability_filter:
            rows = conn.execute(
                "SELECT * FROM agent_cards WHERE capabilities LIKE ?",
                (f"%{capability_filter}%",),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM agent_cards ORDER BY trust_score DESC").fetchall()
        conn.close()
        cols = [
            "agent_id",
            "name",
            "description",
            "capabilities",
            "endpoint_url",
            "instance_id",
            "last_seen",
            "trust_score",
        ]
        result = []
        for r in rows:
            d = dict(zip(cols, r, strict=True))
            d["capabilities"] = json.loads(d["capabilities"])
            result.append(d)
        return result

    def find_agent(self, capability: str) -> list[dict]:
        """查找具有某个能力的Agent。"""
        return self.list_agents(capability_filter=capability)


if __name__ == "__main__":
    import sys

    fm = FederationManager()
    if len(sys.argv) > 1 and sys.argv[1] == "discover":
        results = fm.discover_peers()
        for r in results:
            if isinstance(r, dict) and "agent_id" in r:
                print(f"  {r['agent_id']:25s} {r['name']:15s} trust={r['trust_score']}")
            else:
                print(f"  Error: {r}")
    elif len(sys.argv) > 3 and sys.argv[1] == "add-peer":
        fm.add_peer(sys.argv[2], sys.argv[3])
        print(f"Peer added: {sys.argv[2]}")
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        for a in fm.list_agents():
            print(
                f"  {a['agent_id']:25s} {a['name']:15s} {', '.join(a['capabilities'][:2]):20s} trust={a['trust_score']}"
            )
    else:
        print("Usage: federation.py [discover|add-peer <id> <endpoint>|list]")
