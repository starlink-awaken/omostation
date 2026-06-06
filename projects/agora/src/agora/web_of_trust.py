"""Web of Trust — 信任链传递与评分衰退引擎。

Phase 12 / T156

核心概念:
- 每个实体(user/agent/org)有一个信任评分 (0-10)
- 信任可以传递: A信任B(8), B信任C(7) → A信任C = sqrt(8*7) ≈ 7.48
- 每跳距离衰减: 直接信任 √, 间接信任 √√, 三跳 √√√
- 信任评分随时间衰退 (每月-0.5, 最低0)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

WOT_DB = Path.home() / ".kos" / "web_of_trust.db"


@dataclass
class TrustEdge:
    from_entity: str  # "user:老王"
    to_entity: str  # "user:小张"
    score: float  # 0-10, 直接信任评分
    context: str  # "work", "personal", "org"
    created_at: str
    expires_at: str = ""


class WebOfTrust:
    """信任网引擎"""

    def __init__(self):
        pass

    def _get_conn(self):
        import sqlite3

        conn = sqlite3.connect(str(WOT_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trust_edges (
                from_entity TEXT NOT NULL,
                to_entity TEXT NOT NULL,
                score REAL DEFAULT 5.0,
                context TEXT DEFAULT 'general',
                created_at TEXT DEFAULT '',
                expires_at TEXT DEFAULT '',
                PRIMARY KEY (from_entity, to_entity)
            )
        """)
        conn.commit()
        return conn

    def set_trust(self, from_entity: str, to_entity: str, score: float, context: str = "general") -> dict:
        """建立或更新直接信任关系。"""
        conn = self._get_conn()
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "INSERT OR REPLACE INTO trust_edges VALUES (?, ?, ?, ?, ?, ?)",
            (from_entity, to_entity, min(score, 10.0), context, ts, ""),
        )
        conn.commit()
        conn.close()
        return {"from": from_entity, "to": to_entity, "score": score, "context": context}

    def get_trust_score(self, from_entity: str, to_entity: str) -> dict:
        """计算从from到to的信任分数（含传递链）。"""
        # 直接信任
        conn = self._get_conn()
        row = conn.execute(
            "SELECT score, context FROM trust_edges WHERE from_entity=? AND to_entity=?",
            (from_entity, to_entity),
        ).fetchone()

        if row:
            conn.close()
            return {"score": row[0], "path": [f"{from_entity}→{to_entity}"], "hops": 1, "source": "direct"}

        # BFS遍历间接信任 (最多3跳)
        # 信任链公式: n跳信任 = (score1 * score2 * ... * scoreN) ^ (1/N)  — 几何均值
        visited = {from_entity}
        queue = [(from_entity, 1.0, [from_entity])]  # (entity, product_of_scores, path)

        try:
            while queue:
                current, product, path = queue.pop(0)
                if len(path) > 1 and current == to_entity:
                    hops = len(path) - 1
                    score = round(10.0 * (product ** (1.0 / hops)), 2)
                    return {"score": score, "path": "→".join(path), "hops": hops, "source": "indirect"}
                if len(path) > 3:  # 最多3跳
                    continue

                edges = conn.execute(
                    "SELECT to_entity, score FROM trust_edges WHERE from_entity=? AND score>=5.0",
                    (current,),
                ).fetchall()
                for next_entity, score in edges:
                    if next_entity not in visited:
                        visited.add(next_entity)
                        # 累计乘积，最终取几何均值
                        queue.append((next_entity, product * (score / 10.0), path + [next_entity]))

            return {"score": 0, "path": "", "hops": 0, "source": "unreachable"}
        finally:
            conn.close()

    def decay_all(self, months: int = 1) -> int:
        """对所有信任评分做时效衰退。"""
        conn = self._get_conn()
        # 每月-0.5, 最低0
        count = conn.execute("UPDATE trust_edges SET score = MAX(0, score - 0.5) WHERE score > 0").rowcount
        conn.commit()
        conn.close()
        return count

    def list_edges(self, entity: str = "") -> list[dict]:
        """列出信任边。"""
        conn = self._get_conn()
        if entity:
            rows = conn.execute(
                "SELECT * FROM trust_edges WHERE from_entity=? OR to_entity=? ORDER BY score DESC",
                (entity, entity),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM trust_edges ORDER BY score DESC").fetchall()
        conn.close()
        cols = ["from_entity", "to_entity", "score", "context", "created_at", "expires_at"]
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def validate_capability_grant(self, grant: dict, from_entity: str) -> dict:
        """验证跨域CapabilityGrant的信任链。"""
        subject = grant.get("subject", "")
        trust = self.get_trust_score(from_entity, subject)
        if trust["score"] >= 5.0:
            return {
                "valid": True,
                "trust_score": trust["score"],
                "trust_path": trust["path"],
                "note": "Trust chain verified",
            }
        return {
            "valid": False,
            "trust_score": trust["score"],
            "note": f"Insufficient trust: {trust['score']} (need >= 5.0)",
        }


# CLI
if __name__ == "__main__":
    import sys

    wot = WebOfTrust()
    if len(sys.argv) > 2 and sys.argv[1] == "set":
        r = wot.set_trust(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 5.0)
        print(f"Trust set: {r['from']} → {r['to']} = {r['score']}")
    elif len(sys.argv) > 2 and sys.argv[1] == "get":
        r = wot.get_trust_score(sys.argv[2], sys.argv[3])
        print(f"{r['path']:30s} score={r['score']} ({r['source']})")
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        for e in wot.list_edges():
            print(f"  {e['from_entity']:20s} → {e['to_entity']:20s} score={e['score']}")
    elif len(sys.argv) > 1 and sys.argv[1] == "decay":
        cnt = wot.decay_all()
        print(f"Decayed {cnt} edges")
    else:
        print("Usage: web_of_trust.py [set|get|list|decay]")
