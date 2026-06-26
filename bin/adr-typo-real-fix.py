#!/usr/bin/env python3
"""P96 R1: ADR drift TYPO 字符级 Levenshtein 真正修复工具.

替代 P95 adr-typo-fix.py 的 Jaccard 简化版, 用真正 Levenshtein 距离:
- 对 typo path 找最相似的实际文件
- 阈值: Levenshtein distance <= 3 (或 ratio >= 0.7)
- 应用策略保守: 只建议最相似 (top-1), 不自动修改

使用:
  python3 bin/adr-typo-real-fix.py
  python3 bin/adr-typo-real-fix.py --json
  python3 bin/adr-typo-real-fix.py --apply  # 实际修改
  python3 bin/adr-typo-real-fix.py --rollback
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

LEVENSHTEIN_HISTORY = Path(".omo/_delivery/adr-typo-real-fix-history.jsonl")


def levenshtein(a: str, b: str) -> int:
    """真正 Levenshtein 距离 (动态规划)."""
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            ins = prev[j + 1] + 1
            dele = curr[j] + 1
            sub = prev[j] + (0 if ca == cb else 1)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]


def similarity_ratio(a: str, b: str) -> float:
    """归一化相似度 [0, 1]."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return 1.0 - levenshtein(a, b) / max(len(a), len(b))


def find_similar_files(typo_path: str, root: Path, threshold: float = 0.7) -> list[dict]:
    """找 typo_path 最相似的实际文件 (Levenshtein 阈值)."""
    candidates: list[dict] = []
    typo_basename = Path(typo_path).name  # 精确匹配文件名

    for f in root.rglob("*"):
        if not f.is_file():
            continue
        ratio = similarity_ratio(typo_basename, f.name)
        if ratio >= threshold:
            candidates.append({"path": str(f.relative_to(root)), "ratio": round(ratio, 3)})
    # 按 ratio 降序
    candidates.sort(key=lambda x: -x["ratio"])
    return candidates[:5]


def main() -> int:
    parser = argparse.ArgumentParser(description="P96: ADR drift TYPO 真正字符级修复")
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.7,
                        help="Levenshtein ratio 阈值 (默认 0.7)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    if args.rollback:
        if not LEVENSHTEIN_HISTORY.exists():
            print("❌ no history")
            return 1
        with LEVENSHTEIN_HISTORY.open(encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        if not lines:
            return 1
        last = json.loads(lines[-1])
        if last.get("action") != "apply":
            print(f"❌ last not apply: {last.get('action')}")
            return 1
        # 反向替换
        rolled = []
        for item in last.get("items", []):
            adr = Path(item["adr_path"])
            if not adr.exists():
                continue
            content = adr.read_text(encoding="utf-8")
            new_content = content.replace(item["correct"], item["typo"])
            if new_content != content:
                adr.write_text(new_content, encoding="utf-8")
                rolled.append(item)
        # 追加 history
        with LEVENSHTEIN_HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "action": "rollback",
                "items": rolled,
            }, ensure_ascii=False) + "\n")
        print(f"🔙 Rolled: {len(rolled)}")
        for item in rolled:
            print(f"   {item['typo']} ← {item['correct']}")
        return 0

    # 调用 adr-drift-auto-fix
    r = subprocess.run(
        ["python3", str(root / "bin" / "adr-drift-auto-fix.py"), "--json"],
        cwd=str(root), capture_output=True, text=True, timeout=60,
    )
    try:
        classify = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse: {e}")
        return 1

    typos = [i for i in classify.get("items", [])
             if i.get("classification", {}).get("type") == "TYPO"]

    # 用 Levenshtein 重新找最相似
    plans: list[dict] = []
    for t in typos:
        msg = t["msg"]
        typo_path = msg.replace("路径不存在: ", "").strip()
        # 当前 auto-fix 的 Jaccard suggestion 不一定对, 重新算
        cands = find_similar_files(typo_path, root, args.threshold)
        if not cands:
            # 即使无 Levenshtein 匹配, 仍记录旧 suggestion
            old_reason = t["classification"].get("reason", "")
            import re
            m = re.search(r"实际文件: (.+)", old_reason)
            old_suggest = m.group(1).strip() if m else None
            plans.append({
                "adr_number": t["adr_number"],
                "typo": typo_path,
                "candidates": [],
                "old_suggest": old_suggest,
            })
        else:
            plans.append({
                "adr_number": t["adr_number"],
                "typo": typo_path,
                "candidates": cands,
            })

    if args.apply:
        # 自动应用: 对每个 typo, 选 ratio 最高的 candidate 修改 ADR
        applied: list[dict] = []
        skipped: list[dict] = []
        for p in plans:
            if not p["candidates"]:
                skipped.append({**p, "reason": "no Levenshtein match"})
                continue
            best = p["candidates"][0]
            adr_pattern = f"{p['adr_number']:04d}-*.md"
            adr_file = next(
                (f for f in (root / ".omo" / "_knowledge" / "decisions").glob(adr_pattern)),
                None,
            )
            if not adr_file:
                skipped.append({**p, "reason": "ADR file not found"})
                continue
            content = adr_file.read_text(encoding="utf-8")
            if p["typo"] not in content:
                skipped.append({**p, "reason": "typo not in ADR content"})
                continue
            new_content = content.replace(p["typo"], best["path"])
            adr_file.write_text(new_content, encoding="utf-8")
            applied.append({
                "adr_number": p["adr_number"],
                "adr_path": str(adr_file),
                "typo": p["typo"],
                "correct": best["path"],
                "ratio": best["ratio"],
            })
        # 写 history
        LEVENSHTEIN_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with LEVENSHTEIN_HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "action": "apply",
                "items": applied,
            }, ensure_ascii=False) + "\n")
        result = {"applied": applied, "skipped": skipped}
    else:
        result = {"plans": plans, "action": "dry-run", "threshold": args.threshold}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print(f"🔧 P96 ADR TYPO Levenshtein 修复 ({'APPLY' if args.apply else 'DRY-RUN'}, 阈值 {args.threshold})")
    print("=" * 60)
    if args.apply:
        print(f"✅ Applied: {len(result['applied'])}")
        for item in result["applied"]:
            print(f"   ADR-{item['adr_number']:04d}: {item['typo']} → {item['correct']} (ratio {item['ratio']})")
        print(f"⚠️  Skipped: {len(result['skipped'])}")
        for item in result["skipped"]:
            print(f"   ADR-{item['adr_number']:04d}: {item.get('typo')} ({item['reason']})")
    else:
        print(f"📊 TYPO 待 Levenshtein 匹配: {len(plans)}")
        for p in plans:
            print(f"   ADR-{p['adr_number']:04d}: {p['typo']}")
            if p["candidates"]:
                for c in p["candidates"][:3]:
                    print(f"     → {c['path']}  (ratio {c['ratio']})")
            else:
                print(f"     ⚠️  无 Levenshtein >= {args.threshold} 匹配")
                if p.get("old_suggest"):
                    print(f"     💡 旧 Jaccard 建议: {p['old_suggest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
