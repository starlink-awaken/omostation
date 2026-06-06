"""分布式CapabilityGrant (Phase 12 / T157)

跨Agora实例的能力授权:
- 组织A的CapabilityGrant + WoT信任链 → 组织B可使用
- 无需在组织B的Agora中手动创建grant
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from agora.web_of_trust import WebOfTrust  # type: ignore[import-not-found]

DISTRIBUTED_GRANTS_DB = Path.home() / ".kos" / "distributed_grants.json"


class DistributedGrantManager:
    def __init__(self):
        self._grants = self._load()

    def _load(self) -> list[dict]:
        if DISTRIBUTED_GRANTS_DB.exists():
            return json.loads(DISTRIBUTED_GRANTS_DB.read_text())
        return []

    def _save(self):
        DISTRIBUTED_GRANTS_DB.write_text(json.dumps(self._grants, ensure_ascii=False, indent=2))

    def issue_cross_instance(
        self,
        issuer_instance: str,
        subject: str,
        capability: str,
        resource_scope: str = "",
        constraints: dict | None = None,
    ) -> dict:
        """跨实例签发CapabilityGrant。"""
        import secrets

        grant = {
            "grant_id": f"dg:{secrets.token_hex(8)}",
            "issuer_instance": issuer_instance,
            "subject": subject,
            "capability": capability,
            "resource_scope": resource_scope,
            "constraints": constraints or {},
            "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "call_count": 0,
            "total_cost": 0.0,
        }
        self._grants.append(grant)
        self._save()
        return grant

    def verify_cross_instance(self, grant_id: str, caller: str, tool: str, cost: float = 0) -> dict:
        """验证跨实例grant（含WoT信任检查）。"""
        grant = next((g for g in self._grants if g["grant_id"] == grant_id), None)
        if not grant:
            return {"allowed": False, "reason": "grant not found"}

        # 1. 检查capability匹配
        cap = grant["capability"]
        if cap != "*" and not tool.startswith(cap.rstrip("*")):
            return {"allowed": False, "reason": f"capability mismatch: {tool} not in {cap}"}

        # 2. 检查约束
        cons = grant["constraints"]
        if cons.get("max_calls") and grant["call_count"] >= cons["max_calls"]:
            return {"allowed": False, "reason": "max calls exceeded"}
        if cons.get("max_cost") and grant["total_cost"] >= cons["max_cost"]:
            return {"allowed": False, "reason": "max cost exceeded"}

        # 3. WoT信任验证
        wot = WebOfTrust()
        trust = wot.get_trust_score(caller, grant["subject"])
        if trust["score"] < 5.0:
            return {"allowed": False, "reason": f"insufficient trust ({trust['score']}), need >= 5.0"}

        # 更新计数器
        grant["call_count"] += 1
        grant["total_cost"] += cost
        self._save()
        return {"allowed": True, "grant_id": grant_id, "trust_score": trust["score"]}

    def list_grants(self, subject: str = "") -> list[dict]:
        if subject:
            return [g for g in self._grants if g["subject"] == subject]
        return self._grants


# CLI
if __name__ == "__main__":
    import sys

    dg = DistributedGrantManager()
    if sys.argv[1] == "issue":
        r = dg.issue_cross_instance(sys.argv[2], sys.argv[3], sys.argv[4])
        print(f"Issued: {r['grant_id']}")
    elif sys.argv[1] == "list":
        for g in dg.list_grants():
            print(f"  {g['grant_id']:25s} {g['subject']:20s} {g['capability']:20s}")
