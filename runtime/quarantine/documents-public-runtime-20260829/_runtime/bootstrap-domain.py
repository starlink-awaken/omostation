#!/usr/bin/env python3
"""
域引导工具 — 基于 DOMAIN-META-MODEL 创建新域骨架

用法:
  python3 bootstrap-domain.py --name @项目名 --type Functional --desc "项目描述" [--parent @聚合域] [--base ~/mnt]

域类型:
  Aggregate    聚合域    不自持内容，路由到子域
  Functional   功能域    自持全量内容，6 面完整
  Infrastructure 基础设施 被继承引用
  Sub          子域      在聚合域下，独立 KEMS 六面
  Transient    瞬时域    暂存中转

示例:
  python3 bootstrap-domain.py --name @新人设 --type Functional --desc "新项目启动"
  python3 bootstrap-domain.py --name 子模块 --type Sub --parent @项目 --desc "子模块"
"""

import os
import sys
import argparse
from datetime import datetime

TEMPLATES = {
    "Aggregate": '''# CLAUDE.md — {name}

> **（L4 文档域）聚合入口** | {desc}
> **v1.0** | 继承 @公共/_control/CLAUDE-公约.md | {date}
> 与 ~/Documents/CLAUDE.md (L4 网关) 配合

---

## §0 入场动作

```
1. 查——用户要找哪个子域？
   → 子域列表见 §1
2. 路由到对应子域并执行其入场动作
```

## §1 子域路由

| 子域 | 入口 |
|------|------|

---

> **全局注册表**: MCP → `@公共/_control/MCP-REGISTRY.md` · Skill → `@公共/_control/SKILL-INDEX.md` · 路由 → `@公共/_control/ROUTING.md`
''',

    "Functional": '''# CLAUDE.md — {name}

> **（L4 文档域）功能域** | {desc}
> **v1.0** | 继承 @公共/_control/CLAUDE-公约.md | {date}
> 与 ~/Documents/CLAUDE.md (L4 网关) 配合

---

## §0 SSOT 声明

| 内容类型 | SSOT 位置 | 说明 |
|---------|----------|------|
| 域状态 | `_control/STATUS.md` | 三态判定 |
| 域健康度 | `_control/STATE.md` | 项目·瓶颈·下一步 |
| 元事实 | `_control/MEMORY.md` | 跨会话不变信息 |
| 时间线 | `_control/TIMELINE.md` | 事件序列 |
| 信号 | `_control/signals.md` | 信号队列 |
| 控制规则 | `_control/control-rules.md` | CR01-CRN 映射 |

**公约继承**: 六平面定义·入口协议·SSOT 规范·版本命名·维护格式·入场动作·行为规则框架 → `@公共/_control/CLAUDE-公约.md`

---

## §0a 入场动作

```
1. STATUS.md   → 系统三态判定
2. STATE.md    → 域健康度
3. MEMORY.md   → 元事实
4. signals.md  → 最新信号
5. control-rules.md → 规则映射
6. TIMELINE.md → 事件时间线
```

---

## §1 场景路由

| 场景 | 怎么做 |
|------|--------|

---

## §2 关联域

| 域 | 关系 |
|----|------|

---

## §3 维护

最后更新: {date} | 下次审查: {next_date}

---

> **全局注册表**: MCP → `@公共/_control/MCP-REGISTRY.md` · Skill → `@公共/_control/SKILL-INDEX.md` · 路由 → `@公共/_control/ROUTING.md`
> **域元模型**: `@公共/_control/DOMAIN-META-MODEL.md`
''',

    "Sub": '''# CLAUDE.md — {name}

> **L4 (子域)** | {parent} 子域 | {desc}
> **v1.0** | 继承 @公共/_control/CLAUDE-公约.md | {date}
> 与 ~/Documents/CLAUDE.md (L4 网关) 配合

---

## §0 SSOT 声明

| 内容类型 | SSOT 位置 | 说明 |
|---------|----------|------|
| 域状态 | `_control/STATUS.md` | 三态判定 |
| 域健康度 | `_control/STATE.md` | 项目状态 |
| l4-kernel | `_control/l4-kernel.md` | **KEMS v7.1 域内核** |
| 跨域接口 | `_control/l4-kernel.md §3` | 父域+对等域 |

**公约继承**: → `@公共/_control/CLAUDE-公约.md`
**KEMS 治理**: → 引用 `@公共/_control/l4-kernel.md` v1.0

---

## §0a 入场动作

```
1. STATUS.md → 三态判定
2. STATE.md  → 健康度
3. l4-kernel.md → 域内核(消费 @公共 l4-kernel v1.0)
```

---

> **全局注册表**: MCP → `@公共/_control/MCP-REGISTRY.md` · Skill → `@公共/_control/SKILL-INDEX.md`
''',

    # KEMS v7.1 新增:文件库类型
    "Filelib": '''# CLAUDE.md — {name}

> **L4 (文件库)** | {desc}
> **v1.0** | 继承 @公共/_control/CLAUDE-公约.md | {date}
> 文件库类型:仅供查询引用,无活跃知识管理

---

## §0 SSOT 声明

| 内容类型 | SSOT 位置 | 说明 |
|---------|----------|------|
| 域状态 | `_control/STATE.md` | filelib 状态 |
| 文件清单 | 各子目录 | PDF/docx/xls/zip |

**公约继承**: → `@公共/_control/CLAUDE-公约.md`

---

## §0a 入场动作

```
1. STATE.md → filelib 状态
2. 直接搜索文件名定位文件
3. 引用时使用完整路径
```

---

> **本域不维护**: _knowledge / _entities / _runtime(纯文件库)
> **全局注册表**: MCP → `@公共/_control/MCP-REGISTRY.md` · Skill → `@公共/_control/SKILL-INDEX.md`
''',
}

CONTROL_FILES = {
    "STATUS.md": '''---
title: 系统三态
description: {name} 健康度判定。
created: {date}
---

# STATUS — 系统三态

## 当前状态：STABLE 🟢
''',

    "STATE.md": '''---
title: 域状态
description: {name} 状态快照。
created: {date}
---

# STATE — 域健康度
''',

    "MEMORY.md": '''---
title: 元事实
description: {name} 跨会话元事实。
created: {date}
---

# MEMORY — 元事实与指针
''',

    "TIMELINE.md": '''---
title: 时间线
description: {name} 事件时间线。
created: {date}
---

# TIMELINE — 事件时间线

| 日期 | 事件 |
|------|------|
| {date} | 域初始化 |
''',

    "signals.md": '''---
signals: []
---
''',

    "control-rules.md": '''---
title: 控制规则
description: {name} 控制规则。
created: {date}
---

# 控制规则表

| ID | 输入 | 动作 |
|----|------|------|
| CR01 | 新信号到达 | 追加至 signals.md |
''',
}


# KEMS v7.1 新增:l4-kernel 模板
L4_KERNEL_TEMPLATE = '''---
title: l4-kernel — {name}
description: KEMS v7.1 域内核 · type={dtype} · 消费 @公共 l4-kernel v1.0。
status: 已采纳
type: kernel
owner: 夏明星
created: {date}
last-reviewed: {date}
tags: [l4-kernel, KEMS-v7.1]
---

# l4-kernel — {name}

> **{dtype} 域 l4-kernel** | v1.0 · {date}
> **SSOT**:`@公共/_control/l4-kernel.md` v1.0(主内核)
> **本文件**:本地化适配 — 父域 {parent}

---

## §1 本地化

| 维度 | 内容 |
|------|------|
| type | **{dtype}** |
| 父域 | {parent} |
| 描述 | {desc} |

## §2 控制器

| 控制器 | 状态 |
|--------|:---:|
| sensors.md | (待建) |
| control-rules.md | ✅ |
| executor-rules.md | (待建) |
| **l4-kernel.md** | ✅(本文件) |

## §3 跨域接口

消费 `@公共/_control/l4-kernel.md` v1.0 §2 协议。

## §4 关联

| 内容 | 路径 |
|------|------|
| 主内核 | `@公共/_control/l4-kernel.md` v1.0 |
| 公约 | `@公共/_control/CLAUDE-公约.md` v2.1 |

---

*生成自 bootstrap-domain.py · KEMS v7.1 模板*
'''


def run():
    parser = argparse.ArgumentParser(description="域引导工具 — 创建新域骨架 (KEMS v7.1)")
    parser.add_argument("--name", required=True, help="域名，如 @项目或 子模块")
    parser.add_argument("--type", required=True, choices=["Aggregate", "Functional", "Infrastructure", "Sub", "Transient", "Filelib"], help="域类型(v7.1 新增 Filelib)")
    parser.add_argument("--desc", default="新建域", help="域描述")
    parser.add_argument("--parent", default=None, help="父聚合域（仅 Sub 类型需要）")
    parser.add_argument("--base", default=os.path.expanduser("~/mnt"), help="基准路径")
    parser.add_argument("--l4-kernel", action="store_true", help="生成 l4-kernel.md(KEMS v7.1 强制)")
    
    args = parser.parse_args()
    name = args.name
    dtype = args.type
    desc = args.desc
    parent = args.parent
    base = os.path.expanduser(args.base)
    
    # Determine directory path
    if dtype == "Sub":
        if not parent:
            print("❌ Sub 类型必须指定 --parent")
            sys.exit(1)
        dir_name = name
        full_path = os.path.join(base, "Documents", parent.lstrip("@"), dir_name)
    else:
        dir_name = name if name.startswith("@") else f"@{name}"
        full_path = os.path.join(base, "Documents", dir_name)
    
    # Create directory structure
    os.makedirs(full_path, exist_ok=True)
    
    # For Functional/Sub: create _control/ directory
    if dtype in ("Functional", "Sub", "Filelib"):
        control_dir = os.path.join(full_path, "_control")
        os.makedirs(control_dir, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        for cf_name, cf_template in CONTROL_FILES.items():
            cf_path = os.path.join(control_dir, cf_name)
            content = cf_template.format(name=name, date=today)
            with open(cf_path, "w") as f:
                f.write(content)
            print(f"  ✅ _control/{cf_name}")

        # KEMS v7.1: 默认加 l4-kernel.md
        if args.l4_kernel or dtype in ("Functional", "Sub"):
            l4k_path = os.path.join(control_dir, "l4-kernel.md")
            l4k_content = L4_KERNEL_TEMPLATE.format(
                name=name, dtype=dtype, desc=desc, date=today, parent=parent or "—"
            )
            with open(l4k_path, "w") as f:
                f.write(l4k_content)
            print(f"  ✅ _control/l4-kernel.md (KEMS v7.1)")
    
    if dtype in ("Functional", "Infrastructure"):
        for plane in ["_entities", "_knowledge", "_storage", "_archive"]:
            os.makedirs(os.path.join(full_path, plane), exist_ok=True)
            print(f"  ✅ {plane}/")
    
    # Create CLAUDE.md
    template = TEMPLATES.get(dtype, TEMPLATES["Functional"])
    today = datetime.now().strftime("%Y-%m-%d")
    from datetime import timedelta
    next_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    claude_content = template.format(name=name, desc=desc, date=today, next_date=next_date, parent=parent or "")
    claude_path = os.path.join(full_path, "CLAUDE.md")
    with open(claude_path, "w") as f:
        f.write(claude_content)
    print(f"  ✅ CLAUDE.md")
    
    print(f"\n✅ {name} ({dtype}) 域骨架已创建: {full_path}")
    print(f"\n下一步:")
    print(f"  1. 编辑 CLAUDE.md 完善 SSOT 声明和场景路由")
    print(f"  2. 注册到 @驾驶舱 DOMAIN-INDEX.md")
    print(f"  3. 配置关联域引用")
    if dtype != "Aggregate":
        print(f"  4. 填充 _control/STATE.md 和 _control/MEMORY.md")


if __name__ == "__main__":
    run()
