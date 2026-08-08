#!/usr/bin/env python3
"""盯住"写机器级配置"的脚本集合 — 新成员必须经过审阅。

2026-08-08 两起事故的根因是同一个组合:
用 `__file__` 反推仓库根 + 往 ~/Library/LaunchAgents 这类**机器级**路径写。
worktree 是临时的, 把它的路径写进机器级配置, 清理后就成死路径 —— 而且
当场看不出来, 要等下次重启才发现服务起不来。
(实例: gen-service-configs 把 omlx 网关等 7 个 plist 写成
 `<worktree>/~/.local/bin/omlx-gw-guard`, 并被不同 worktree 反复改写。)

**为什么是基线机制而不是语义判断**

先试过静态推断"这个机器级路径是不是用派生根拼的", 两版都不准:
第一版把仓内的 `projects/agora/etc/...` 当成 `/etc/` 报了 4 个假阳性;
第二版反过来漏掉了真正有问题的 install-watch-agent.py。
一个总在报错报不准的检查, 很快就没人看了 —— 比没有还糟。

所以这里不猜语义, 只做一件能做准的事: **检测集合变化**。
谁写机器级配置是可以精确列出的; 新脚本加入这个集合时, 让人来判一次。

用法:
  python3 bin/ssot/machine-config-write-lint.py            # 检查
  python3 bin/ssot/machine-config-write-lint.py --list     # 列出当前集合
  python3 bin/ssot/machine-config-write-lint.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # 本脚本只读仓内, 反推正确
SCAN = ["bin"]

MACHINE = re.compile(r"Library/LaunchAgents|Library/LaunchDaemons|crontab|\.local/(?:bin|state|share)")
WRITE = re.compile(
    r"write_text|write_bytes|plistlib\.dump|shutil\.copy|shutil\.move|"
    r"os\.replace|os\.rename|\bopen\([^)]*['\"][wa]|"
    r"launchctl\s+(?:bootstrap|load|unload|bootout)"
)

# 已审阅名单 —— 值是"为什么它是安全的 / 它的现状"。
# 新脚本进入集合时不在这里, 就会被拦下要求审阅。
REVIEWED: dict[str, str] = {
    "bin/mof/gen-service-configs.py":
        "已加固: WORKSPACE 锚定规范检出 + ~ 展开 + 未知 interpreter 报错 + 写前校验路径存在",
    "bin/svc/service_view.py":
        "分工正确: LaunchAgents 用绝对 HOME, 仓内 SSOT 才用派生根",
    "bin/gac/install-watch-agent.py":
        "已加固: WORKSPACE=canonical_root(), 从 worktree 跑也执行规范检出的生成器",
    "bin/ssot/machine-config-write-lint.py": "本文件",
}


def collect() -> list[str]:
    out = []
    for sd in SCAN:
        d = ROOT / sd
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix not in (".py", ".sh"):
                continue
            if "__pycache__" in str(f) or "/_archive/" in str(f):
                continue
            try:
                t = f.read_text(errors="ignore")
            except OSError:
                continue
            if MACHINE.search(t) and WRITE.search(t):
                out.append(str(f.relative_to(ROOT)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    current = collect()
    if args.list:
        print(f"写机器级配置的脚本 ({len(current)}):")
        for f in current:
            print(f"  {f}\n     {REVIEWED.get(f, '未审阅')}")
        return 0

    newcomers = [f for f in current if f not in REVIEWED]
    gone = [f for f in REVIEWED if f not in current and f != "bin/ssot/machine-config-write-lint.py"]

    if args.json:
        print(json.dumps({"ok": not newcomers, "current": current,
                          "newcomers": newcomers, "stale_entries": gone},
                         ensure_ascii=False, indent=2))
        return 0 if not newcomers else 1

    if gone:
        print(f"ℹ️  名单里有 {len(gone)} 项已不再写机器级配置(可从 REVIEWED 移除): {gone}")
    if not newcomers:
        print(f"machine-config-write-lint: PASS ({len(current)} 个脚本, 均已审阅)")
        return 0

    print(f"machine-config-write-lint: FAIL ({len(newcomers)} 个未审阅)\n", file=sys.stderr)
    for f in newcomers:
        print(f"  {f}", file=sys.stderr)
    print(
        "\n  这些脚本会写 ~/Library/LaunchAgents 等机器级路径。请确认:\n"
        "    路径是用 __file__/parents 反推的仓库根拼出来的吗?\n"
        "      是 → 改用 bin/lib/repo_root.canonical_root()\n"
        "      否 → 加进 REVIEWED 并写明理由\n"
        "  worktree 是临时的; 机器级配置指向它, 清理后就是死路径。\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
