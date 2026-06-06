# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""注入冲突的个人知识事实 — 模拟多来源矛盾信息。"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[6]
DB_PATH = str(PROJECT_ROOT / "data" / "db" / "organs" / "memory" / "fact_graph.db")
SCENARIO_LABEL = "personal_conflict_scenario"


CONFLICT_PAIRS = [
    {
        "fact_a": {
            "sub": "Rust",
            "pred": "recommended_use",
            "obj": "适合系统编程和性能敏感场景如嵌入式",
            "source": "wechat_2026-04-24",
            "confidence": 0.85,
        },
        "fact_b": {
            "sub": "Rust",
            "pred": "recommended_use",
            "obj": "主要优势在于WebAssembly和前端工具链",
            "source": "notes_2026-04-25",
            "confidence": 0.70,
        },
    },
    {
        "fact_a": {
            "sub": "学习计划",
            "pred": "next_step",
            "obj": "计划学习PyTorch和深度学习方向",
            "source": "notes_2026-Q1",
            "confidence": 0.90,
        },
        "fact_b": {
            "sub": "学习计划",
            "pred": "next_step",
            "obj": "已转向Rust系统编程，暂缓深度学习",
            "source": "wechat_2026-04-22",
            "confidence": 0.75,
        },
    },
    {
        "fact_a": {
            "sub": "Go",
            "pred": "concurrency_performance",
            "obj": "GO并发模型优秀，适合IO密集型任务",
            "source": "wechat_2026-04-24",
            "confidence": 0.80,
        },
        "fact_b": {
            "sub": "Go",
            "pred": "concurrency_performance",
            "obj": "Goroutine轻量但GC在高并发下延迟不稳定",
            "source": "article_reference",
            "confidence": 0.65,
        },
    },
]


def inject_conflicts(db_path: str | None = None) -> dict:
    if db_path is None:
        db_path = DB_PATH
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {"total_pairs": len(CONFLICT_PAIRS), "injected": 0, "skipped": 0, "conflicts": []}

    for pair in CONFLICT_PAIRS:
        pair_conflicts = []
        for side in ["fact_a", "fact_b"]:
            f = pair[side]
            cursor.execute(
                "SELECT id FROM fact_triples WHERE sub=? AND pred=? AND obj=?",
                (f["sub"], f["pred"], f["obj"]),
            )
            if cursor.fetchone():
                stats["skipped"] += 1  # type: ignore[operator]
                continue

            fact_id = str(uuid.uuid4())
            metadata = json.dumps({
                "source": f["source"],
                "confidence": f["confidence"],
                "scenario": SCENARIO_LABEL,
            }, ensure_ascii=False)

            from datetime import datetime
            iso_ts = datetime.now(UTC).isoformat()
            cursor.execute(
                "INSERT INTO fact_triples (id, sub, pred, obj, metadata, source_node_id, timestamp) VALUES (?,?,?,?,?,?,?)",
                (fact_id, f["sub"], f["pred"], f["obj"], metadata, "scenario2", iso_ts),
            )
            stats["injected"] += 1  # type: ignore[operator]
            pair_conflicts.append(fact_id)

        if len(pair_conflicts) == 2:
            stats["conflicts"].append({  # type: ignore[attr-defined]
                "sub": pair["fact_a"]["sub"],
                "pred": pair["fact_a"]["pred"],
                "fact_a_id": pair_conflicts[0],
                "fact_b_id": pair_conflicts[1],
            })

    conn.commit()
    conn.close()
    return stats


def main() -> None:
    result = inject_conflicts()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["injected"] > 0:
        print(f"✅ 成功注入 {result['injected']} 条冲突事实 ({result['total_pairs']} 对)")
    else:
        print("ℹ️  所有冲突事实已存在（跳过）")


if __name__ == "__main__":
    main()
