#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KEMS 域初始化引导器 — kems-init.py
一条命令生成新域的 KEMS v2.0 骨架（六平面 + 元模型 + 本体 + 工具链 + 入口协议），
使「推广到其他域」从手册变成可执行。

用法：
  python3 _runtime/kems-init.py --root ~/Documents/@工作文档/国转中心 --domain work-guozhuan --name "国转中心"
  python3 _runtime/kems-init.py --root <路径> --domain <域标记> --name <名称> --verify   # 生成后跑守卫

来源域（模板/工具链）：本脚本所在域的父目录（卫健委）。
"""
import argparse, os, shutil, sys
from pathlib import Path

ORIGIN = Path(__file__).parent.parent  # 卫健委域根（模板源）


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"  ✍️ {p.relative_to(ORIGIN) if p.is_relative_to(ORIGIN) else p}")


def main():
    ap = argparse.ArgumentParser(description="KEMS v2.0 域初始化引导器")
    ap.add_argument("--root", required=True, help="目标域根路径")
    ap.add_argument("--domain", required=True, help="域标记 (如 work-guozhuan)")
    ap.add_argument("--name", required=True, help="域显示名")
    ap.add_argument("--verify", action="store_true", help="生成后运行 check-ssot-sync 守卫")
    a = ap.parse_args()

    root = Path(a.root).expanduser()
    if root.exists() and any(root.iterdir()):
        print(f"❌ 目标域非空: {root}（请用空目录或 --force）")
        return 1

    print(f"🔨 初始化 KEMS v2.0 域: {a.name} ({a.domain})")
    print(f"   目标: {root}\n")

    # ---- 1. 六平面 ----
    for d in ["_control", "_entities", "_entities/ontology", "_entities/models", "_entities/entities",
              "_knowledge", "_storage", "_runtime", "_meta/框架", "_meta/_methods"]:
        (root / d).mkdir(parents=True, exist_ok=True)
    print("  ✅ 六平面骨架")

    # ---- 2. 入口协议 CLAUDE.md ----
    write(root / "CLAUDE.md", f"""---
domain: {a.domain}
title: "CLAUDE.md — {a.name} 域入口"
---

# {a.name} 域入口（KEMS v2.0）

> L4 | {a.name} | KEMS 框架 v2.0（决策支撑化）
> 生成：kems-init.py · {__import__("datetime").date.today()}

## 会话入口协议

```
Step 0: 读 _control/STATE.md（当前状态）
Step 1: python3 _runtime/kems-toolkit.py --root <域根> --mode check --dry-run   ← 新输入检查
Step 2: python3 _runtime/check-ssot-sync.py   ← 【强制】SSOT 三层守卫（跳过=违规）
Step 3: 按任务路由定位
```

## 强制规则

1. **新输入检查**：任何新文件/通知先跑 kems-toolkit check（--dry-run 只读）
2. **SSOT 守卫**：模型/本体/实例改动后必跑 `check-ssot-sync.py` 全绿，跳过=违规
3. **数字机器化**：计数来自脚本断言，禁手抄
4. **诚实标注**：不确定标「需确认」

## 任务路由

| 用户说 | 入口 |
|--------|------|
| 一键快照/当前状态 | `python3 _runtime/kems-snapshot.py` |
| 问模型 | `python3 _runtime/model-ask.py "<问题>"` |
| 汇报 | `python3 _runtime/gen-report-view.py` |
| 查实体 | `python3 _runtime/graph-query.py <id>` |
| SSOT检查 | `python3 _runtime/check-ssot-sync.py` |

## 框架

- 规格：`_meta/框架/KEMS框架-v2.0.md`（五支柱）
- 推广：`_meta/框架/KEMS框架-推广指南.md`
""")

    # ---- 3. 控制面骨架 ----
    write(root / "_control/key-milestones.yaml", """# 关键路径里程碑 SSOT（域初始化骨架）
version: 1.0
domain: %s
milestones: []
""" % a.domain)
    write(root / "_control/STATE.md", f"""---
title: 当前工作状态
status: 已采纳
type: log
owner: {a.name}
created: {__import__("datetime").date.today()}
---
# STATE — 当前工作状态
（域初始化骨架，待填充活跃任务线）
""")
    write(root / "_control/signals.md", f"""# 信号动态
（域初始化骨架，新信号追加于此）
""")

    # ---- 4. 本体 + 元模型 ----
    write(root / "_entities/ontology/metamodel.yaml", """# KEMS 元模型（M2）— 域模板
version: 1.0
domain: %s
model-metaclass:
  required: [title, model_type, status, owner, created, review-date]
  review_freshness_days: 90
model-taxonomy: {ontology: 本体, domain: 域模型, data: 数据模型, view: 视图, strategy: 战略, governance: 治理, analysis: 分析}
conformance:
  - {id: CF-1, rule: 必填 6 字段}
  - {id: CF-2, rule: model_type 合法}
  - {id: CF-4, rule: 新鲜度 ≤90 天}
""" % a.domain)
    write(root / "_entities/ontology/classes.yaml", """# 实体类定义（9 类骨架，按域调整）
version: 1.0
domain: %s
classes:
  - {id: C1, code: Policy, name_cn: 政策法规类, instance_count: 0}
  - {id: C2, code: Organization, name_cn: 组织机构类, instance_count: 0}
  - {id: C3, code: Project, name_cn: 项目工程类, instance_count: 0}
  - {id: C4, code: System, name_cn: 应用系统类, instance_count: 0}
  - {id: C5, code: DataAsset, name_cn: 数据资源类, instance_count: 0}
  - {id: C6, code: Infrastructure, name_cn: 基础设施类, instance_count: 0}
  - {id: C7, code: Actor, name_cn: 人员角色类, instance_count: 0}
  - {id: C8, code: Assessment, name_cn: 监管考核类, instance_count: 0}
  - {id: C9, code: Intelligence, name_cn: 智能化应用类, instance_count: 0}
""" % a.domain)
    write(root / "_entities/ontology/relations.yaml", """# 关系定义（R1-R9 骨架）
version: 1.0
domain: %s
relations:
  - {id: R1, code: bases_on, source_classes: [C3], target_classes: [C1]}
  - {id: R2, code: governs, source_classes: [C2, C7], target_classes: [C2]}
  - {id: R3, code: implements, source_classes: [C3], target_classes: [C4, C2]}
  - {id: R4, code: deploys, source_classes: [C4], target_classes: [C6]}
  - {id: R5, code: data_flows, source_classes: [C2, C5, C4, C9], target_classes: [C5, C4, C9]}
  - {id: R6, code: assesses, source_classes: [C8], target_classes: [C2, C3]}
  - {id: R7, code: enables, source_classes: [C9], target_classes: [C4]}
  - {id: R8, code: cooperates, source_classes: [C2], target_classes: [C2]}
  - {id: R9, code: supplies, source_classes: [C2], target_classes: [C3]}
""" % a.domain)
    write(root / "_entities/ontology/layers.yaml", """# 分层架构（L0-L7 骨架）
version: 1.0
domain: %s
layers:
  - {id: L7, name: 治理考核层}
  - {id: L6, name: 智能化层}
  - {id: L5, name: 数据资源层}
  - {id: L4, name: 应用系统层}
  - {id: L3, name: 建设运营层}
  - {id: L2, name: 基础设施层}
  - {id: L1, name: 组织层}
  - {id: L0, name: 政策依据层}
""" % a.domain)
    write(root / "_entities/ontology/instances.yaml", """# 实体注册表（域初始化骨架）
version: 1.0
domain: %s
total_instances: 0
instances: []
""" % a.domain)
    write(root / "_entities/ontology/gaps.yaml", """# 信息缺口清单（域初始化骨架）
version: 1.0
domain: %s
gaps: []
""" % a.domain)
    write(root / "_entities/ontology/aliases.yaml", """# 别名/视图注册表（域初始化骨架）
version: 1.0
domain: %s
aliases: []
views: []
""" % a.domain)
    write(root / "_entities/ontology/constraints.yaml", """# 模型约束（五类 32 条，从发源域复制）
version: 1.0
domain: %s
""" % a.domain)
    # 复制约束模板
    shutil.copy(ORIGIN / "_entities/ontology/constraints.yaml", root / "_entities/ontology/constraints.yaml")
    print("  📋 复制 constraints.yaml（32 条模板）")

    # ---- 5. 最小决策视图 ----
    write(root / "_entities/models/模型驱动决策视图.md", f"""---
domain: {a.domain}
title: "模型驱动决策视图"
date: {__import__("datetime").date.today()}
status: active
type: view
owner: {a.name}
created: {__import__("datetime").date.today()}
last-reviewed: {__import__("datetime").date.today()}
version: v1.0
---
# 模型驱动决策视图（域初始化骨架）
（待按域填充项目/考核/数据/汇报/安全/预算六类决策）
""")

    # ---- 6. 工具链复制 ----
    TOOLS = ["check-ssot-sync.py", "check-ontology-consistency.py", "check-model-conformance.py",
             "refresh-indexes.py", "kems-snapshot.py", "model-ask.py", "gen-report-view.py",
             "graph-query.py", "kems-toolkit.py"]
    for t in TOOLS:
        src = ORIGIN / "_runtime" / t
        if src.exists():
            shutil.copy(src, root / "_runtime" / t)
    print(f"  📋 复制工具链 {len(TOOLS)} 个脚本（BASE 自适应域根）")

    # ---- 7. 框架规格 ----
    for f in ["KEMS框架-v2.0.md", "KEMS框架-推广指南.md"]:
        src = ORIGIN / "_meta" / "框架" / f
        if src.exists():
            shutil.copy(src, root / "_meta" / "框架" / f)
    print("  📋 复制框架规格 + 推广指南")

    print(f"\n✅ 域骨架生成完成: {root}")
    print(f"   下一步：\n    1. 填充 instances/gaps/models（按域实体）\n    2. 跑 `python3 _runtime/check-ssot-sync.py` 守卫\n    3. 参考推广指南 Step 1-5")

    # ---- 8. 验证 ----
    if a.verify:
        import subprocess
        r = subprocess.run([sys.executable, str(root / "_runtime/check-ssot-sync.py")],
                           cwd=root, capture_output=True, text=True, timeout=180)
        print("\n--- verify: check-ssot-sync ---")
        print(r.stdout[-300:] if r.stdout else r.stderr[-300:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
