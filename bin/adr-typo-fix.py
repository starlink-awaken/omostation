#!/usr/bin/env python3
"""P95 R1: ADR drift TYPO 字符级自动修复工具.

读取 adr-drift-auto-fix 报告, 对 TYPO 类型自动修正 ADR 文件中的路径引用.
- 找到 ADR 中 typo path, 替换为建议的 correct path
- 干跑模式只显示不修改
- 应用模式直接修改 ADR 文件 (in-place edit)
- 回滚模式: 读 history 撤销

使用:
  python3 bin/adr-typo-fix.py              # 干跑
  python3 bin/adr-typo-fix.py --apply     # 实际修改
  python3 bin/adr-typo-fix.py --rollback  # 撤销
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TYPO_HISTORY = Path(".omo/_delivery/adr-typo-fix-history.jsonl")


def load_classify(root: Path) -> dict:
    """调用 adr-drift-auto-fix 拿分类结果."""
    r = subprocess.run(
        ["python3", str(root / "bin" / "adr-drift-auto-fix.py"), "--json"],
        cwd=str(root), capture_output=True, text=True, timeout=60,
    )
    if r.returncode not in (0, 1):
        raise RuntimeError(f"adr-drift-auto-fix 失败: {r.stderr[:200]}")
    return json.loads(r.stdout)


def find_adr_file(adr_number: int, root: Path) -> Path | None:
    """找 ADR 文件 by 编号."""
    pattern = f"{adr_number:04d}-*.md"
    for f in (root / ".omo" / "_knowledge" / "decisions").glob(pattern):
        return f
    return None


def apply_typo_fix(adr_path: Path, typo: str, correct: str) -> bool:
    """在 ADR 文件中替换 typo → correct."""
    try:
        content = adr_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if typo not in content:
        return False
    new_content = content.replace(typo, correct)
    adr_path.write_text(new_content, encoding="utf-8")
    return True


def record_history(action: str, items: list[dict]) -> None:
    TYPO_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "items": items,
    }
    with TYPO_HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def rollback(root: Path) -> dict:
    """撤销最近一次 apply (重新读取并 revert)."""
    if not TYPO_HISTORY.exists():
        return {"error": "no apply history"}
    with TYPO_HISTORY.open(encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    if not lines:
        return {"error": "empty apply history"}
    last = json.loads(lines[-1])
    if last.get("action") != "apply":
        return {"error": f"last entry not apply: {last.get('action')}"}
    rolled: list[dict] = []
    skipped: list[dict] = []
    for item in last.get("items", []):
        adr_path = Path(item["adr_path"])
        correct = item["correct"]
        typo = item["typo"]
        if not adr_path.exists():
            skipped.append({"typo": typo, "reason": "ADR 已被删除"})
            continue
        # 反向替换: correct → typo
        if apply_typo_fix(adr_path, correct, typo):
            rolled.append({"typo": typo, "correct": correct, "action": "reverted"})
        else:
            skipped.append({"typo": typo, "reason": "revert failed"})
    record_history("rollback", rolled)
    return {"rolled": rolled, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description="P95: ADR drift TYPO 自动修复")
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true", help="实际修改 ADR 文件")
    parser.add_argument("--rollback", action="store_true", help="撤销最近一次 apply")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    if args.rollback:
        result = rollback(root)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if "error" in result:
            print(f"❌ {result['error']}")
            return 1
        print("=" * 60)
        print("🔙 P95 ADR typo fix rollback")
        print("=" * 60)
        print(f"✅ Rolled: {len(result.get('rolled', []))}")
        for item in result.get("rolled", []):
            print(f"   {item['typo']} → {item['correct']}")
        print(f"⚠️  Skipped: {len(result.get('skipped', []))}")
        for item in result.get("skipped", []):
            print(f"   {item['typo']}  ({item['reason']})")
        return 0

    # 加载分类
    try:
        classify = load_classify(root)
    except Exception as e:
        print(f"❌ 加载分类失败: {e}")
        return 1

    # 过滤 TYPO
    typos = [i for i in classify.get("items", []) if i.get("classification", {}).get("type") == "TYPO"]
    # 提取 correct (从 fix_action 字段或 reason 字段)
    plans: list[dict] = []
    for t in typos:
        msg = t["msg"]
        # msg 格式: "路径不存在: X"
        typo_path = msg.replace("路径不存在: ", "").strip()
        # reason 格式: "可能 typo, 实际文件: <correct_path>"
        reason = t["classification"].get("reason", "")
        correct = None
        m = re.search(r"实际文件: (.+)", reason)
        if m:
            correct = m.group(1).strip()
        if not correct:
            continue
        adr_file = find_adr_file(t["adr_number"], root)
        if not adr_file:
            continue
        plans.append({
            "adr_number": t["adr_number"],
            "adr_path": str(adr_file),
            "typo": typo_path,
            "correct": correct,
        })

    if args.apply:
        applied: list[dict] = []
        skipped: list[dict] = []
        for p in plans:
            adr = Path(p["adr_path"])
            if apply_typo_fix(adr, p["typo"], p["correct"]):
                applied.append(p)
            else:
                skipped.append({**p, "reason": "typo not in ADR content"})
        record_history("apply", applied)
        result = {"applied": applied, "skipped": skipped}
    else:
        result = {"plans": plans, "action": "dry-run"}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print(f"🔧 P95 ADR typo fix ({'APPLY' if args.apply else 'DRY-RUN'})")
    print("=" * 60)
    if args.apply:
        print(f"✅ Applied: {len(result.get('applied', []))}")
        for item in result.get("applied", []):
            print(f"   ADR-{item['adr_number']:04d}: {item['typo']} → {item['correct']}")
        print(f"⚠️  Skipped: {len(result.get('skipped', []))}")
        for item in result.get("skipped", []):
            print(f"   ADR-{item['adr_number']:04d}: {item['typo']} ({item['reason']})")
        print()
        print(f"📜 History: {TYPO_HISTORY}")
        print("   撤销: bin/adr-typo-fix.py --rollback")
    else:
        print(f"📊 TYPO 待修: {len(plans)}")
        for p in plans:
            print(f"   ADR-{p['adr_number']:04d}: {p['typo']} → {p['correct']}")
        print()
        print("   实际应用: bin/adr-typo-fix.py --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
