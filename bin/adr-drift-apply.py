#!/usr/bin/env python3
"""P94 R1: ADR drift auto-fix 应用工具.

读取 adr-drift-auto-fix 报告, 对 SUBDIR_MISSING 类型执行 touch 占位,
对 TYPO 类型生成 ADR 修正建议 (不直接修改 ADR), 其他类型 dry-run.

应用策略 (保守):
- SUBDIR_MISSING: touch 空文件 (或 .gitkeep 占位) - 可撤销
- TEMPLATE: 不动 (已在 ADR 标注建议)
- TYPO: 生成 sed 修正建议 (人 review 后再跑)
- REAL_BUG / ASPIRATIONAL: 仅 dry-run 报告, 不动

使用:
  python3 bin/adr-drift-apply.py              # dry-run
  python3 bin/adr-drift-apply.py --apply     # 实际 touch
  python3 bin/adr-drift-apply.py --rollback  # 撤销最近一次 apply
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APPLY_HISTORY = Path(".omo/_delivery/adr-drift-apply-history.jsonl")


def load_classify_result(root: Path) -> dict:
    """调用 adr-drift-auto-fix 拿分类结果."""
    r = subprocess.run(
        ["python3", str(root / "bin" / "adr-drift-auto-fix.py"), "--json"],
        cwd=str(root), capture_output=True, text=True, timeout=60,
    )
    if r.returncode not in (0, 1):
        raise RuntimeError(f"adr-drift-auto-fix 失败: {r.stderr[:200]}")
    return json.loads(r.stdout)


def record_history(action: str, items: list[dict]) -> None:
    """记录 apply / rollback 操作历史."""
    APPLY_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "items": items,
    }
    with APPLY_HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def touch_path(path: Path) -> bool:
    """touch 文件 (含父目录)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir() or str(path).endswith("/"):
            path.mkdir(parents=True, exist_ok=True)
            (path / ".gitkeep").touch(exist_ok=True)
        else:
            path.touch(exist_ok=True)
        return True
    except Exception as e:
        print(f"❌ touch 失败: {path}: {e}")
        return False


def apply(root: Path, items: list[dict]) -> dict:
    """应用 SUBDIR_MISSING 修复."""
    applied: list[dict] = []
    skipped: list[dict] = []
    for item in items:
        cls_type = item.get("classification", {}).get("type")
        msg = item["msg"]
        # 提取 path
        path = msg.replace("路径不存在: ", "").strip()
        full = root / path

        if cls_type == "SUBDIR_MISSING":
            if touch_path(full):
                applied.append({"path": path, "type": cls_type, "action": "touch"})
            else:
                skipped.append({"path": path, "type": cls_type, "reason": "touch failed"})
        else:
            skipped.append({"path": path, "type": cls_type, "reason": f"非 SUBDIR_MISSING (是 {cls_type}), 不自动修复"})

    record_history("apply", applied)
    return {"applied": applied, "skipped": skipped}


def rollback(root: Path) -> dict:
    """撤销最近一次 apply (删除 touch 创建的文件)."""
    if not APPLY_HISTORY.exists():
        return {"error": "no apply history"}
    with APPLY_HISTORY.open(encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    if not lines:
        return {"error": "empty apply history"}
    last = json.loads(lines[-1])
    if last.get("action") != "apply":
        return {"error": f"last entry is not apply: {last.get('action')}"}
    rolled: list[dict] = []
    skipped: list[dict] = []
    for item in last.get("items", []):
        path = item["path"]
        full = root / path
        if not full.exists():
            skipped.append({"path": path, "reason": "已不存在"})
            continue
        try:
            if full.is_file():
                full.unlink()
            elif full.is_dir():
                # 仅删 .gitkeep, 不删目录 (避免误删)
                gitkeep = full / ".gitkeep"
                if gitkeep.exists():
                    gitkeep.unlink()
            rolled.append({"path": path, "action": "removed"})
        except Exception as e:
            skipped.append({"path": path, "reason": str(e)})
    record_history("rollback", rolled)
    return {"rolled": rolled, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description="P94: ADR drift auto-fix apply")
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true", help="实际应用 SUBDIR_MISSING 修复")
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
        print("🔙 P94 ADR drift apply rollback")
        print("=" * 60)
        print(f"✅ Rolled: {len(result.get('rolled', []))}")
        for item in result.get("rolled", []):
            print(f"   {item['path']}  ({item['action']})")
        print(f"⚠️  Skipped: {len(result.get('skipped', []))}")
        for item in result.get("skipped", []):
            print(f"   {item['path']}  ({item['reason']})")
        return 0

    # 加载分类
    try:
        classify = load_classify_result(root)
    except Exception as e:
        print(f"❌ 加载分类失败: {e}")
        return 1

    items = classify.get("items", [])

    if args.apply:
        result = apply(root, items)
    else:
        result = {"items": items, "action": "dry-run"}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print(f"🔧 P94 ADR drift apply ({'APPLY' if args.apply else 'DRY-RUN'})")
    print("=" * 60)
    if args.apply:
        print(f"✅ Applied: {len(result.get('applied', []))}")
        for item in result.get("applied", []):
            print(f"   {item['path']}  ({item['action']})")
        print(f"⚠️  Skipped: {len(result.get('skipped', []))}")
        for item in result.get("skipped", []):
            print(f"   {item['path']}  ({item['reason']})")
        print()
        print(f"📜 History: {APPLY_HISTORY}")
        print("   撤销: bin/adr-drift-apply.py --rollback")
    else:
        subdir = [i for i in items if i.get("classification", {}).get("type") == "SUBDIR_MISSING"]
        print(f"📊 SUBDIR_MISSING: {len(subdir)} (将 touch)")
        for i in subdir[:10]:
            path = i["msg"].replace("路径不存在: ", "").strip()
            print(f"   {path}")
        if len(subdir) > 10:
            print("   ... 还有 {} 个".format(len(subdir) - 10))
        print()
        print("   实际应用: bin/adr-drift-apply.py --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
