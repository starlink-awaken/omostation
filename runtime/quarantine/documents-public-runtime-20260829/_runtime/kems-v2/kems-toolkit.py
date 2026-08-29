#!/usr/bin/env python3
"""
kems-toolkit.py — KEMS 域工具集（统一版）

供所有 KEMS 文档域共用。以 --root <域根路径> 参数化，对任意域执行：
  --mode check   强制更新检查（目录 hash 比对 + inbox 待分类检测 + 状态基线）
  --mode health  健康度巡检（老化知识 / inbox 滞留 / 待分类 / 信号统计）

用法：
  python3 kems-toolkit.py --root ~/Documents/@工作文档/卫健委
  python3 kems-toolkit.py --root ~/Documents/@工作文档/卫健委 --mode health
  python3 kems-toolkit.py --root <域根> --mode check --dry-run   # 只读不写状态

规范位置：@公共/_runtime/kems-toolkit.py | v1.0 | 2026-07-31
  · 跨域共享逻辑的唯一实现，域内不复制逻辑，只传参。
  · 当前会话无法直接写入 @公共，本文件暂驻域内 _runtime/；
    迁移命令：cp _runtime/kems-toolkit.py ~/Documents/@公共/_runtime/
    迁移后删除域内副本，包装脚本 check-kems-update.py 会自动优先引用 @公共 版。
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DRY_RUN = False  # 由 __main__ 依据 --dry-run 设置


def resolve_root(raw):
    """解析域根：支持绝对路径与 ~ 展开；目录必须存在。"""
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        sys.exit(f"❌ 域根不存在: {p}")
    return p


def find_inbox(domain):
    """兼容两种 inbox 布局：_storage/01-Inbox（卫健委/国转中心）或 _storage/inbox。"""
    for name in ("01-Inbox", "inbox"):
        p = domain / "_storage" / name
        if p.is_dir():
            return p
    return domain / "_storage" / "01-Inbox"


def _banner(title, domain):
    print("=" * 60)
    print(f"{title}")
    print(f"   域: {domain}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


# ── mode: check — 强制更新检查 ──
def run_check(domain, state_file, extra_inbox=None):
    inbox = find_inbox(domain)
    paths = {
        "inbox": inbox,
        "knowledge": domain / "_knowledge",
        "entities": domain / "_entities" / "entities",
        "control": domain / "_control",
    }
    # 前店后厂缓冲区（~/Documents/_inbox）——经 --inbox-extra 传入，不硬编码
    if extra_inbox:
        ep = Path(extra_inbox).expanduser()
        if ep.is_dir():
            paths["buff_inbox"] = ep

    hashes = {}
    for name, path in paths.items():
        if path.is_dir():
            try:
                files = sorted(f for f in os.listdir(path) if not f.startswith("."))
                h = hashlib.md5()
                for f in files:
                    fp = path / f
                    if fp.is_file():
                        h.update(f.encode())
                        h.update(str(fp.stat().st_mtime).encode())
                hashes[name] = h.hexdigest()[:8]
            except OSError:
                hashes[name] = "error"
        else:
            hashes[name] = "not_found"

    saved = {}
    if state_file.is_file():
        try:
            saved = json.loads(state_file.read_text())
        except (json.JSONDecodeError, OSError):
            saved = {}

    changes = []
    for name, h in hashes.items():
        sh = saved.get("hashes", {}).get(name, "")
        if sh and sh != h and h != "not_found":
            changes.append(f"⚠️ {name} 发生变化")

    manifest = inbox / "inbox-manifest.md"
    pending = manifest.read_text().count("📥 待分类") if manifest.is_file() else 0
    if pending:
        changes.append(f"⚠️ inbox-manifest 有 {pending} 条待分类")

    _banner("🔍 KEMS 强制更新检查", domain)
    if not changes and saved.get("last_check"):
        print("\n✅ 系统状态正常，无需更新")
        print(f"   上次检查: {saved['last_check']}")
    else:
        if changes:
            print("\n❗ 检测到以下变化：")
            for c in changes:
                print(f"   {c}")
            print("\n⚠️ 请执行更新：确认变化 → 更新KEMS知识 → 更新signals → 更新实体索引 → 提交记录")
        if not saved.get("last_check"):
            print("\n🆕 首次运行，已建立检查基线")

    if not DRY_RUN:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(
                {"last_check": datetime.now().isoformat(), "hashes": hashes},
                indent=2,
                ensure_ascii=False,
            )
        )
    print("\n" + "=" * 60)
    return len(changes) > 0


# ── mode: health — 健康度巡检 ──
def run_health(domain):
    now = datetime.now()

    stale = []
    know = domain / "_knowledge"
    if know.is_dir():
        for root, dirs, files in os.walk(know):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                # 目录导航 README.md 为归档目录占位说明，mtime 旧属设计正常，不计入老化知识
                if f.endswith(".md") and f != "README.md":
                    fp = Path(root) / f
                    age = (now - datetime.fromtimestamp(fp.stat().st_mtime)).days
                    if age > 30:
                        stale.append((f, age))

    stale_inbox = []
    inbox = find_inbox(domain)
    if inbox.is_dir():
        for f in inbox.iterdir():
            if f.is_file() and not f.name.startswith("."):
                age = (now - datetime.fromtimestamp(f.stat().st_mtime)).days
                if age > 7:
                    stale_inbox.append((f.name, age))

    manifest = inbox / "inbox-manifest.md"
    pending = manifest.read_text().count("📥 待分类") if manifest.is_file() else 0

    signals_file = domain / "_control" / "signals.md"
    signal_count = 0
    if signals_file.is_file():
        content = signals_file.read_text()
        signal_count = content.count("signal-") + content.count("- message:")

    _banner("🔍 KEMS 知识库健康度巡检", domain)
    total = 0
    if stale:
        print(f"\n⚠️ 老化知识（>30天）：{len(stale)}个")
        for f, age in stale[:5]:
            print(f"   · {f}（{age}天）")
        if len(stale) > 5:
            print(f"   ... 共{len(stale)}个")
        total += len(stale)
    else:
        print("\n✅ 知识库新鲜度正常")

    if stale_inbox:
        print(f"\n⚠️ Inbox滞留（>7天）：{len(stale_inbox)}个")
        for f, age in stale_inbox:
            print(f"   · {f}（{age}天）")
        total += len(stale_inbox)
    else:
        print("\n✅ Inbox处理及时")

    if pending:
        print(f"\n⚠️ 待分类文件：{pending}个")
        total += pending
    else:
        print("\n✅ 无待分类文件")

    print(f"\n📊 活跃信号：{signal_count}个")
    print("\n" + "=" * 60)
    if total == 0:
        print("✅ 知识库健康状况：良好")
    else:
        print(f"⚠️ 共发现 {total} 个问题，建议处理")
        print("   优先：更新老化知识 → 归档inbox → 处理待分类")
    print("=" * 60)
    return total


def main():
    global DRY_RUN
    ap = argparse.ArgumentParser(description="KEMS 域工具集（统一版）")
    ap.add_argument("--root", required=True, help="域根绝对路径（如 ~/Documents/@工作文档/卫健委）")
    ap.add_argument("--mode", choices=["check", "health"], default="check")
    ap.add_argument("--inbox-extra", default=None, help="额外检查的缓冲区目录（如 ~/Documents/_inbox）")
    ap.add_argument("--dry-run", action="store_true", help="只读模式，不写状态文件")
    args = ap.parse_args()

    DRY_RUN = args.dry_run
    domain = resolve_root(args.root)
    state_file = domain / "_control" / ".kems_check_state.json"

    if args.mode == "check":
        sys.exit(1 if run_check(domain, state_file, args.inbox_extra) else 0)
    else:
        sys.exit(1 if run_health(domain) > 0 else 0)


if __name__ == "__main__":
    main()
