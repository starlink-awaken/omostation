#!/usr/bin/env python3
"""
eCOS v5 — 极小骨架引导 (ecos-bootstrap)
==========================================
给新用户最少的、最干净的起点。
只搭建框架骨架，不预装任何有外部依赖的脚本。

骨架包含:
  ✅ CLAUDE.md 级联 (claude.md → L4 网关 → 域入口)
  ✅ 3 个核心脚本 (health-check / freshness / brief) — 无外部依赖
  ✅ 目录结构 (5 域 + 知识库)
  ✅ 空白治理体系

脚本扩展: 引导完成后提示如何按需安装更多脚本。

用法:
    python3 ecos-bootstrap.py              # 交互式
    python3 ecos-bootstrap.py --quick      # 快速默认
"""

import sys
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

G = "\033[92m"; C = "\033[96m"; Y = "\033[93m"; B = "\033[1m"; N = "\033[0m"


def ask(prompt: str, default: str = "") -> str:
    val = input(f"  {C}?{N} {prompt}" + (f" [{Y}{default}{N}]" if default else "") + ": ").strip()
    return val if val else default


def progress(current: int, total: int, label: str):
    filled = int(current / total * 20)
    sys.stdout.write(f"\r  {G}{'█' * filled}{'░' * (20 - filled)}{N} {current}/{total}  {label}{' ' * 20}")
    sys.stdout.flush()


# ── 核心脚本: 内嵌，零外部依赖 ──
CORE_SCRIPTS = {
    "ecos-brief.py": """#!/usr/bin/env python3
\"\"\"会话简报 — 聚合当前系统状态到一页。无外部依赖。\"\"\"

import sys, json
from datetime import datetime

def check_freshness(root: str, max_age: int = 60) -> list[str]:
    from pathlib import Path
    stale = []
    for f in Path(root).rglob(\"CLAUDE.md\"):
        if f.is_file() and not f.is_symlink():
            age = (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days
            if age > max_age:
                stale.append(str(f.relative_to(root)))
    return stale

def main():
    root = str(Path.home() / \"Documents\")
    stale = check_freshness(root)
    now = datetime.now()
    
    print(f\"# 会话简报 — {now.strftime('%Y-%m-%d %H:%M')}\")
    print(f\"> eCOS v5 · 自动生成\")
    print()
    print(f\"## 🟢 系统健康\" if not stale else \"## 🟡 保鲜告警\")
    print(f\"CLAUDE.md 文件: {len(stale)} 过期\" if stale else \"全部新鲜 ✅\")
    print(f\"检查时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\")
    print()
    
    if stale:
        print(\"## ⚠️ 过期文件\")
        for s in stale:
            age = (datetime.now() - datetime.fromtimestamp(
                (Path.home() / \"Documents\" / s).stat().st_mtime)).days
            print(f\"- {s} ({age}d)\")
    
    print()
    print(\"---\")
    print(\"> 下一步: python3 驾驶舱/scripts/ecos-health-check.py\")

if __name__ == \"__main__\":
    from pathlib import Path
    main()
""",
    "ecos-health-check.py": """#!/usr/bin/env python3
\"\"\"一键健康检查 — 检查基础系统健康。无外部依赖。\"\"\"

from pathlib import Path
from datetime import datetime

CHECKS = [
    (\"L4 网关\", \"CLAUDE_COWORK_GLOBAL.md\"),
    (\"驾驶舱入口\", \"驾驶舱/CLAUDE.md\"),
    (\"Vault 入口\", \"学习进化/CLAUDE.md\"),
    (\"DASHBOARD\", \"驾驶舱/DASHBOARD.md\"),
    (\"claude.md\", \"claude.md\"),
]

DOCS = Path.home() / \"Documents\"

print(\"=\" * 48)
print(\"  eCOS v5 — 健康检查\")
print(\"=\" * 48)

passed = 0
for name, path in CHECKS:
    p = DOCS / path
    ok = p.exists() and not p.is_symlink()
    print(f\"  {'✅' if ok else '❌'} {name}: {path}\")
    if ok:
        passed += 1

# CLAUDE.md 保鲜
count = sum(1 for f in DOCS.rglob(\"CLAUDE.md\") if f.is_file() and not f.is_symlink())
print(f\"  ✅ CLAUDE.md 文件: {count} 个\")

print(f\"\\n  结果: {passed}/{len(CHECKS)} 通过\")
print(\"=\" * 48)
sys.exit(0 if passed == len(CHECKS) else 1)
""",
    "ecos-whoami.py": """#!/usr/bin/env python3
\"\"\"系统自述 — 我是谁，我有什么。\"\"\"

from pathlib import Path
from datetime import datetime

DOCS = Path.home() / \"Documents\"
now = datetime.now()

print()
print(f\"  eCOS v5 — 系统自述\")
print(f\"  时间: {now.strftime('%Y-%m-%d %H:%M')}\")
print()
print(f\"  📍 位置: {DOCS}\")
print()

# 检查域
for domain in [\"驾驶舱\", \"学习进化\", \"工作文档\", \"家庭生活\", \"工具箱\", \"领域知识库\"]:
    d = DOCS / domain
    exists = d.exists()
    files = len(list(d.rglob(\"*\"))) if exists else 0
    print(f\"  {'✅' if exists else '❌'} {domain:10s} ({files} 文件)\")

print()
print(f\"  下一步: cat ~/Documents/驾驶舱/CLAUDE.md\")
print(f\"  手册:   cat ~/Documents/驾驶舱/OPS.md\")
print()
""",
}

DOC_TEMPLATES = {
    "驾驶舱/CLAUDE.md": """# 驾驶舱 — Agent 操作契约

> 定义 Agent 在驾驶舱的行为规则

## §0 快速路由

| 意图 | 动作 |
|------|------|
| 看全局状态 | 读 DASHBOARD.md |
| 看跨域信号 | 读 SIGNALS.md |
| 查看健康 | `python3 scripts/ecos-health-check.py` |
""",
    "学习进化/CLAUDE.md": """# 学习进化 — Vault 入口

> L1 | 知识面主体。三层：1-active / 2-knowledge / 3-archive
""",
    "驾驶舱/SIGNALS.md": "# SIGNALS — 跨域信号\n\n> 跨域影响在此登记。\n",
    "学习进化/STATE.md": "# STATE — Vault 状态\n\n> Vault 子模块健康度。\n",
    "领域知识库/ENTITIES.md": """# 领域知识库 — ENTITIES 索引

| 子域 | 实体类型 |
|------|---------|
| 人物/ | Person |
| 组织/ | Organization |
| 系统/ | System |
| 关系/ | Relation |
""",
}


def generate_gateway(name: str, role: str, has_work: bool, has_family: bool) -> str:
    """生成 L4 网关"""
    now = datetime.now().strftime("%Y-%m-%d")
    domains = "| **驾驶舱** | `驾驶舱/CLAUDE.md` | 全局状态·任务·治理 |\n"
    domains += "| **Vault** | `学习进化/CLAUDE.md` | 知识系统·创作·经验 |\n"
    if has_work:
        domains += "| **工作文档** | `工作文档/CLAUDE.md` | 业务文档 |\n"
    if has_family:
        domains += "| **家庭生活** | `家庭生活/CLAUDE.md` | 日常管理 |\n"

    return f"""# CLAUDE_COWORK_GLOBAL.md — L4 自我层网关

> **L4 网关** — 身份锚 + 域路由 + 执行纪律
> eCOS v5 | {now} | 由 ecos-bootstrap 生成

---

## §0 我是谁

**{name}** — {role}

---

## §1 域路由

{domains}
---

## §2 启动链

Agent 启动后按顺序执行：
1. `python3 驾驶舱/scripts/ecos-brief.py`
2. 读 `驾驶舱/brief.md`
3. 读本文件
4. 读 `驾驶舱/DASHBOARD.md`
5. 目标域 CLAUDE.md

---

## §3 可用工具

| 工具 | 用法 |
|------|------|
| 健康检查 | `python3 驾驶舱/scripts/ecos-health-check.py` |
| 会话简报 | `python3 驾驶舱/scripts/ecos-brief.py` |
| 系统自述 | `python3 驾驶舱/scripts/ecos-whoami.py` |

---

## §4 核心原则

1. **SSOT** — 每个事实只有一个权威位置
2. **启动链必读** — 每次会话从 brief 开始
3. **治理可验证** — 一键 health-check

---

_此文件由 ecos-bootstrap 生成。编辑 §0 更新你的信息。_
"""


def main():
    # ── 解析参数 ──
    quick = "--quick" in sys.argv
    target = Path.home() / "Documents"
    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i + 1 < len(sys.argv):
            target = Path(sys.argv[i + 1]).expanduser().resolve()

    # 源路径: 此脚本所在目录
    src = Path(__file__).parent.resolve()

    # ── 头部 ──
    print(f"\n{B}  eCOS v5 — 极小骨架引导{N}")
    print(f"  只搭框架，不填内容。扩展按需安装。\n")

    # ── 交互 ──
    if quick:
        name, role = "新用户", "个人知识工作者"
        has_work, has_family = True, True
        print(f"  {Y}⚡ 快速模式 — 默认值{N}\n")
    else:
        name = ask("你的名字", "新用户")
        role = ask("一句话身份", "个人知识工作者")
        has_work = ask("需要工作文档域? (y/n)", "y").lower() == "y"
        has_family = ask("需要家庭生活域? (y/n)", "y").lower() == "y"

    # ── 构建 ──
    total = 5
    print(f"\n  {B}构建中...{N}\n")

    # 1. 目录
    progress(1, total, "创建目录")
    dirs = [
        "驾驶舱/scripts", "驾驶舱/CARDS",
        "学习进化/1-active/自我剖析", "学习进化/1-active/收件箱",
        "学习进化/2-knowledge/体系", "学习进化/2-knowledge/基建架构",
        "学习进化/2-knowledge/经验积累/lessons",
        "学习进化/3-archive/资料库", "学习进化/3-archive/灵感顿悟",
        "工具箱", "领域知识库",
    ]
    if has_work:
        dirs.append("工作文档")
    if has_family:
        dirs.append("家庭生活")
    for d in dirs:
        (target / d).mkdir(parents=True, exist_ok=True)
    time.sleep(0.2)
    progress(1, total, f"✅ {len(dirs)} 个目录")

    # 2. 核心脚本
    script_count = 0
    for sname, content in CORE_SCRIPTS.items():
        p = target / "驾驶舱/scripts" / sname
        if not p.exists():
            p.write_text(content)
            script_count += 1
    time.sleep(0.2)
    progress(2, total, f"✅ {script_count} 个核心脚本")

    # 3. 网关
    gw = generate_gateway(name, role, has_work, has_family)
    (target / "CLAUDE_COWORK_GLOBAL.md").write_text(gw)
    if not (target / "claude.md").exists():
        (target / "claude.md").symlink_to("CLAUDE_COWORK_GLOBAL.md")
    time.sleep(0.2)
    progress(3, total, "✅ L4 网关 + claude.md")

    # 4. 文档
    for docpath, doc_content in DOC_TEMPLATES.items():
        p = target / docpath
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {docpath.split('/')[-1]}\n\n> ecos-bootstrap 生成 | {datetime.now().strftime('%Y-%m-%d')}\n\n{doc_content}")
    (target / "驾驶舱/DASHBOARD.md").write_text(
        f"# DASHBOARD — {name} 的全局状态\n\n"
        f"> ecos-bootstrap 生成 | {datetime.now().strftime('%Y-%m-%d')}\n"
    )
    time.sleep(0.2)
    progress(4, total, "✅ 入口文档")

    # 5. 运行时
    ecos_dir = Path.home() / ".ecos"
    for sub in ["runtime", "events", "sla", "sessions"]:
        (ecos_dir / sub).mkdir(parents=True, exist_ok=True)
    (ecos_dir / "runtime/registry.json").write_text(
        '{"services":[],"updated_at":"' + datetime.now().isoformat() + '"}')
    time.sleep(0.2)
    progress(5, total, "✅ 运行时目录")
    print()

    # ── 完成 ──
    print(f"\n  {B}{'─'*48}{N}")
    print(f"  {B}🎉 {name} 的 eCOS 骨架已就绪{N}")
    print(f"  {B}{'─'*48}{N}")
    print(f"  📍  {target}")
    print(f"  🛠️   {script_count} 个核心脚本")
    print(f"  📁  {len(dirs)} 个目录")
    print(f"\n  {B}立即开始:{N}")
    print(f"    python3 驾驶舱/scripts/ecos-brief.py")
    print(f"    python3 驾驶舱/scripts/ecos-whoami.py")

    print(f"\n  {C}扩展脚本 (按需安装):{N}")
    print(f"    从 eCOS 源安装全部治理脚本:")
    print(f"    python3 ecos-bootstrap.py --from /path/to/full/ecos/scripts --target ~/Documents")
    print(f"    或: 从 {src} 逐个复制需要的脚本到 ~/Documents/驾驶舱/scripts/")

    print(f"\n  {Y}💡 骨架只包含基础治理。需要更高级的功能时，再安装扩展。{N}")
    print(f"  {'─'*48}\n")


if __name__ == "__main__":
    main()
