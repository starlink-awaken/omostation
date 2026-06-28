#!/usr/bin/env python3
"""P75 R3: graphify 本地扫描 wrapper.

graphify 0.8.46 工具的 extract 命令是 headless 全提取 (AST + semantic LLM),
但需要 LLM API 配置 (OPENAI_API_KEY 等). 本脚本:
1. 检测 API key 是否配置
2. 如有, 调 graphify extract 扫描 .omo/_knowledge/management/ (144 files)
3. 读旧 .omo/_knowledge/design/plans/graphify-out/graph.json
4. 输出对比 (旧 133 files vs 新 N files)
5. 如无 API key, 提示配置方法

使用:
  python3 bin/graphify-local-extract.py
  python3 bin/graphify-local-extract.py --output-only  # 只输出
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


GRAPHIFY_BIN = "/Users/xiamingxing/.local/share/uv/tools/graphifyy/bin/graphify"
OLD_GRAPH = ".omo/_knowledge/design/plans/graphify-out/graph.json"


def check_api_key() -> str:
    """检查 LLM API key 是否配置."""
    return os.environ.get("OPENAI_API_KEY", "")


def load_old_graph(root: Path) -> dict:
    """读旧 graph.json (P29 时期 133 文件)."""
    p = root / OLD_GRAPH
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def run_extract(root: Path) -> dict:
    """调 graphify extract 扫描."""
    cmd = [GRAPHIFY_BIN, "extract", str(root / ".omo" / "_knowledge" / "management")]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except FileNotFoundError:
        return {"error": f"graphify 二进制不存在: {GRAPHIFY_BIN}"}
    except Exception as e:
        return {"error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P75: graphify 本地扫描 wrapper (替代 P29 旧 graph)"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--output-only", action="store_true", help="只输出统计")
    parser.add_argument("--report-only", action="store_true",
                        help="P77: 仅读旧 graph.json 输出报告 (无需 API key)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    # P79: --report-only 仅读旧 graph.json (无需 API key)
    if args.report_only:
        old = load_old_graph(root)
        if not old:
            print(f"❌ 旧 graph.json 不存在: {OLD_GRAPH}")
            return 1
        total_files = old.get("total_files", 0)
        total_words = old.get("total_words", 0)
        print("=" * 60)
        print("📊 P79 graphify 旧报告 (无需 API key)")
        print("=" * 60)
        print(f"📁 来源: {OLD_GRAPH}")
        print(f"📈 总文件: {total_files}")
        print(f"📝 总词数: {total_words}")
        if "communities" in old:
            print(f"🏘  社区数: {len(old['communities'])}")
        if "extraction" in old:
            ex = old["extraction"]
            print(f"📂 提取: {ex.get('total_files', '?')} files, {ex.get('total_words', '?')} words")
        return 0

    api_key = check_api_key()
    if not api_key:
        print("=" * 60)
        print("⚠️  OPENAI_API_KEY 未配置, graphify extract 需 LLM")
        print("=" * 60)
        print()
        print("配置方法:")
        print("  export OPENAI_API_KEY=sk-xxx")
        print("  python3 bin/graphify-local-extract.py")
        print()
        print("或在 ~/.bashrc / ~/.zshrc 永久配置")
        print()
        print("📌 替代方案: graphify 0.8.46 extract 是 headless 完整提取,")
        print("   P75 阶段暂不实施, 留 P76+ 评估 API 成本")
        return 0

    # 旧 graph 对比
    old = load_old_graph(root)
    old_files = old.get("total_files", 0) if old else 0
    if not args.output_only:
        print("=" * 60)
        print("📊 P75 graphify 本地扫描 (management 144 files)")
        print("=" * 60)
        print("📁 扫描目录: .omo/_knowledge/management/")
        print(f"📈 旧 graph.json (P29): {old_files} files")
        print(f"🔑 OPENAI_API_KEY: {api_key[:8]}...")
        print()

    # 实际扫描
    result = run_extract(root)
    if "error" in result:
        print(f"❌ 扫描失败: {result['error']}")
        return 1

    if not args.output_only:
        print("🚀 运行 graphify extract...")
        print(f"returncode: {result['returncode']}")
        if result.get('stdout'):
            print("--- stdout ---")
            print(result['stdout'][:500])
        if result.get('stderr'):
            print("--- stderr ---")
            print(result['stderr'][:500])

    return result['returncode']


if __name__ == "__main__":
    sys.exit(main())