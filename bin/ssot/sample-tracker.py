#!/usr/bin/env python3
"""Sample Tracker — document-review 样本追踪器.

追踪 document-review 场景的 30 个样本收集进度.
样本来源: docs/ 下卫健委域相关文档.

用法:
    python3 sample-tracker.py --status           # 查看进度
    python3 sample-tracker.py --collect          # 自动收集样本
    python3 sample-tracker.py --list             # 列出所有候选文档
    python3 sample-tracker.py --json             # JSON 输出
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO / "docs"
STATE_FILE = REPO / ".omo/state/document-review-samples.jsonl"

# 卫健委域关键词
WEIJIAN_KEYWORDS = [
    "卫健委", "卫生", "健康", "医疗", "借调", "公文",
    "国转", "致远", "钉钉", "飞书", "OA",
    "报告", "汇报", "总结", "计划", "方案",
    "closeout", "retrospective", "report",
]


def find_weijian_documents() -> list[dict]:
    """查找卫健委域相关文档."""
    docs = []

    for f in sorted(DOCS_DIR.rglob("*.md")):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            # 检查是否包含卫健委相关关键词
            matches = []
            for kw in WEIJIAN_KEYWORDS:
                if kw.lower() in text.lower():
                    matches.append(kw)

            if matches:
                # 计算相关性得分 (关键词命中数)
                score = len(matches)
                docs.append({
                    "file": str(f.relative_to(REPO)),
                    "keywords": matches,
                    "score": score,
                    "size": len(text),
                })
        except Exception:
            continue

    # 按相关性排序
    docs.sort(key=lambda d: (-d["score"], -d["size"]))
    return docs


def load_state() -> dict:
    """加载样本收集状态."""
    if not STATE_FILE.exists():
        return {
            "target": 30,
            "collected": [],
            "remaining": 30,
            "last_updated": None,
        }

    try:
        with open(STATE_FILE) as f:
            lines = f.readlines()
            if lines:
                return json.loads(lines[-1])
    except Exception:
        pass

    return {
        "target": 30,
        "collected": [],
        "remaining": 30,
        "last_updated": None,
    }


def save_state(state: dict):
    """保存样本收集状态."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "a") as f:
        f.write(json.dumps(state, ensure_ascii=False) + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Document Review Sample Tracker")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.list:
        docs = find_weijian_documents()
        if args.json:
            print(json.dumps(docs[:50], ensure_ascii=False, indent=2))
        else:
            print(f"Found {len(docs)} candidate documents:")
            for i, d in enumerate(docs[:50], 1):
                print(f"  {i:2d}. [{d['score']}] {d['file']}")
                print(f"      keywords: {', '.join(d['keywords'][:5])}")
        return

    if args.collect:
        docs = find_weijian_documents()
        state = load_state()

        # 取前 30 个高相关性文档
        target_docs = docs[:30]
        state["collected"] = [d["file"] for d in target_docs]
        state["remaining"] = max(0, 30 - len(state["collected"]))
        state["target"] = 30

        save_state(state)

        if args.json:
            print(json.dumps(state, ensure_ascii=False, indent=2))
        else:
            print(f"Collected {len(state['collected'])} samples")
            print(f"Remaining: {state['remaining']}")
            for i, f in enumerate(state["collected"][:10], 1):
                print(f"  {i:2d}. {f}")
            if len(state["collected"]) > 10:
                print(f"  ... and {len(state['collected']) - 10} more")
        return

    # 默认: 显示状态
    state = load_state()
    docs = find_weijian_documents()

    if args.json:
        print(json.dumps({
            "state": state,
            "candidates": len(docs),
        }, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Document Review Sample Tracker")
    print("=" * 56)
    print(f"  Target: {state['target']} samples")
    print(f"  Collected: {len(state['collected'])}")
    print(f"  Remaining: {state['remaining']}")
    print(f"  Candidates available: {len(docs)}")
    print()

    if state["collected"]:
        print("  Collected samples:")
        for i, f in enumerate(state["collected"][:10], 1):
            print(f"    {i:2d}. {f}")
        if len(state["collected"]) > 10:
            print(f"    ... and {len(state['collected']) - 10} more")
    else:
        print("  No samples collected yet. Run --collect to start.")


if __name__ == "__main__":
    sys.exit(main())
