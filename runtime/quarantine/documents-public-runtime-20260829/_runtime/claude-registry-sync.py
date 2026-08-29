#!/usr/bin/env python3
"""claude-registry-sync.py — CLAUDE-REGISTRY 域版本表生成器

问题: CLAUDE-REGISTRY.md 手抄各域 CLAUDE.md 的版本号/日期, 域文件升级后
注册表不跟 (审计实证: @学习进化 v6.2 vs 实际 v6.3, @家庭生活状态过期 3 周)。

做法: 文件系统驱动 — glob 各域 CLAUDE.md, 从头部抽版本/日期,
重写 CLAUDE-REGISTRY.md 的 AUTOGEN 区块。注册表降级为生成视图,
SSOT = 各域 CLAUDE.md 文件本身。

用法:
  python3 claude-registry-sync.py           # --check: 比对, 漂移 exit 1
  python3 claude-registry-sync.py --write   # 重写 AUTOGEN 区块
v1.0 | 2026-07-02
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = DOCS_ROOT / "@驾驶舱/_control/CLAUDE-REGISTRY.md"
AUTOGEN_BEGIN = "<!-- AUTOGEN:CLAUDE-VERSIONS BEGIN (claude-registry-sync.py --write · 勿手改) -->"
AUTOGEN_END = "<!-- AUTOGEN:CLAUDE-VERSIONS END -->"


def scan_header(f: Path) -> dict:
    head = "\n".join(f.read_text(encoding="utf-8").splitlines()[:12])
    ver = re.search(r"\*\*v(\d+\.\d+)\*\*", head) or re.search(r"\bv(\d+\.\d+)\b", head)
    day = re.search(r"(20\d{2}-\d{2}-\d{2})", head)
    kems = re.search(r"KEMS\s*v(\d+\.\d+)", head)
    return {"version": f"v{ver.group(1)}" if ver else "—",
            "updated": day.group(1) if day else "—",
            "kems": f"KEMS v{kems.group(1)}" if kems else "—"}


def collect() -> tuple[list, list]:
    mains, subs = [], []
    for f in sorted(DOCS_ROOT.glob("@*/CLAUDE.md")):
        mains.append((f.parent.name, scan_header(f)))
    for f in sorted((DOCS_ROOT / "@工作文档").glob("*/CLAUDE.md")):
        subs.append((f"@工作文档/{f.parent.name}", scan_header(f)))
    return mains, subs


def render(mains: list, subs: list) -> str:
    lines = [f"> 生成自各域 CLAUDE.md 头部 · {date.today()} · SSOT = 域文件本身", "",
             f"### 主域 ({len(mains)})", "",
             "| 域 | 版本 | KEMS | 头部日期 |", "|----|:---:|:---:|:---:|"]
    lines += [f"| {n} | **{h['version']}** | {h['kems']} | {h['updated']} |" for n, h in mains]
    lines += ["", f"### @工作文档 子域 ({len(subs)})", "",
              "| 域 | 版本 | KEMS | 头部日期 |", "|----|:---:|:---:|:---:|"]
    lines += [f"| {n} | **{h['version']}** | {h['kems']} | {h['updated']} |" for n, h in subs]
    return "\n".join(lines)


def main() -> int:
    write = "--write" in sys.argv
    mains, subs = collect()
    body = render(mains, subs)
    text = REGISTRY.read_text(encoding="utf-8")
    if AUTOGEN_BEGIN not in text:
        print(f"❌ CLAUDE-REGISTRY 缺 AUTOGEN 标记: {AUTOGEN_BEGIN}")
        return 2
    pre, rest = text.split(AUTOGEN_BEGIN, 1)
    cur, post = rest.split(AUTOGEN_END, 1)
    # 比对时忽略生成日期行
    strip = lambda s: re.sub(r"> 生成自各域.*", "", s).strip()  # noqa: E731
    if strip(cur) == strip(body):
        print(f"✅ 注册表与域文件一致 ({len(mains)} 主域 + {len(subs)} 子域)")
        return 0
    if write:
        REGISTRY.write_text(f"{pre}{AUTOGEN_BEGIN}\n{body}\n{AUTOGEN_END}{post}", encoding="utf-8")
        print(f"✅ 已重写 ({len(mains)} 主域 + {len(subs)} 子域)")
        return 0
    print("🔴 注册表与域文件漂移 — 跑 --write 重生成")
    return 1


if __name__ == "__main__":
    sys.exit(main())
