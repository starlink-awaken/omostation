#!/usr/bin/env python3
# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""场景三全管道编排 — 意图拆解 → 多源检索 → 洞察生成 → 图谱更新 → 闭环验证 + HITL。

用法:
    python3 workflows/scenario3/run_pipeline.py "分析我对编程语言的学习模式"
    python3 workflows/scenario3/run_pipeline.py --auto "我的Rust和Go学习对比"
"""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = PROJECT_ROOT / "data" / "scenario3"


def _run(cmd: list[str], desc: str) -> tuple[int, str]:
    print(f"\n{'='*60}")
    print(f"  ▶ [{desc}]")
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.stdout:
        print(result.stdout[:1500])
    if result.stderr:
        print(f"  [stderr]: {result.stderr[:300]}")
    return result.returncode, result.stdout


def _hitl(phase: str) -> bool:
    print(f"\n{'#'*60}")
    print(f"# ⏸️  HITL: {phase}")
    print(f"# 时间: {datetime.now(UTC).isoformat()}")
    try:
        r = input("继续下一阶段？(Y/n): ").strip().lower()
        return r in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def phase1_decompose(question: str, auto: bool = False) -> bool:
    print("\n=== PHASE 1: 意图理解与任务拆解 ===")
    rc, out = _run(
        [sys.executable, "workflows/scenario3/task_decomposer.py", question],
        "任务拆解",
    )
    if not auto and not _hitl("Phase 1: 确认任务拆解方案"):
        return False
    return rc == 0


def phase2_retrieve(question: str, auto: bool = False) -> bool:
    print("\n=== PHASE 2: 多源知识检索 ===")
    rc, out = _run(
        [sys.executable, "workflows/scenario3/knowledge_retriever.py", question],
        "知识检索",
    )
    if not auto and not _hitl("Phase 2: 确认检索结果"):
        return False
    (REPORT_DIR / ".last_question").write_text(question, encoding="utf-8")
    return rc == 0


def phase3_insight(question: str, auto: bool = False) -> bool:
    print("\n=== PHASE 3: 洞察生成与图谱更新 ===")
    rc, out = _run(
        [sys.executable, "workflows/scenario3/insight_generator.py", question],
        "洞察生成",
    )
    if not auto and not _hitl("Phase 3: 确认洞察报告"):
        return False
    return rc == 0


def phase4_verify(auto: bool = False) -> bool:
    print("\n=== PHASE 4: 闭环一致性验证 ===")

    # 1. 检查 FactGraph 是否有新关系
    rc1, out1 = _run(
        [sys.executable, "-c", """
import sqlite3, json
conn = sqlite3.connect('data/db/organs/memory/fact_graph.db')
rows = conn.execute("SELECT COUNT(*) FROM fact_triples WHERE source_node_id='scenario3_insight'").fetchall()
print(f"Insight新关系: {rows[0][0]}条")
rows2 = conn.execute("SELECT sub, pred, obj FROM fact_triples WHERE source_node_id='scenario3_insight' LIMIT 5").fetchall()
for r in rows2:
    print(f"  {r[0]} --{r[1]}--> {r[2][:40]}")
conn.close()
"""],
        "FactGraph验证",
    )

    # 2. 验证可检索到新关系
    rc2, out2 = _run(
        [sys.executable, "-c", """
import sqlite3
conn = sqlite3.connect('data/db/organs/memory/fact_graph.db')
rows = conn.execute("SELECT COUNT(*) FROM fact_triples WHERE source_node_id LIKE '%scenario3%'").fetchall()
print(f"场景三相关数据: {rows[0][0]}条")
conn.close()
"""],
        "检索验证",
    )

    if rc1 == 0 and rc2 == 0:
        print("\n✅ 闭环一致性验证通过")
    else:
        print("\n⚠️ 部分验证未通过")

    if not auto:
        _hitl("Phase 4: 闭环验证确认")
    return rc1 == 0 and rc2 == 0


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="场景三：自主研究助手闭环")
    parser.add_argument("question", nargs="?", default="分析我对编程语言的学习模式",
                        help="要分析的问题")
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--phase", choices=["1", "2", "3", "4"])
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    question = args.question
    auto = args.auto

    print(f"\n{'='*60}")
    print("  场景三: 自主研究助手")
    print(f"  问题: {question}")
    print(f"{'='*60}")

    phases = [
        ("1", "任务拆解", lambda: phase1_decompose(question, auto)),
        ("2", "知识检索", lambda: phase2_retrieve(question, auto)),
        ("3", "洞察生成", lambda: phase3_insight(question, auto)),
        ("4", "闭环验证", lambda: phase4_verify(auto)),
    ]

    for pid, pname, pfunc in phases:
        if args.phase and args.phase != pid:
            continue
        print(f"\n>>> Phase {pid}: {pname}")
        if not pfunc():
            print(f"❌ Phase {pid} 中止")
            sys.exit(1)

    print(f"\n{'='*60}")
    print("  ✅ 场景三执行完成！")
    print(f"  报告目录: {REPORT_DIR}")


if __name__ == "__main__":
    main()
