#!/usr/bin/env python3
"""agent-output-extract: 从 Agent output_file 提取纯 assistant text (R3 harness bug 修复).

🔴 背景 (Q2 证, R3 修复): Agent 工具 result 字段回收缺陷 — result 只放摘要
("任务完成"), 完整产出在 output_file (JSONL transcript). 拿 result 下质量结论 = 违规.

本工具是度量基础设施修复: 解析 output_file JSONL, 提取纯 assistant message text
(去工具调用/读文件/中间思考噪音), 作为协作实验的可信度量 (替代不可信 result).

harness 平台层 bug agent 无法修 (送卡人类), 本工具是**绕过修复** (agent 侧可信度量).

Usage:
  python3 bin/collab/agent-output-extract.py <output_file>           # 输出 char 数
  python3 bin/collab/agent-output-extract.py <output_file> --full    # 输出全文
  python3 bin/collab/agent-output-extract.py <file1> <file2> ...     # 多文件对比
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def extract_assistant_texts(path: Path) -> list[str]:
    """提取 output_file JSONL 里所有 assistant message 的 text (去工具调用噪音)."""
    texts: list[str] = []
    if not path.is_file():
        return texts
    for line in path.open(encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:  # K3: 不静默, 跳过非 JSON 行 (transcript 可能有非 JSON)
            continue
        msg = d.get("message") or d
        role = msg.get("role") or d.get("type") or d.get("role")
        if role != "assistant":
            continue
        content = msg.get("content") or d.get("content")
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    texts.append(c.get("text", ""))
        elif isinstance(content, str):
            texts.append(content)
    return texts


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("output_files", nargs="+", help="Agent output_file(s)")
    parser.add_argument("--full", action="store_true", help="输出全文 (默认只 char 数)")
    args = parser.parse_args(argv)

    for f in args.output_files:
        path = Path(f)
        texts = extract_assistant_texts(path)
        total = sum(len(t) for t in texts)
        if args.full:
            print(f"=== {path.name} ({len(texts)} msgs, {total} chars) ===")
            for t in texts:
                print(t)
            print()
        else:
            print(f"{path.name}: {len(texts)} assistant msgs, {total} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
