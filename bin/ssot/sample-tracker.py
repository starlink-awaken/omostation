#!/usr/bin/env python3
"""Sample Tracker — document-review 样本追踪器."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO / "docs"
SAMPLE_FILE = REPO / ".omo/state/document-review-samples.jsonl"

WEIJIAN_KEYWORDS = ["卫健委", "卫生", "健康", "医疗", "借调", "公文", "国转", "致远", "钉钉", "飞书", "OA", "报告", "汇报", "总结", "计划", "方案", "closeout", "retrospective", "report"]


def find_weijian_documents() -> list[dict]:
    docs = []
    if not DOCS_DIR.exists():
        return docs
    for f in sorted(DOCS_DIR.rglob("*.md")):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            matches = [kw for kw in WEIJIAN_KEYWORDS if kw.lower() in text.lower()]
            if matches:
                docs.append({"file": str(f.relative_to(REPO)), "keywords": matches, "score": len(matches), "size": len(text)})
        except Exception:
            continue
    docs.sort(key=lambda d: (-d["score"], -d["size"]))
    return docs


def load_state() -> dict:
    if not SAMPLE_FILE.exists():
        return {"target": 30, "collected": [], "remaining": 30}
    try:
        with open(SAMPLE_FILE) as f:
            for line in f:
                data = json.loads(line.strip())
                return data
    except Exception:
        pass
    return {"target": 30, "collected": [], "remaining": 30}


def save_state(state: dict):
    SAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(SAMPLE_FILE, "a") as f:
        f.write(json.dumps(state, ensure_ascii=False) + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sample Tracker")
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--status", action="store_true")
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
        return

    if args.collect:
        docs = find_weijian_documents()
        state = load_state()
        target_docs = docs[:30]
        state["collected"] = [d["file"] for d in target_docs]
        state["remaining"] = max(0, 30 - len(state["collected"]))
        save_state(state)
        print(f"Collected {len(state['collected'])} samples, remaining: {state['remaining']}")
        return

    state = load_state()
    docs = find_weijian_documents()
    print("=" * 56)
    print("  Document Review Sample Tracker")
    print("=" * 56)
    print(f"  Target: {state['target']}")
    print(f"  Collected: {len(state['collected'])}")
    print(f"  Remaining: {state['remaining']}")
    print(f"  Candidates: {len(docs)}")


if __name__ == "__main__":
    sys.exit(main())
