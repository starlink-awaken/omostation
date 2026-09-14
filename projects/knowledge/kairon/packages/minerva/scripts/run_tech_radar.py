#!/usr/bin/env python3
"""快速验证 + 运行 tech-radar。

用法：
    # 仅验证 import（不发网络请求）
    cd projects/kairon && uv run python scripts/run_tech_radar.py --verify

    # dry-run（发网络请求但不写 KOS / 不保存文件）
    cd projects/kairon && uv run python scripts/run_tech_radar.py --dry-run

    # 正式运行（写 KOS + 生成报告）
    cd projects/kairon && uv run python scripts/run_tech_radar.py
"""

import argparse
import asyncio
import sys


def verify_imports() -> bool:
    """验证所有模块可以 import。"""
    print("验证 import…")
    try:
        import importlib

        for mod in [
            "minerva.tech_radar.analyzer",
            "minerva.tech_radar.fetcher",
            "minerva.tech_radar.kos_writer",
            "minerva.tech_radar.reporter",
            "minerva.tech_radar.runner",
        ]:
            importlib.import_module(mod)
        from minerva.tech_radar.analyzer import analyze_items
        from minerva.tech_radar.fetcher import TechItem

        print("✅ 所有模块 import 成功")

        # 快速评分测试
        items = [
            TechItem(
                title="Multi-agent MCP tool use with RAG knowledge graph",
                description="orchestration ontology embedding vector retrieval",
                url="https://test.com",
                source="arxiv",
            ),
            TechItem(
                title="Climate weather forecast model",
                description="sports prediction",
                url="https://test.com/2",
                source="arxiv",
            ),
        ]
        scored = analyze_items(items, threshold=0.0)
        high = scored[0]
        low = scored[-1]
        assert high.relevance_score > low.relevance_score, "排序错误"
        assert high.upgrade_candidate, f"高相关度条目未标记 upgrade_candidate: {high.relevance_score}"
        print(f"✅ 评分测试通过: [{high.relevance_score:.2f}] {high.title[:40]}")
        print(f"   低分示例: [{low.relevance_score:.2f}] {low.title[:40]}")
        return True
    except Exception as exc:
        print(f"❌ 失败: {exc}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Tech Radar 运行脚本")
    parser.add_argument("--verify", action="store_true", help="只验证 import，不发请求")
    parser.add_argument("--dry-run", action="store_true", help="发请求但不写文件")
    parser.add_argument("--sources", default="arxiv,github,huggingface")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.verify:
        ok = verify_imports()
        sys.exit(0 if ok else 1)

    if not verify_imports():
        sys.exit(1)

    from minerva.tech_radar.runner import run

    src_list = [s.strip() for s in args.sources.split(",")]
    print(f"\n启动 tech-radar (sources={src_list}, dry_run={args.dry_run})…\n")

    result = asyncio.run(
        run(
            output_path=args.output,
            sources=src_list,
            dry_run=args.dry_run,
        )
    )

    print("\n===== 运行摘要 =====")
    print(f"原始条目:  {result['raw_count']}")
    print(f"相关条目:  {result['relevant_count']}")
    print(f"升级候选:  {result['candidate_count']}")
    print(f"KOS 写入:  {result['kos']}")
    if result["report_path"]:
        print(f"报告路径:  {result['report_path']}")
    if result["top_candidates"]:
        print("\nTop 候选:")
        for c in result["top_candidates"]:
            print(f"  [{c['score']:.2f}] {c['source']:12s} {c['title'][:60]}")


if __name__ == "__main__":
    main()
