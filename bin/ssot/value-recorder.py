#!/usr/bin/env python3
"""Value Recorder — 价值记录器.

每次 Agent Workflow 结束后运行, 记录时间节省.
这是达成 value 维度的必要操作.

用法:
    python3 value-recorder.py --review 120 --saved 300 --verdict accept
    python3 value-recorder.py --status
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVIDENCE_FILE = REPO / ".omo/_delivery/ingress/value-evidence.jsonl"


def record_episode(review_seconds: int, saved_seconds: int, verdict: str) -> dict:
    now = datetime.now(timezone.utc)
    episode = {
        "schema": "value-evidence/v1",
        "timestamp": now.isoformat(),
        "principal_id": "xiamingxing",
        "review_duration_seconds": review_seconds,
        "estimated_time_saved_seconds": saved_seconds,
        "verdict": verdict,
        "net_saved_seconds": saved_seconds - review_seconds,
        "qualifying": saved_seconds > review_seconds and verdict in ("accept", "edit"),
    }
    EVIDENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE_FILE, "a") as f:
        f.write(json.dumps(episode, ensure_ascii=False) + "\n")
    return episode


def count_episodes() -> dict:
    total = qualifying = total_review = total_saved = 0
    if EVIDENCE_FILE.exists():
        with open(EVIDENCE_FILE) as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    total += 1
                    if data.get("qualifying"):
                        qualifying += 1
                    total_review += data.get("review_duration_seconds", 0)
                    total_saved += data.get("estimated_time_saved_seconds", 0)
                except Exception:
                    continue
    return {
        "total": total,
        "qualifying": qualifying,
        "total_review_min": round(total_review / 60, 1),
        "total_saved_min": round(total_saved / 60, 1),
        "qualifying_rate": round(qualifying / total, 2) if total else 0,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Value Recorder")
    parser.add_argument("--review", type=int, help="审核时间 (秒)")
    parser.add_argument("--saved", type=int, help="节省时间 (秒)")
    parser.add_argument("--verdict", choices=["accept", "edit", "reject"])
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        stats = count_episodes()
        print("=" * 56)
        print("  Value Episodes 统计")
        print("=" * 56)
        print(f"  总 episodes: {stats['total']}")
        print(f"  Qualifying: {stats['qualifying']}")
        print(f"  审核总时长: {stats['total_review_min']} 分钟")
        print(f"  节省总时长: {stats['total_saved_min']} 分钟")
        print(f"  Qualifying rate: {stats['qualifying_rate']}")
        print()
        print("  目标: 12 个 qualifying (4周 × 3/周)")
        if stats['qualifying'] >= 12:
            print("  ✓ 目标已达成!")
        else:
            print(f"  还需: {12 - stats['qualifying']} 个")
        return

    if args.review is None or args.saved is None or args.verdict is None:
        print("请提供 --review, --saved, --verdict 参数")
        sys.exit(1)

    episode = record_episode(args.review, args.saved, args.verdict)
    print("=" * 56)
    print("  Episode 已记录")
    print("=" * 56)
    print(f"  审核时间: {episode['review_duration_seconds']} 秒")
    print(f"  节省时间: {episode['estimated_time_saved_seconds']} 秒")
    print(f"  净节省: {episode['net_saved_seconds']} 秒")
    print(f"  裁决: {episode['verdict']}")
    print(f"  Qualifying: {'✓' if episode['qualifying'] else '✗'}")


if __name__ == "__main__":
    sys.exit(main())
